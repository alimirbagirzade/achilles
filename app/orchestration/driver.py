"""driver.py — AutoDriver: deep-hunt aşamasını headless `claude -p` ile otonom sürer.

Kullanıcının "tek tuş → Claude aboneliğiyle devreye soksun" isteğinin çekirdeği. Orchestrator'ın
salt-okuma aşamalarını ilerletir, ZORUNLU `deep-hunt` (Kademe-2 derin av) aşamasını headless
`claude -p` ile otonom çalıştırır, PASS ise onay kapısına kadar ilerletir.

GÜVENLİK (Kural 8): onay kapısında DURUR — gerçek eğitim yine TAZE insan onayı bekler; train
aşaması varsayılan HANDOFF. AutoDriver eğitim BAŞLATMAZ.

LOCAL-FIRST: `claude -p` ABONELİK CLI'sidir (API key DEĞİL; weekly-bug-scan.ps1 ile aynı yol).
Spawn yalnız `execute=True` + `claude` PATH'te iken yapılır; varsayılan DRY-RUN komutu döner
(Kural 8 deseni). `runner` enjekte edilebilir → testler gerçek spawn olmadan çalışır.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from collections.abc import Callable
from typing import Any

from app.orchestration.orchestrator import TrainingOrchestrator

log = logging.getLogger(__name__)

# claude -p çıktısının SON satırındaki verdict işaretçisi.
_VERDICT_RE = re.compile(r"ACHILLES_HUNT_VERDICT:\s*(PASS|FAIL)", re.IGNORECASE)
HUNT_TIMEOUT_S = 1800  # 30 dk — CPU'da derin av uzun sürebilir.

# runner sözleşmesi: (command, timeout_s) -> (returncode, combined_output)
Runner = Callable[[list[str], int], tuple[int, str]]


def build_hunt_prompt(run: dict[str, Any]) -> str:
    """Headless claude -p için Kademe-2 derin av promptu (SALT RAPOR; kod/eğitim YOK)."""
    adapter = run.get("adapter_name", "achilles_lora")
    return (
        "Sen Achilles deposunda KADEME-2 derin adversarial bug-avı çalıştıran bir ajansın "
        "(CLAUDE.md). Bu, eğitim ÖNCESİ ZORUNLU denetimdir. KESİNLİKLE: yalnız RAPOR üret; "
        "KOD DEĞİŞTİRME, git commit/push YAPMA, EĞİTİM BAŞLATMA, hiçbir dosyaya yazma. "
        "Alt-sistem başına paralel bul → şüpheci adversarial doğrula (varsayılan çürütülmüş) "
        "→ yalnız onaylanan CİDDİ (HIGH/BLOCKER) bulguları say. Çıktının SON SATIRI tam olarak "
        "şu biçimde olmalı:\n"
        "ACHILLES_HUNT_VERDICT: PASS    (ciddi bulgu yok — eğitim güvenli)\n"
        "veya\n"
        "ACHILLES_HUNT_VERDICT: FAIL    (ciddi bulgu var — önce düzeltilmeli)\n"
        f"Bağlam: orkestrasyon koşusu, adapter={adapter}."
    )


def build_hunt_command(run: dict[str, Any]) -> list[str]:
    """`claude -p <prompt>` argv'si (shell yok → enjeksiyon yok; prompt sabit şablon)."""
    return ["claude", "-p", build_hunt_prompt(run)]


def parse_hunt_verdict(output: str) -> dict[str, Any]:
    """claude çıktısından verdict satırını (sondan) ayıkla → {verdict, passed, summary}."""
    match = None
    for line in reversed((output or "").splitlines()):
        match = _VERDICT_RE.search(line)
        if match:
            break
    if match is None:
        return {
            "verdict": "unknown",
            "passed": False,
            "summary": "Verdict satırı (ACHILLES_HUNT_VERDICT) bulunamadı — güvenli tarafta FAIL.",
        }
    verdict = match.group(1).upper()
    return {"verdict": verdict, "passed": verdict == "PASS", "summary": (output or "")[-600:]}


def claude_available() -> bool:
    """Abonelikli `claude` CLI PATH'te mi (gerçek otonom sürüş için)."""
    return shutil.which("claude") is not None


