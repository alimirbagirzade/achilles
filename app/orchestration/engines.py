"""engines.py — yerel "motor" (abonelikli CLI ajanı) kayıt tablosu.

AutoDriver eskiden yalnız `claude`'u biliyordu. Bu modül onu küçük bir kayıt tablosuna
genelleştirir: her motor için ad, PATH yoklama komutu, argv şablonu ve insan-okur etiket.
Yeni motor eklemek `_ENGINES` içine TEK SATIR.

⛔ KİMLİK BİLGİSİ YOK (kalıcı kısıt — CLAUDE.md + [[no-api-local-subscription-only]]):
Achilles hiçbir motorun mail/şifre/API anahtarını TOPLAMAZ, SAKLAMAZ, İSTEMEZ. Motorlar
kendi CLI oturumlarıyla (abonelik OAuth) girişlidir; bizim işimiz yalnız "PATH'te kurulu mu"
tespiti. Bu yüzden `available()` KURULU-MU der, GİRİŞLİ-Mİ diyemez — giriş durumu ancak
motorun kendisi çalıştırılınca anlaşılır. Yalnız API anahtarıyla çalışan bir motor bu
tabloya EKLENMEZ.

GÜVENLİK: argv listesi + `shell=False` → prompt asla kabuğa string olarak geçmez. Şablondaki
`PROMPT` sentinel'i, komut kurulurken tam eşleşme ile TEK bir argv öğesi olarak değiştirilir;
metnin içeriği (tırnak, `;`, `&&`, `$(...)`) hiçbir zaman yorumlanmaz.

DETERMİNİZM: PATH yoklaması cache'lenir ama TTL AÇIKTIR (`PROBE_TTL_S`); saat ve `which`
enjekte edilebilir → testler gerçek PATH'e ve gerçek zamana bağlı değildir.
"""

from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)

# argv şablonunda prompt'un yerini tutan sentinel. Kullanıcı metniyle çakışması önemsizdir:
# değişim şablonun ÖĞELERİ üzerinde tam eşleşmeyle yapılır, prompt içeriğinde arama yapılmaz.
PROMPT = "\x00ACHILLES_PROMPT\x00"

# "Sür" modunda üretilen MCP config dosyasının yolunu tutan sentinel (aynı tam-eşleşme kuralı).
MCP_CONFIG = "\x00ACHILLES_MCP_CONFIG\x00"

# PATH yoklama cache ömrü (saniye). Motor oturum ortasında kurulabilir → sonsuz cache yanlış.
PROBE_TTL_S = 60.0

# which sözleşmesi: binary adı -> tam yol ya da None (enjekte edilebilir → offline test).
Which = Callable[[str], str | None]
# clock sözleşmesi: monotonik saniye (enjekte edilebilir → deterministik TTL testi).
Clock = Callable[[], float]


