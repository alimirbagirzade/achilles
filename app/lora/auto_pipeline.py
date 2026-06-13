"""Auto-LoRA Pipeline — otomatik denetim + kullanıcı onaylı eğitim döngüsü.

Akış:
  1. [OTOMATİK] Her check_interval_min dakikada onaylı kart sayısını kontrol eder.
  2. MIN_ELIGIBLE_CARDS eşiğini geçince Gate 0-8 otomatik çalışır.
  3. [KULLANICI ONAYI] Eğitimi başlatmak için web UI onayı gerekir (CLAUDE.md kural 8).
  4. [OTOMATİK] Eğitim bitince eval çalıştırır, adapter'ı EVAL_PASSED olarak kaydeder.
  5. [KULLANICI ONAYI] Production'a terfi için web UI onayı gerekir.

State dosyası: storage/auto_lora_state.json
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class PipelineStage(StrEnum):
    IDLE = "idle"
    CHECKING = "checking"
    GATE_FAILED = "gate_failed"
    READY_TO_TRAIN = "ready_to_train"  # kullanıcı onayı bekliyor
    TRAINING = "training"
    TRAIN_FAILED = "train_failed"
    EVALUATING = "evaluating"
    EVAL_FAILED = "eval_failed"
    EVAL_SKIPPED = "eval_skipped"  # eval seti yok — TERFİ EDİLEMEZ (Anayasa II/VI)
    EVAL_PASSED = "eval_passed"  # production onayı bekliyor
    PROMOTED = "promoted"


@dataclass
class AutoPipelineState:
    stage: PipelineStage = PipelineStage.IDLE
    last_check: str = ""
    last_gate_result: str = ""
    gate_summary: str = ""
    approved_cards_at_last_check: int = 0
    adapter_id: str = ""
    adapter_path: str = ""
    eval_scores: dict[str, Any] = field(default_factory=dict)
    last_error: str = ""
    last_run: str = ""

    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "last_check": self.last_check,
            "last_gate_result": self.last_gate_result,
            "gate_summary": self.gate_summary,
            "approved_cards_at_last_check": self.approved_cards_at_last_check,
            "adapter_id": self.adapter_id,
            "adapter_path": self.adapter_path,
            "eval_scores": self.eval_scores,
            "last_error": self.last_error,
            "last_run": self.last_run,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AutoPipelineState:
        s = cls()
        s.stage = PipelineStage(d.get("stage", PipelineStage.IDLE.value))
        s.last_check = d.get("last_check", "")
        s.last_gate_result = d.get("last_gate_result", "")
        s.gate_summary = d.get("gate_summary", "")
        s.approved_cards_at_last_check = d.get("approved_cards_at_last_check", 0)
        s.adapter_id = d.get("adapter_id", "")
        s.adapter_path = d.get("adapter_path", "")
        s.eval_scores = d.get("eval_scores", {})
        s.last_error = d.get("last_error", "")
        s.last_run = d.get("last_run", "")
        return s


def _utcnow() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class AutoLoRAPipeline:
    """Otomatik LoRA denetim ve eğitim döngüsü yöneticisi."""

    def __init__(
        self,
        min_eligible_cards: int = 20,
        check_interval_min: int = 60,
        eval_pass_threshold: float = 0.5,
        auto_enabled: bool = False,
    ) -> None:
        self.min_eligible_cards = min_eligible_cards
        self.check_interval_min = check_interval_min
        self.eval_pass_threshold = eval_pass_threshold
        self.auto_enabled = auto_enabled
        self._state = self._load_state()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ state

    def _load_state(self) -> AutoPipelineState:
        path = Path("storage") / "auto_lora_state.json"
        if path.exists():
            try:
                return AutoPipelineState.from_dict(json.loads(path.read_text()))
            except Exception:
                pass
        return AutoPipelineState()

    def _save_state(self) -> None:
        path = Path("storage") / "auto_lora_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._state.to_dict(), indent=2))

    def get_status(self) -> dict:
        return self._state.to_dict() | {
            "auto_enabled": self.auto_enabled,
            "min_eligible_cards": self.min_eligible_cards,
            "check_interval_min": self.check_interval_min,
            "eval_pass_threshold": self.eval_pass_threshold,
        }

    def set_enabled(self, enabled: bool) -> None:
        self.auto_enabled = enabled

    # ------------------------------------------------------------------ gates

    async def check_and_prepare(self) -> dict:
        """Gate 0-8 çalıştır. Geçerse READY_TO_TRAIN'e geçer (kullanıcı onayı bekler)."""
        async with self._lock:
            self._state.stage = PipelineStage.CHECKING
            self._state.last_check = _utcnow()
            self._save_state()

        try:
            from app.lora.control_plane import LoRAControlPlane
            from app.memory.sqlite_store import SqliteStore

            store = SqliteStore()
            n_approved = len(store.list_approved_cards())

            async with self._lock:
                self._state.approved_cards_at_last_check = n_approved

            if n_approved < self.min_eligible_cards:
                async with self._lock:
                    self._state.stage = PipelineStage.IDLE
                    self._state.gate_summary = (
                        f"Yetersiz kart: {n_approved}/{self.min_eligible_cards}"
                    )
                    self._save_state()
                return {"ok": False, "reason": self._state.gate_summary}

            log.info("Auto-LoRA: Gate 0-8 başlatılıyor (%d kart)", n_approved)
            plane = LoRAControlPlane(store=store)
            report = await asyncio.to_thread(plane.run_full, False)

            async with self._lock:
                if report.passed:
                    self._state.stage = PipelineStage.READY_TO_TRAIN
                    self._state.last_gate_result = "passed"
                    self._state.gate_summary = (
                        f"{report.total_approved} kart onaylandı, "
                        f"{report.total_rejected} reddedildi"
                    )
                    log.info("Auto-LoRA: Gate geçti → kullanıcı onayı bekleniyor")
                else:
                    failed = [s.name for s in report.stages if not s.passed]
                    self._state.stage = PipelineStage.GATE_FAILED
                    self._state.last_gate_result = "failed"
                    self._state.gate_summary = f"Başarısız gate'ler: {failed}"
                    log.warning("Auto-LoRA: Gate başarısız: %s", failed)
                self._save_state()

            return {"ok": report.passed, "summary": self._state.gate_summary}

        except Exception as exc:
            async with self._lock:
                self._state.stage = PipelineStage.IDLE
                self._state.last_error = str(exc)
                self._save_state()
            log.exception("Auto-LoRA: check_and_prepare hatası")
            return {"ok": False, "reason": str(exc)}

    # ------------------------------------------------------------------ train

    async def start_training(self, adapter_name: str, iters: int = 300) -> dict:
        """Kullanıcı onayıyla eğitimi başlatır. READY_TO_TRAIN durumu gerekir."""
        async with self._lock:
            if self._state.stage != PipelineStage.READY_TO_TRAIN:
                return {
                    "ok": False,
                    "reason": (
                        f"Beklenen durum READY_TO_TRAIN, mevcut: {self._state.stage}. "
                        "Önce 'Gate Kontrolü Başlat' çalıştırın."
                    ),
                }

        from app.config.settings import get_settings
        from app.training.backend import detect_lora_backend
        from app.web.training_manager import get_training_manager

        settings = get_settings()
        manager = get_training_manager()
        backend = detect_lora_backend()

        if backend == "mlx":
            cmd = (
                f"python -m mlx_lm.lora "
                f"--model {settings.mlx_base_model} "
                f"--train "
                f"--data data/training/jsonl "
                f"--adapter-path models/adapters/{adapter_name} "
                f"--iters {iters}"
            )
        else:
            # Windows / Linux: PEFT backend (torch + peft).
            # MLX 4-bit modeli transformers ile yüklenemez → ayrı HF base model kullan.
            cmd = (
                f"python -m app.training.peft_lora_train "
                f"--model {settings.peft_base_model} "
                f"--train data/training/jsonl/train.jsonl "
                f"--valid data/training/jsonl/valid.jsonl "
                f"--output models/adapters/{adapter_name} "
                f"--iters {iters} "
                f"--run"
            )

        ok = manager.start(cmd.split(), adapter_name, iters)
        if not ok:
            return {"ok": False, "reason": "TrainingManager başlatılamadı (başka eğitim çalışıyor)"}

        async with self._lock:
            self._state.stage = PipelineStage.TRAINING
            self._state.adapter_path = f"models/adapters/{adapter_name}"
            self._state.last_run = _utcnow()
            self._state.last_error = ""
            self._save_state()

        task = asyncio.create_task(self._watch_training(adapter_name))
        task.add_done_callback(lambda _t: None)
        return {"ok": True, "adapter_name": adapter_name}

    async def _watch_training(self, adapter_name: str) -> None:
        """Eğitim tamamlanınca otomatik eval çalıştır."""
        from app.web.training_manager import TrainState, get_training_manager

        manager = get_training_manager()
        try:
            async for _progress in manager.subscribe():
                if manager._progress.state in (
                    TrainState.COMPLETED,
                    TrainState.FAILED,
                    TrainState.STOPPED,
                ):
                    break

            if manager._progress.state == TrainState.COMPLETED:
                log.info("Auto-LoRA: Eğitim tamamlandı → eval başlatılıyor")
                await self._run_eval(adapter_name)
            else:
                async with self._lock:
                    self._state.stage = PipelineStage.TRAIN_FAILED
                    self._state.last_error = "Eğitim COMPLETED olmadı"
                    self._save_state()
        except Exception as exc:
            async with self._lock:
                self._state.stage = PipelineStage.TRAIN_FAILED
                self._state.last_error = str(exc)
                self._save_state()
            log.exception("Auto-LoRA: _watch_training hatası")

    # ------------------------------------------------------------------ eval

    async def _run_eval(self, adapter_name: str) -> None:
        async with self._lock:
            self._state.stage = PipelineStage.EVALUATING
            self._save_state()

        try:
            eval_dir = Path("evals")
            eval_sets = list(eval_dir.glob("*.jsonl")) if eval_dir.exists() else []

            if not eval_sets:
                # Anayasa II/VI: test edilmeden "geçti" deme. Eval seti yoksa
                # EVAL_PASSED VARSAYMA — EVAL_SKIPPED yap (promote_to_production
                # yalnız EVAL_PASSED'i terfi ettirir, bu durum terfiyi bloklar).
                log.warning("Auto-LoRA: eval seti yok → EVAL_SKIPPED (terfi edilemez)")
                async with self._lock:
                    self._state.stage = PipelineStage.EVAL_SKIPPED
                    self._save_state()
                await self._register_adapter(adapter_name)
                return

            from app.training.evaluate_model import ModelEvaluator

            evaluator = ModelEvaluator()
            scores: dict[str, Any] = {}
            total = 0.0

            for es in eval_sets:
                result = await asyncio.to_thread(evaluator.run_eval, es, adapter_name)
                scores[es.stem] = result
                total += result.get("pass_rate", 0.0)

            avg = total / len(eval_sets)
            passed = avg >= self.eval_pass_threshold

            # Eval sonuçlarını kalıcı DB'ye kaydet
            try:
                from app.memory.sqlite_store import SqliteStore

                store = SqliteStore()
                for es in eval_sets:
                    r = scores.get(es.stem, {})
                    store.save_eval_history(
                        adapter_name=adapter_name,
                        eval_set=es.stem,
                        pass_rate=float(r.get("pass_rate", 0.0)),
                        total_items=int(r.get("total", 0)),
                        passed_items=int(r.get("passed", 0)),
                    )
            except Exception:
                log.warning("Auto-LoRA: eval_history kaydedilemedi")

            async with self._lock:
                self._state.eval_scores = scores
                if passed:
                    self._state.stage = PipelineStage.EVAL_PASSED
                    log.info("Auto-LoRA: Eval geçti (%.2f) → production onayı bekleniyor", avg)
                else:
                    self._state.stage = PipelineStage.EVAL_FAILED
                    self._state.last_error = (
                        f"Eval başarısız: ort={avg:.2f} < eşik={self.eval_pass_threshold}"
                    )
                    log.warning("Auto-LoRA: Eval başarısız: %.2f", avg)
                self._save_state()

            if passed:
                await self._register_adapter(adapter_name)

        except Exception as exc:
            async with self._lock:
                self._state.stage = PipelineStage.EVAL_FAILED
                self._state.last_error = str(exc)
                self._save_state()
            log.exception("Auto-LoRA: eval hatası")

    async def _register_adapter(self, adapter_name: str) -> None:
        try:
            from app.config.settings import get_settings
            from app.lora.adapter_registry import AdapterRecord, AdapterRegistry, AdapterStatus

            settings = get_settings()
            registry = AdapterRegistry()
            record = AdapterRecord(
                base_model=settings.mlx_base_model,
                adapter_name=adapter_name,
                eval_score=self._state.eval_scores.get("discipline_core", {}).get("pass_rate"),
            )
            # Eval gerçekten geçtiyse EVAL_PASSED; eval atlandıysa yalnız SMOKE_PASSED
            # (registry de yanlış "eval geçti" damgası vurmasın — Anayasa II/VI).
            record.status = (
                AdapterStatus.EVAL_PASSED
                if self._state.stage == PipelineStage.EVAL_PASSED
                else AdapterStatus.SMOKE_PASSED
            )
            adapter_id = await asyncio.to_thread(registry.register, record)
            async with self._lock:
                self._state.adapter_id = adapter_id
                self._save_state()
            log.info("Auto-LoRA: Adapter kaydedildi: %s", adapter_id)
        except Exception as exc:
            log.exception("Auto-LoRA: adapter kayıt hatası")
            async with self._lock:
                self._state.last_error = str(exc)
                self._save_state()

    # ------------------------------------------------------------------ promote

    async def promote_to_production(self) -> dict:
        """Kullanıcı onayıyla production'a terfi et."""
        async with self._lock:
            if self._state.stage != PipelineStage.EVAL_PASSED:
                return {
                    "ok": False,
                    "reason": f"Beklenen EVAL_PASSED, mevcut: {self._state.stage}",
                }
            adapter_id = self._state.adapter_id

        if not adapter_id:
            return {"ok": False, "reason": "Kayıtlı adapter ID bulunamadı"}

        try:
            from app.lora.adapter_registry import AdapterRegistry

            registry = AdapterRegistry()
            ok = await asyncio.to_thread(registry.promote, adapter_id, True)
            if ok:
                async with self._lock:
                    self._state.stage = PipelineStage.PROMOTED
                    self._save_state()
                return {"ok": True, "adapter_id": adapter_id}
            return {"ok": False, "reason": "Registry terfi başarısız"}
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}

    # ------------------------------------------------------------------ reset

    async def reset(self) -> None:
        """Pipeline'ı IDLE'a sıfırla."""
        async with self._lock:
            self._state = AutoPipelineState()
            self._save_state()

    # ------------------------------------------------------------------ background loop

    async def background_loop(self) -> None:
        log.info(
            "Auto-LoRA arka plan döngüsü başladı (enabled=%s, interval=%d dk, min_cards=%d)",
            self.auto_enabled,
            self.check_interval_min,
            self.min_eligible_cards,
        )
        while True:
            await asyncio.sleep(self.check_interval_min * 60)
            if not self.auto_enabled:
                continue
            if self._state.stage not in (PipelineStage.IDLE, PipelineStage.GATE_FAILED):
                continue
            log.info("Auto-LoRA: Periyodik kontrol başlatılıyor")
            await self.check_and_prepare()


# ---------- singleton ----------

_pipeline: AutoLoRAPipeline | None = None


def get_auto_pipeline() -> AutoLoRAPipeline:
    global _pipeline
    if _pipeline is None:
        from app.config.settings import get_settings

        s = get_settings()
        _pipeline = AutoLoRAPipeline(
            min_eligible_cards=getattr(s, "auto_lora_min_cards", 20),
            check_interval_min=getattr(s, "auto_lora_check_interval_min", 60),
            eval_pass_threshold=getattr(s, "auto_lora_eval_threshold", 0.5),
            auto_enabled=getattr(s, "auto_lora_enabled", False),
        )
    return _pipeline
