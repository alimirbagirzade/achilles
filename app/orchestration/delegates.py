"""delegates.py — orkestrasyon aşamalarının GERÇEK fonksiyonlara bağlanması.

Her delege `RunContext` alır, `StageResult` döner. İç-bağımlılıklar SAVUNMACI import
edilir (eksikse aşama makul biçimde blocked/skipped olur, koşu çökmez).

Güvenlik sınırı (CLAUDE.md Kural 8):
  - Salt-okuma aşamaları (preflight/data-gate/curriculum/dry-run) GERÇEK çalışır.
  - `deep-hunt` zorunlu Kademe-2 avı temsil eder → hunt_ack olmadan blocked.
  - `approval` TAZE insan onayı ister → onaysız blocked.
  - `train`/`evaluate`/`registry` varsayılan olarak HANDOFF'tur (gerçek detached
    yürütme bilinçli olarak gözetimsiz BAŞLATILMAZ; web tek-tık akışı ayrı, onay-kapılı
    bir "yürüten delege" seti enjekte ederek devralır).
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.orchestration.pipeline import StageStatus

if TYPE_CHECKING:
    from app.orchestration.orchestrator import RunContext, StageDelegate, StageResult

log = logging.getLogger(__name__)

_SFT_REL = ("data", "lora_sft", "lora_sft.jsonl")


def _result(status: StageStatus, message: str, output: dict | None = None) -> StageResult:
    # Lazy import — orchestrator ↔ delegates döngüsünü kırar.
    from app.orchestration.orchestrator import StageResult as _SR

    return _SR(status=status, message=message, output=output or {})


def _deps_available() -> bool:
    """torch + transformers + peft kurulu mu (gerçek eğitim/eval için)."""
    return all(importlib.util.find_spec(m) is not None for m in ("torch", "transformers", "peft"))


def _count_sft_lines() -> tuple[int, Path]:
    from app.config import get_settings

    settings = get_settings()
    jsonl = settings.root.joinpath(*_SFT_REL)
    if not jsonl.exists():
        return 0, jsonl
    n = sum(1 for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip())
    return n, jsonl


# ── aşama delegeleri ─────────────────────────────────────────────────────────


def preflight(ctx: RunContext) -> StageResult:
    """STOP_ALL + veri hazırlığı + bağımlılık durumu — salt-okuma."""
    out: dict = {}
    stop_all = False
    try:
        from app.agents.runtime import supervisor

        stop_all = bool(supervisor.is_stop_all_active())
    except Exception as exc:  # supervisor yüklenemese bile koşu çökmesin
        out["supervisor_error"] = str(exc)
    out["stop_all"] = stop_all

    try:
        from app.training.detached_launch import readiness

        r = readiness()
        out["ready"] = bool(r.get("ready"))
        out["n_examples"] = int(r.get("ready_examples", 0))
        out["ready_label"] = r.get("ready_label", "")
    except Exception as exc:
        out["readiness_error"] = str(exc)

    out["train_deps_ok"] = _deps_available()

    if stop_all:
        return _result(StageStatus.blocked, "STOP_ALL aktif — orkestrasyon durdu.", out)
    return _result(StageStatus.completed, out.get("ready_label", "ön kontrol tamam"), out)


def deep_hunt(ctx: RunContext) -> StageResult:
    """Eğitim öncesi ZORUNLU Kademe-2 derin av (CLAUDE.md). hunt_ack olmadan blocked."""
    if bool(ctx.params.get("hunt_ack")):
        return _result(
            StageStatus.completed,
            "Kademe-2 derin av onaylandı (hunt_ack=true).",
            {"hunt_ack": True},
        )
    return _result(
        StageStatus.blocked,
        (
            "ZORUNLU: eğitim öncesi Kademe-2 derin adversarial bug-avı çalıştırılmalı "
            "(v5 regresyonu bu yüzden olmuştu). Tamamlanınca hunt_ack=true ile sürdür."
        ),
        {"hunt_ack": False},
    )


def data_gate(ctx: RunContext) -> StageResult:
    """pretrain-gate GO/NO-GO kalite kapısı — salt-okuma (LLM'siz)."""
    n, jsonl = _count_sft_lines()
    if n == 0:
        return _result(
            StageStatus.failed,
            f"SFT verisi yok veya boş: {jsonl.name}",
            {"exists": jsonl.exists(), "n_lines": 0},
        )
    try:
        from app.training.dataset_quality import audit_dataset
        from app.training.discipline_dataset import discipline_jsonl_lines

        lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
        report = audit_dataset(lines, discipline_lines=discipline_jsonl_lines())
        out = report.to_dict()
        if report.verdict == "GO":
            return _result(
                StageStatus.completed,
                f"GO — {report.total} örnek, öneri {report.recommended_epochs} epoch.",
                out,
            )
        reason = "; ".join(report.blockers) or "kalite kapısı NO-GO"
        return _result(StageStatus.blocked, f"NO-GO: {reason}", out)
    except Exception as exc:
        return _result(StageStatus.failed, f"Kalite kapısı hatası: {exc}", {"n_lines": n})


def curriculum(ctx: RunContext) -> StageResult:
    """Müfredat seviyelendirme şeması (L0-L4) hazır mı — hafif, salt-okuma."""
    try:
        from app.lora.curriculum import LEVEL_BOUNDS

        return _result(
            StageStatus.completed,
            f"Müfredat şeması hazır — {len(LEVEL_BOUNDS)} seviye (L0-L4).",
            {"levels": list(LEVEL_BOUNDS.keys())},
        )
    except Exception as exc:
        return _result(StageStatus.skipped, f"Müfredat modülü yüklenemedi: {exc}", {})


def dry_run(ctx: RunContext) -> StageResult:
    """Eğitim komutu + örnek sayısı önizleme — gerçek yürütme/yazma YOK."""
    from app.config import get_settings

    settings = get_settings()
    model = ctx.run.get("model", "") or getattr(settings, "peft_base_model", "")
    profile = ctx.run.get("profile", "") or "discipline_safe_local"
    adapter = ctx.run.get("adapter_name", "") or "achilles_lora"
    iters = int(ctx.params.get("iters", 0) or 0)
    n, _ = _count_sft_lines()
    cmd = f"achilles train --run --backend peft --profile {profile} --adapter {adapter}"
    out = {
        "command": cmd,
        "model": model,
        "profile": profile,
        "adapter": adapter,
        "n_examples": n,
        "iters": iters,
    }
    return _result(StageStatus.completed, f"Komut hazır: {cmd}", out)


def approval(ctx: RunContext) -> StageResult:
    """Gerçek eğitim için TAZE insan onayı (Kural 8). Onaysız blocked."""
    try:
        from app.agents.runtime import approvals, supervisor
    except Exception as exc:
        return _result(StageStatus.failed, f"Onay altyapısı yüklenemedi: {exc}", {})

    if supervisor.is_stop_all_active():
        return _result(
            StageStatus.blocked, "STOP_ALL aktif — onay alınamaz.", {"blocked_by": "stop_all"}
        )

    adapter = ctx.run.get("adapter_name", "") or "achilles_lora"
    iters = int(ctx.params.get("iters", 300) or 300)
    decision = approvals.require_fresh_approval(
        "training-orchestrator",
        "orchestrate_train_run",
        "critical",
        f"Orkestrasyonlu gerçek eğitim: {adapter} ({iters} adım)",
    )
    if decision.authorized:
        return _result(
            StageStatus.completed,
            "Taze onay tüketildi — eğitim yetkili.",
            {"approval_id": decision.approval_id},
        )
    return _result(
        StageStatus.blocked,
        (
            "Gerçek eğitim TAZE onay gerektirir (Kural 8). Onayla: "
            f"achilles approval-approve {decision.approval_id} — sonra sürdür."
        ),
        {"approval_id": decision.approval_id, "needs_approval": True},
    )


def train_handoff(ctx: RunContext) -> StageResult:
    """Gerçek eğitimi gözetimsiz BAŞLATMAZ — detached devir talimatı verir (Kural 8)."""
    adapter = ctx.run.get("adapter_name", "") or "achilles_lora"
    iters = int(ctx.params.get("iters", 300) or 300)
    cmd = f"achilles train --run --adapter {adapter}"
    return _result(
        StageStatus.blocked,
        (
            "Onay alındı. Gerçek eğitim DEVRİ (detached): web tek-tık akışı bunu otomatik "
            f"delege eder; elle başlat: {cmd}"
        ),
        {"handoff": True, "command": cmd, "adapter": adapter, "iters": iters},
    )


def eval_handoff(ctx: RunContext) -> StageResult:
    """Eval, eğitim devri sonrası auto_pipeline tarafından yürütülür (handoff)."""
    return _result(
        StageStatus.skipped,
        "Eval, eğitim devri sonrası auto_pipeline._run_eval tarafından yürütülür.",
        {"handoff": True},
    )


def registry_handoff(ctx: RunContext) -> StageResult:
    """Kayıt, eval sonrası auto_pipeline tarafından yürütülür (handoff)."""
    return _result(
        StageStatus.skipped,
        "Adapter kaydı, eval sonrası auto_pipeline._register_adapter tarafından yapılır.",
        {"handoff": True},
    )


def default_delegates() -> dict[str, StageDelegate]:
    """Üretim varsayılanı: salt-okuma aşamaları gerçek; tehlikeli tail handoff."""
    return {
        "preflight": preflight,
        "deep-hunt": deep_hunt,
        "data-gate": data_gate,
        "curriculum": curriculum,
        "dry-run": dry_run,
        "approval": approval,
        "train": train_handoff,
        "evaluate": eval_handoff,
        "registry": registry_handoff,
    }