@dataclass(frozen=True)
class Engine:
    """Tek bir yerel motor tanımı (salt-okuma; kimlik bilgisi TAŞIMAZ)."""

    name: str
    label: str
    binary: str | None
    argv_template: tuple[str, ...]
    quota_warning: str
    spawns: bool = True
    # "Sür" (drive) modu argv şablonu — MCP erişimi GEREKTİRİR, bu yüzden av modundan
    # AYRI bir sertleştirme profili kullanır (bkz. _CLAUDE_DRIVE_ARGV). Boş = motor sür
    # modunu DESTEKLEMEZ (fail-closed).
    drive_argv_template: tuple[str, ...] = ()
    # Sür modu profili araç seviyesinde kısıtlı mı? Av modundaki `hardened`'DAN AYRIDIR:
    # sür modu `--safe-mode` KULLANAMAZ (o bayrak MCP'yi de kapatır) → farklı bayrak seti.
    drive_hardened: bool = False
    # Doğurulan ajan ARAÇ SEVİYESİNDE kısıtlanarak mı başlatılıyor?
    # AutoDriver YALNIZ hardened motorları doğurur (bkz. docs/SCOPE_ISOLATION.md):
    # kısıtsız bir motor, auth'suz yerel CLI'yi (`achilles approval-approve`) ya da
    # 127.0.0.1:8765'i çağırıp KENDİ eğitimini onaylayabilir → Kural 8 delinir.
    # Sertleştirme bayrakları motora ÖZGÜdür, bu yüzden motor bazında işaretlenir.
    hardened: bool = False

    def build_command(self, prompt: str) -> list[str]:
        """argv listesi kur — PROMPT sentinel'i prompt ile değiştirilir (kabuk YOK)."""
        if not self.spawns:
            raise ValueError(
                f"Motor '{self.name}' süreç başlatmaz (doğrudan yerel hat) — argv kurulamaz."
            )
        return [prompt if part == PROMPT else part for part in self.argv_template]

    def build_drive_command(self, prompt: str, mcp_config_path: str) -> list[str]:
        """ "Sür" modu argv'si — PROMPT ve MCP_CONFIG sentinel'leri değiştirilir (kabuk YOK).

        Sür modunu desteklemeyen motor ValueError ile REDDEDİLİR (sessiz av-moduna düşme YOK:
        av modu MCP'siz olduğundan sessiz düşüş, aracı olmayan bir ajan doğururdu)."""
        if not self.spawns or not self.drive_argv_template:
            raise ValueError(
                f"Motor '{self.name}' sür (drive) modunu desteklemiyor — "
                "MCP erişimli sertleştirilmiş şablonu yok."
            )
        if not mcp_config_path:
            raise ValueError("mcp_config_path boş olamaz — sür modu MCP config dosyası ister.")
        subs = {PROMPT: prompt, MCP_CONFIG: mcp_config_path}
        return [subs.get(part, part) for part in self.drive_argv_template]


# ── Kota uyarıları — headless koşu, interaktif kullanımla AYNI pencereyi tüketir ────────
_SHARED = "Headless koşular interaktif kullanımla AYNI abonelik penceresini tüketir."
_Q_CLAUDE = f"{_SHARED} Otonom av, interaktif Claude Code kotanı yiyebilir."
_Q_CODEX = f"{_SHARED} Codex'te pencere 5 saatlik YUVARLANAN kotadır."
_Q_GEMINI = f"{_SHARED} Google hesabının günlük istek kotasına sayılır."
_Q_LOCAL = "Abonelik kotası YOK — yerel Ollama hattı (süreç başlatılmaz)."

# ── Sertleştirme (yalnız `claude`) ──────────────────────────────────────────────────────
# Motorun YASAKLI yerleşik araçları. Derin av SALT-OKUMADIR (Read/Grep/Glob yeter).
# `Task` de yasak: kısıtsız araçlı bir ALT-ajan doğurup deny-list'i dolaylı aşmasın.
DISALLOWED_TOOLS: tuple[str, ...] = (
    "Bash",
    "Edit",
    "Write",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
    "Task",
)

# ÜÇÜ BİRLİKTE gerekli (bkz. docs/SCOPE_ISOLATION.md):
#  --safe-mode          : hook / plugin / MCP / özel ajan-komut-skill kanallarını kapatır.
#                         Bunlar araç katmanının DIŞINDA çalışır; deny-list onları GÖRMEZ.
#                         (Hook'lar `-p` modunda güven diyaloğu atlandığı için onaysız koşar.)
#  --strict-mcp-config  : kemer-askı; --mcp-config verilmediği için sıfır MCP sunucusu.
#  --disallowedTools    : yerleşik araçları kısar (safe-mode onları kısmaz).
#                         VARIADIC → argv'nin EN SONUNDA, tek virgüllü arg olarak durmalı,
#                         aksi halde sonraki bayrakları yutar.
_CLAUDE_ARGV: tuple[str, ...] = (
    "claude",
    "-p",
    PROMPT,
    "--safe-mode",
    "--strict-mcp-config",
    "--disallowedTools",
    ",".join(DISALLOWED_TOOLS),
)

