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
import os
import re
import subprocess
from collections.abc import Callable
from typing import Any

from app.orchestration import engines
from app.orchestration.engines import DEFAULT_ENGINE
from app.orchestration.orchestrator import TrainingOrchestrator
from app.web import driver_scope

log = logging.getLogger(__name__)

# claude -p çıktısının SON satırındaki verdict işaretçisi.
_VERDICT_RE = re.compile(r"ACHILLES_HUNT_VERDICT:\s*(PASS|FAIL)", re.IGNORECASE)
HUNT_TIMEOUT_S = 1800  # 30 dk — CPU'da derin av uzun sürebilir.

# Araç deny-list'i motor kayıt tablosunda durur (motora ÖZGÜ bayraklar).
# Geriye dönük uyum + tek kaynak: buradan yeniden dışa aktarılır.
DISALLOWED_TOOLS = engines.DISALLOWED_TOOLS

# Çocuğa GEÇİRİLMEYECEK insan sırları. NOT: anahtarı silmek YETMEZ — Settings
# `env_file=".env"` kullandığı için silinen anahtar dotenv'den geri okunur
# (deneyle doğrulandı). Bu yüzden anahtar açıkça BOŞ STRING'e ezilir; env kaynağı
# pydantic-settings'te dotenv'den önceliklidir.
_HUMAN_SECRET_ENV = ("ACHILLES_API_TOKEN",)

# Çocuğa geçirilmeyecek AYAR-EZME değişkenleri. `--safe-mode` "admin-managed (policy)
# settings still apply" der; bu değişkenler harici bir ayar dosyası işaret ederek
# safe-mode'a rağmen hook/ayar geri getirebilir. Ebeveynin ortamı kirlenmişse
# (kalıcı shell profili, sistem-genel env) sürücü kısıtı sessizce delinirdi.
# Derinlemesine savunma: spawn öncesi açıkça temizlenir.
_SETTINGS_OVERRIDE_ENV = (
    "CLAUDE_CODE_MANAGED_SETTINGS_PATH",
    "CLAUDE_CODE_REMOTE_SETTINGS_PATH",
    "CLAUDE_CODE_MOCK_REMOTE_SETTINGS",
)

# runner sözleşmesi: (command, timeout_s, env) -> (returncode, combined_output)
Runner = Callable[..., tuple[int, str]]


def build_hunt_prompt(run: dict[str, Any]) -> str:
    """Headless claude -p için Kademe-2 derin av promptu (SALT RAPOR; kod/eğitim YOK)."""
    adapter = run.get("adapter_name", "achilles_lora")
    return (
        "Sen Achilles deposunda KADEME-2 derin adversarial bug-avı çalıştıran bir ajansın. "
        "İLK İŞ: depo kökündeki CLAUDE.md'yi Read ile OKU (safe-mode'da oto-keşif kapalıdır; "
        "kurallar oradadır). Bu, eğitim ÖNCESİ ZORUNLU denetimdir. KESİNLİKLE: yalnız RAPOR üret; "
        "KOD DEĞİŞTİRME, git commit/push YAPMA, EĞİTİM BAŞLATMA, hiçbir dosyaya yazma. "
        "Alt-sistem başına paralel bul → şüpheci adversarial doğrula (varsayılan çürütülmüş) "
        "→ yalnız onaylanan CİDDİ (HIGH/BLOCKER) bulguları say. Çıktının SON SATIRI tam olarak "
        "şu biçimde olmalı:\n"
        "ACHILLES_HUNT_VERDICT: PASS    (ciddi bulgu yok — eğitim güvenli)\n"
        "veya\n"
        "ACHILLES_HUNT_VERDICT: FAIL    (ciddi bulgu var — önce düzeltilmeli)\n"
        f"Bağlam: orkestrasyon koşusu, adapter={adapter}."
    )


def build_hunt_command(run: dict[str, Any], engine: str = DEFAULT_ENGINE) -> list[str]:
    """Seçili motorun argv'si (shell yok → enjeksiyon yok; prompt argv ÖĞESİ olarak geçer).

    Motor adı kayıt tablosundan gelir; bilinmeyen ad ValueError ile REDDEDİLİR.

    GÜVENLİK: sertleştirme bayrakları motorun `argv_template`'inde durur
    (`app/orchestration/engines.py`). `claude` motoru `--safe-mode` +
    `--strict-mcp-config` + `--disallowedTools` ile doğurulur; gerekçe için
    `engines.Engine.hardened` ve `docs/SCOPE_ISOLATION.md`.
    """
    return engines.build_command(engine, build_hunt_prompt(run))


def build_child_env(token: str, run_id: str) -> dict[str, str]:
    """Doğurulan motorun ortamı: insan sırları BOŞA ezilir, sürücü kimliği eklenir.

    Anahtarı ``del`` etmek yerine boş string'e ezmek ZORUNLU — bkz. ``_HUMAN_SECRET_ENV``.
    """
    env = dict(os.environ)
    for key in _HUMAN_SECRET_ENV:
        env[key] = ""
    # Ayar-ezme kanalları: burada SİLMEK doğru (boş string de geçerli bir yol sayılıp
    # hataya yol açabilir; yokluk = "ayar yok" demektir).
    for key in _SETTINGS_OVERRIDE_ENV:
        env.pop(key, None)
    env[driver_scope.DRIVER_TOKEN_ENV] = token
    env[driver_scope.DRIVER_RUN_ID_ENV] = run_id
    return env


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


