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

    def build_command(self, prompt: str) -> list[str]:
        """argv listesi kur — PROMPT sentinel'i prompt ile değiştirilir (kabuk YOK)."""
        if not self.spawns:
            raise ValueError(
                f"Motor '{self.name}' süreç başlatmaz (doğrudan yerel hat) — argv kurulamaz."
            )
        return [prompt if part == PROMPT else part for part in self.argv_template]


# ── Kota uyarıları — headless koşu, interaktif kullanımla AYNI pencereyi tüketir ────────
_SHARED = "Headless koşular interaktif kullanımla AYNI abonelik penceresini tüketir."
_Q_CLAUDE = f"{_SHARED} Otonom av, interaktif Claude Code kotanı yiyebilir."
_Q_CODEX = f"{_SHARED} Codex'te pencere 5 saatlik YUVARLANAN kotadır."
_Q_GEMINI = f"{_SHARED} Google hesabının günlük istek kotasına sayılır."
_Q_LOCAL = "Abonelik kotası YOK — yerel Ollama hattı (süreç başlatılmaz)."

# ── Kayıt tablosu — yeni motor eklemek TEK SATIR ────────────────────────────────────────
_ENGINES: tuple[Engine, ...] = (
    Engine("claude", "Claude Code (abonelik)", "claude", ("claude", "-p", PROMPT), _Q_CLAUDE),
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
