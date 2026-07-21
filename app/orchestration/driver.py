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
import shutil
import subprocess
from collections.abc import Callable
from typing import Any

from app.orchestration.orchestrator import TrainingOrchestrator
from app.web import driver_scope

log = logging.getLogger(__name__)

# claude -p çıktısının SON satırındaki verdict işaretçisi.
_VERDICT_RE = re.compile(r"ACHILLES_HUNT_VERDICT:\s*(PASS|FAIL)", re.IGNORECASE)
HUNT_TIMEOUT_S = 1800  # 30 dk — CPU'da derin av uzun sürebilir.

# Doğurulan motorun YASAKLI araçları. Derin av SALT-OKUMADIR (Read/Grep/Glob yeter).
# Bu, prompt'taki "kod değiştirme / eğitim başlatma" talimatını TEKNİK olarak zorunlu
# kılar — prompt talimatı güvenlik sınırı DEĞİLDİR (RAG'e alınan bir makale/kart
# içeriği prompt-injection ile motoru yönlendirebilir).
#
# Bu kısıt olmadan scope katmanı TİYATRODUR: Bash'i olan bir motor HTTP'yi tamamen
# atlayıp `uv run achilles approval-approve <id>` / `clear-stop-all` çalıştırabilir —
# bu CLI komutları hiçbir kimlik doğrulamasından geçmez (denetim BLOCKER bulgusu).
# `Task` de yasak: aksi halde motor, kısıtsız araç setine sahip bir ALT-ajan doğurup
# bu deny-list'i dolaylı olarak aşabilir (deny-list'in alt-ajanlara özyinelemeli
# uygulandığı test edilmiş bir varsayım DEĞİLDİR).
DISALLOWED_TOOLS = (
    "Bash",
    "Edit",
    "Write",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
    "Task",
)

# Çocuğa GEÇİRİLMEYECEK insan sırları. NOT: anahtarı silmek YETMEZ — Settings
# `env_file=".env"` kullandığı için silinen anahtar dotenv'den geri okunur
# (deneyle doğrulandı). Bu yüzden anahtar açıkça BOŞ STRING'e ezilir; env kaynağı
# pydantic-settings'te dotenv'den önceliklidir.
_HUMAN_SECRET_ENV = ("ACHILLES_API_TOKEN",)

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


def build_hunt_command(run: dict[str, Any]) -> list[str]:
    """`claude -p <prompt>` argv'si (shell yok → enjeksiyon yok; prompt sabit şablon).

    ``--disallowedTools`` ile motor araç-seviyesinde kısıtlanır: Bash/Write olmadan
    ne yerel CLI'yi (auth'suz `approval-approve`) çalıştırabilir ne de dosya yazabilir.

    ``--safe-mode`` ZORUNLU — asıl sınır budur. Araç deny-list'i TEK BAŞINA yetmez:
    Claude Code'un *özelleştirme* kanalları (hook'lar, plugin'ler, MCP sunucuları,
    özel ajanlar/komutlar/skill'ler) araç katmanının DIŞINDA çalışır. İki somut
    denetim bulgusu bunu kanıtladı:

    - MCP: proje kapsamında kayıtlı `achilles` sunucusu (`mcp_server/achilles_mcp.py`)
      Achilles OpenAPI'sinden tool üretip ``127.0.0.1:8765``'e proxy'liyor → Bash
      OLMADAN HTTP isteği atan bir kanal (üstelik sürücü başlığı göndermediği için
      istekleri ``human`` scope'una düşerdi).
    - Hook'lar: ``.claude/settings.json`` içindeki ``SessionStart``/``PreToolUse``
      hook'ları Claude Code tarafından DOĞRUDAN kabukta çalıştırılır — ``Bash``
      *aracı* üzerinden değil. ``-p`` modunda güven (trust) diyaloğu atlandığı için
      onaysız çalışırlar; deny-list bunları hiç görmez.

    ``--safe-mode`` bu kanalların tamamını tek seferde kapatır (kanal kanal
    kovalamaca yerine sınıf-düzeyi çözüm). ``--strict-mcp-config`` kemer-askı olarak
    korunur. ``--disallowedTools`` ise yerleşik araçları kısar (safe-mode onları
    kısmaz) → iki bayrak BİRLİKTE gereklidir.

    NOT: ``--safe-mode`` CLAUDE.md oto-keşfini de kapatır; bu yüzden prompt, avcıya
    CLAUDE.md'yi AÇIKÇA okumasını söyler (Read aracı hâlâ açık).

    Bayrak sırası: ``--disallowedTools`` variadic (``<tools...>``) olduğundan EN SONDA
    durur ve tek virgüllü arg alır; aksi halde sonraki bayrakları yutabilir.
    """
    return [
        "claude",
        "-p",
        build_hunt_prompt(run),
        "--safe-mode",
        "--strict-mcp-config",
        "--disallowedTools",
        ",".join(DISALLOWED_TOOLS),
    ]


def build_child_env(token: str, run_id: str) -> dict[str, str]:
    """Doğurulan motorun ortamı: insan sırları BOŞA ezilir, sürücü kimliği eklenir.

    Anahtarı ``del`` etmek yerine boş string'e ezmek ZORUNLU — bkz. ``_HUMAN_SECRET_ENV``.
    """
    env = dict(os.environ)
    for key in _HUMAN_SECRET_ENV:
        env[key] = ""
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


def claude_available() -> bool:
    """Abonelikli `claude` CLI PATH'te mi (gerçek otonom sürüş için)."""
    return shutil.which("claude") is not None


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
        # Sürücü kimliği: bu koşuya bağlı, kısa ömürlü token. Motor bununla insan-yalnız
        # uçlarda 403 alır (Kural 8). Koşu bitince `finally` ile MUTLAKA iptal edilir.
        token = driver_scope.mint(run_id)
        try:
            _rc, output = run_fn(command, timeout, build_child_env(token, run_id))
        except Exception as exc:  # spawn/timeout — koşuyu çökertme, deep-hunt bloklu kalır
            log.exception("AutoDriver: claude -p çalıştırılamadı")
            self.orch.store.add_event(run_id, "deep-hunt", "error", f"Otonom sürüş hatası: {exc}")
            return {"ok": False, "reason": f"claude -p çalıştırılamadı: {exc}", "command": command}
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