def engine_available(engine: str = DEFAULT_ENGINE) -> bool:
    """Motor CLI'si PATH'te KURULU mu (giriş durumu DEĞİL — o ancak çalıştırınca anlaşılır)."""
    return engines.available(engine)


def claude_available() -> bool:
    """Geriye dönük uyumluluk: varsayılan (claude) motorunun kurulu olup olmadığı."""
    return engine_available(DEFAULT_ENGINE)


def _default_runner(
    command: list[str], timeout: int, env: dict[str, str] | None = None
) -> tuple[int, str]:
    # shell=False + argv listesi → kabuk enjeksiyonu yok. Çıktı (stdout+stderr) birleşik.
    # env: insan sırları temizlenmiş + sürücü kimliği eklenmiş ortam (build_child_env).
    proc = subprocess.run(
        command, capture_output=True, text=True, timeout=timeout, check=False, env=env
    )
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
        engine: str = DEFAULT_ENGINE,
        runner: Runner | None = None,
        timeout: int = HUNT_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Salt-okuma aşamaları → deep-hunt'ı claude -p ile sür → PASS ise onaya kadar ilerlet.

        Varsayılan `execute=False`: gerçek spawn YOK, çalıştırılacak komutu döner (DRY-RUN).
        `execute=True` + motor PATH'te: gerçek motor koşar; PASS → hunt_ack + onaya kadar
        ilerletir (Kural 8: onayda DURUR). `runner` enjekte edilirse gerçek spawn yerine o
        kullanılır (test). `engine` kayıt tablosundan gelir (bilinmeyen ad reddedilir);
        süreç başlatmayan motorlar (ör. `local`) otonom sürüşte kullanılamaz."""
        try:
            eng = engines.get_engine(engine)
        except ValueError as exc:
            return {"ok": False, "reason": str(exc)}
        if not eng.spawns:
            return {
                "ok": False,
                "reason": (
                    f"Motor '{eng.name}' süreç başlatmaz (doğrudan yerel hat) — "
                    "otonom derin av için spawn eden bir motor seç."
                ),
            }

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

        command = build_hunt_command(run, eng.name)

        if not execute:
            self.orch.store.add_event(
                run_id,
                "deep-hunt",
                "info",
                f"Otonom sürüş DRY-RUN: {eng.label} komutu hazır (execute=False; spawn yok).",
            )
            return {
                "ok": True,
                "drove": False,
                "dry_run": True,
                "engine": eng.name,
                "quota_warning": eng.quota_warning,
                "command": command,
                "needs": f"execute=True + kurulu `{eng.binary}` CLI (giriş kendi CLI'sinde)",
                **self.orch.status(run_id),
            }

        run_fn = runner or _default_runner
        # FAIL-CLOSED: sertleştirilmemiş motor DOĞURULMAZ. Araç kısıtı olmayan bir motor
        # auth'suz yerel CLI'yi (`achilles approval-approve`) veya 127.0.0.1:8765'i
        # çağırıp kendi eğitimini onaylayabilir → scope katmanı tamamen delinir (Kural 8).
        # `runner` enjekte edilmişse gerçek spawn yoktur (test yolu) → kısıt aranmaz.
        if runner is None and not eng.hardened:
            self.orch.store.add_event(
                run_id,
                "deep-hunt",
                "error",
                f"Otonom sürüş REDDEDİLDİ: {eng.label} araç-seviyesinde kısıtlanamıyor.",
            )
            return {
                "ok": False,
                "reason": (
                    f"{eng.label} sertleştirilmiş değil — AutoDriver yalnız araç-kısıtlı "
                    "motor doğurur. Kısıtsız motor kendi eğitimini onaylayabilir (Kural 8). "
                    "Bkz. docs/SCOPE_ISOLATION.md."
                ),
                "engine": eng.name,
                "hardened": False,
                "command": command,
            }
        if runner is None and not engine_available(eng.name):
            return {
                "ok": False,
                "reason": f"`{eng.binary}` CLI PATH'te yok — {eng.label} kurulu olmalı.",
                "engine": eng.name,
                "command": command,
            }

        self.orch.store.add_event(
            run_id,
            "deep-hunt",
            "info",
            f"Otonom sürüş: {eng.label} ile Kademe-2 derin av başladı. {eng.quota_warning}",
        )
        # Sürücü kimliği: bu koşuya bağlı, kısa ömürlü token. Motor bununla insan-yalnız
        # uçlarda 403 alır (Kural 8). Koşu bitince `finally` ile MUTLAKA iptal edilir.
        token = driver_scope.mint(run_id)
        try:
            _rc, output = run_fn(command, timeout, build_child_env(token, run_id))
        except Exception as exc:  # spawn/timeout — koşuyu çökertme, deep-hunt bloklu kalır
            log.exception("AutoDriver: %s çalıştırılamadı", eng.name)
            self.orch.store.add_event(run_id, "deep-hunt", "error", f"Otonom sürüş hatası: {exc}")
            return {
                "ok": False,
                "reason": f"{eng.label} çalıştırılamadı: {exc}",
                "engine": eng.name,
                "command": command,
            }
        finally:
            driver_scope.revoke_run(run_id)

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
        params["hunt_driven_by"] = f"{eng.name}-autodrive"
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