# ── Sertleştirme — "sür" (drive) modu ───────────────────────────────────────────────────
# ⚠️ NEDEN AV MODUNDAN FARKLI: `claude --help`, `--safe-mode`'un devre dışı bıraktıkları
# arasında **MCP sunucularını** açıkça sayar. Sür modunun TÜM amacı Achilles MCP araçlarına
# erişim olduğundan `--safe-mode` KULLANILAMAZ — kullanılsaydı ajan araçsız kalırdı.
# `--bare` de ELENDİ: yardım metnine göre kimlik doğrulamayı "strictly ANTHROPIC_API_KEY"e
# indirger (OAuth/keychain okunmaz) → projenin KALICI "API ASLA" kısıtını ihlal ederdi
# (CLAUDE.md + HANDOFF; abonelik CLI'si şart).
# Bu yüzden safe-mode'un kapattığı kanallar TEK TEK, MCP'yi öldürmeden kapatılır:
#   --setting-sources ""      : user/project/local ayar kaynaklarının HİÇBİRİ yüklenmez →
#                               hook / özel ajan / plugin kaydı gelmez. (Hook'lar araç
#                               katmanının DIŞINDA, doğrudan kabukta koşar; deny-list onları
#                               GÖRMEZ — bu yüzden kritik.)
#   --disable-slash-commands  : skill kanalı kapalı.
#   --strict-mcp-config       : YALNIZ --mcp-config'teki sunucular; kullanıcı düzeyindeki
#                               `claude mcp add` kayıtları YOK SAYILIR → spawn kendine yeter.
#   --tools Read,Grep,Glob    : yerleşik araçlar için ALLOW-list (deny-list'ten güçlü:
#                               varsayılan KAPALI). Bash/Edit/Write/Task yok → ajan dosya
#                               düzenleyemez, kabuk açamaz, alt-ajan doğuramaz.
# ⚠️ ARTIK RİSK (dürüst ol): `--tools` yalnız YERLEŞİK araç kümesini kapsar; MCP araçları
# (`mcp__*`) bu listeye TABİ DEĞİLDİR. Sür modunda MCP yüzeyinin sınırı ARAÇ katmanında
# değil, SUNUCU tarafındadır: `require_human` + sürücü token'ı (bkz. mcp_server/
# achilles_mcp.py:driver_headers ve docs/SCOPE_ISOLATION.md).
DRIVE_ALLOWED_TOOLS: tuple[str, ...] = ("Read", "Grep", "Glob")

# ⚠️ SIRA ÖNEMLİ: hem `--tools` hem `--mcp-config` VARIADIC'tir (`<tools...>`, `<configs...>`).
# Variadic bir bayrak, `--` ile başlayan bir sonraki bayrağa kadar her şeyi yutar. Bu yüzden
# `--tools` tek virgüllü arg alır ve hemen ardından bir bayrak gelir; `--mcp-config` ise EN
# SONDA, tek yol argümanıyla durur.
_CLAUDE_DRIVE_ARGV: tuple[str, ...] = (
    "claude",
    "-p",
    PROMPT,
    "--setting-sources",
    "",
    "--disable-slash-commands",
    "--strict-mcp-config",
    "--tools",
    ",".join(DRIVE_ALLOWED_TOOLS),
    "--mcp-config",
    MCP_CONFIG,
)