def _default_runner(command: list[str], timeout: int) -> tuple[int, str]:
    # shell=False + argv listesi → kabuk enjeksiyonu yok. Çıktı (stdout+stderr) birleşik.
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


class AutoDriver:
    """deep-hunt'ı headless claude -p ile süren otonom orkestrasyon sürücüsü."""

    def __init__(self, orchestrator: TrainingOrchestrator | None = None) -> None:
        self.orch = orchestrator or TrainingOrchestrator()

    def drive(
        self,
        run_id: str,
        *,
        execute: bool = False,
        runner: Runner | None = None,
        timeout: int = HUNT_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Salt-okuma aşamaları → deep-hunt'ı claude -p ile sür → PASS ise onaya kadar ilerlet.

        Varsayılan `execute=False`: gerçek spawn YOK, çalıştırılacak komutu döner (DRY-RUN).
        `execute=True` + claude PATH'te: gerçek `claude -p` koşar; PASS → hunt_ack + onaya
        kadar ilerletir (Kural 8: onayda DURUR). `runner` enjekte edilirse gerçek spawn yerine
        o kullanılır (test)."""
        run = self.orch.store.get_run(run_id)
        if run is None:
            return {"ok": False, "reason": f"Koşu bulunamadı: {run_id}"}

        # 1) Salt-okuma aşamalarını deep-hunt bloğuna kadar ilerlet.
        snap = self.orch.run_until_blocked(run_id)
        run_now = snap.get("run") or {}
        cur, status = run_now.get("current_stage"), run_now.get("status")

        if cur != "deep-hunt" or status != "blocked":
            # Zaten geçmiş ya da başka yerde bloklanmış/bitmiş → otonom sürüş gereksiz.
            return {
                "ok": True,
                "drove": False,
                "reason": f"deep-hunt'ta blocked değil (current={cur}, status={status})",
                **snap,
            }

        command = build_hunt_command(run)

        if not execute:
            self.orch.store.add_event(
                run_id,
                "deep-hunt",
                "info",
                "Otonom sürüş DRY-RUN: claude -p komutu hazır (execute=False; spawn yok).",
            )
            return {
                "ok": True,
                "drove": False,
                "dry_run": True,
                "command": command,
                "needs": "execute=True + abonelikli `claude` CLI",
                **self.orch.status(run_id),
            }

        run_fn = runner or _default_runner
        if runner is None and not claude_available():
            return {
                "ok": False,
                "reason": "`claude` CLI PATH'te yok — abonelikli Claude Code kurulu olmalı.",
                "command": command,
            }

        self.orch.store.add_event(
            run_id, "deep-hunt", "info", "Otonom sürüş: claude -p ile Kademe-2 derin av başladı."
        )
        try:
            _rc, output = run_fn(command, timeout)
        except Exception as exc:  # spawn/timeout — koşuyu çökertme, deep-hunt bloklu kalır
            log.exception("AutoDriver: claude -p çalıştırılamadı")
            self.orch.store.add_event(run_id, "deep-hunt", "error", f"Otonom sürüş hatası: {exc}")
            return {"ok": False, "reason": f"claude -p çalıştırılamadı: {exc}", "command": command}

        verdict = parse_hunt_verdict(output)
        if not verdict["passed"]:
            self.orch.store.add_event(
                run_id,
                "deep-hunt",
                "warning",
                f"Derin av {verdict['verdict']} → deep-hunt bloklu kalır (eğitim ilerlemez).",
            )
            return {
                "ok": True,
                "drove": True,
                "hunt_passed": False,
                "verdict": verdict,
                **self.orch.status(run_id),
            }

        # 2) PASS → hunt_ack=true işaretle + onay kapısına kadar ilerlet (orada DURUR — Kural 8).
        params = dict(run.get("params") or {})
        params["hunt_ack"] = True
        params["hunt_driven_by"] = "claude-p-autodrive"
        self.orch.store.update_run(
            run_id, params_json=json.dumps(params, ensure_ascii=False, default=str)
        )
        self.orch.store.add_event(
            run_id,
            "deep-hunt",
            "info",
            "Derin av PASS → hunt_ack=true; onay kapısına ilerletiliyor (eğitim onay bekler).",
        )
        final = self.orch.run_until_blocked(run_id)
        return {"ok": True, "drove": True, "hunt_passed": True, "verdict": verdict, **final}
