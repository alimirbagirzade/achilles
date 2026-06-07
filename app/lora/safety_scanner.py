"""Güvenlik / sır tarayıcısı — eğitim verisinde gizli ve tehlikeli içerik.

Gate 7 (BLOCKER) için kullanılır. Tek ihlal bile batch'i reddeder.
Regex tabanlı; LLM gerektirmez. API anahtarı, özel anahtar, parola,
kişisel veri ve kesin finansal yönlendirme arar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# (etiket, derlenmiş regex) çiftleri.
FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # 32+ karakter alfanumerik token (API key benzeri).
    ("api_key", re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")),
    # PEM özel anahtar başlığı.
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    # Bitcoin/Ethereum benzeri cüzdan adresi.
    ("wallet_address", re.compile(r"\b(?:0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")),
    # password= / token= / secret= atamaları.
    (
        "credential_assignment",
        re.compile(r"(?i)\b(?:password|passwd|token|secret|api[_-]?key)\s*[=:]\s*\S+"),
    ),
    # E-posta adresi.
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    # Telefon numarası (TR / uluslararası kaba desen).
    ("phone", re.compile(r"(?:\+90|0)?\s*\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b")),
    # TC kimlik numarası — 11 ardışık rakam.
    ("national_id", re.compile(r"\b\d{11}\b")),
]

# Kesin al/sat / garanti kâr yönlendirmesi (küçük harf eşleşme).
FINANCIAL_DIRECTIVES: list[str] = [
    "buy now",
    "sell now",
    "şimdi al",
    "şimdi sat",
    "garanti kar",
    "garanti kâr",
    "guaranteed profit",
    "risk yok",
    "no risk",
]


@dataclass
class SafetyResult:
    """Güvenlik taraması sonucu. `passed=False` ise batch reddedilir."""

    passed: bool
    violations: list[str] = field(default_factory=list)


def scan_for_secrets(text: str) -> SafetyResult:
    """Metni sır, kişisel veri ve finansal yönlendirme için tara.

    Tek bir ihlal bulunsa bile `passed=False` döner (kısmi geçiş yok).
    """
    if not text:
        return SafetyResult(passed=True)

    violations: list[str] = []

    for label, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            violations.append(f"yasak desen: {label}")

    lowered = text.lower()
    for directive in FINANCIAL_DIRECTIVES:
        if directive in lowered:
            violations.append(f"finansal yönlendirme: '{directive}'")

    return SafetyResult(passed=not violations, violations=violations)