# ── Kayıt tablosu — yeni motor eklemek TEK SATIR ────────────────────────────────────────
# ⚠️ Yeni motor eklerken `hardened=True` yalnız araç-kısıtı bayrakları DOĞRULANMIŞSA
# verilmelidir; aksi halde AutoDriver onu doğurmayı REDDEDER (fail-closed, doğru davranış).
_ENGINES: tuple[Engine, ...] = (
    Engine(
        "claude",
        "Claude Code (abonelik)",
        "claude",
        _CLAUDE_ARGV,
        _Q_CLAUDE,
        hardened=True,
        drive_argv_template=_CLAUDE_DRIVE_ARGV,
        drive_hardened=True,
    ),
    Engine("codex", "Codex CLI (ChatGPT planı)", "codex", ("codex", "exec", PROMPT), _Q_CODEX),
    Engine("gemini", "Gemini CLI (Google hesabı)", "gemini", ("gemini", "-p", PROMPT), _Q_GEMINI),
    Engine("local", "Yerel hat (Ollama)", None, (), _Q_LOCAL, spawns=False),
)

_BY_NAME: dict[str, Engine] = {engine.name: engine for engine in _ENGINES}

DEFAULT_ENGINE = "claude"

# PATH yoklama cache'i: motor adı -> (kurulu_mu, yoklama_zamanı).
_probe_cache: dict[str, tuple[bool, float]] = {}


def engine_names() -> list[str]:
    """Kayıtlı motor adları (tablo sırasıyla)."""
    return [engine.name for engine in _ENGINES]


def get_engine(name: str) -> Engine:
    """Ada göre motor getir; bilinmeyen ad REDDEDİLİR (sessiz varsayılana düşme YOK)."""
    engine = _BY_NAME.get(name)
    if engine is None:
        kayitli = ", ".join(engine_names())
        raise ValueError(f"Bilinmeyen motor: {name!r}. Kayıtlı motorlar: {kayitli}")
    return engine


def build_command(name: str, prompt: str) -> list[str]:
    """Verilen motor için argv listesi kur (bilinmeyen ad → ValueError)."""
    return get_engine(name).build_command(prompt)


def build_drive_command(name: str, prompt: str, mcp_config_path: str) -> list[str]:
    """Verilen motor için "sür" modu argv'si (bilinmeyen/desteklemeyen motor → ValueError)."""
    return get_engine(name).build_drive_command(prompt, mcp_config_path)


def drive_supported(name: str) -> bool:
    """Motor "sür" modunu destekliyor mu (MCP erişimli sertleştirilmiş şablonu var mı)?"""
    return bool(get_engine(name).drive_argv_template)


def reset_probe_cache() -> None:
    """PATH yoklama cache'ini temizle (test ve 'yeniden tara' için)."""
    _probe_cache.clear()


def available(
    name: str,
    *,
    which: Which | None = None,
    clock: Clock | None = None,
    use_cache: bool = True,
) -> bool:
    """Motor PATH'te KURULU mu (GİRİŞLİ mi DEĞİL — giriş yalnız çalıştırınca anlaşılır).

    Sonuç `PROBE_TTL_S` boyunca cache'lenir; `which`/`clock` enjekte edilirse cache atlanır
    (test yolu deterministik kalsın diye)."""
    engine = get_engine(name)
    if engine.binary is None:
        # Yerel hat — dış CLI gerektirmez, her zaman "kullanılabilir".
        return True

    injected = which is not None or clock is not None
    now = (clock or time.monotonic)()
    if use_cache and not injected:
        cached = _probe_cache.get(name)
        if cached is not None and (now - cached[1]) < PROBE_TTL_S:
            return cached[0]

    found = (which or shutil.which)(engine.binary) is not None
    if use_cache and not injected:
        _probe_cache[name] = (found, now)
    return found


def describe(name: str, *, which: Which | None = None) -> dict[str, object]:
    """UI/CLI için motor özeti — kimlik bilgisi ALANI YOK, yalnız kurulum durumu + kota uyarısı."""
    engine = get_engine(name)
    return {
        "name": engine.name,
        "label": engine.label,
        "spawns": engine.spawns,
        "installed": available(name, which=which),
        "quota_warning": engine.quota_warning,
    }


def describe_all(*, which: Which | None = None) -> list[dict[str, object]]:
    """Tüm motorların özeti (P5'te UI kota uyarısını buradan gösterecek)."""
    return [describe(name, which=which) for name in engine_names()]
