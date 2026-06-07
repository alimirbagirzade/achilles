"""Matematik / istatistik doğrulayıcı — deterministik regex tabanlı.

Gate 5 için kullanılır. Hesap tutarlılığı, istatistiksel kırmızı bayraklar
ve aşırı emin yatırım dili gibi sorunları işaretler. LLM gerektirmez.
Şüpheli durumları otomatik reddetmek yerine `requires_review` ile
insan incelemesine yönlendirir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# İstatistiksel kırmızı bayraklar — varlığı uyarı doğurur.
STATISTICAL_FLAGS: list[str] = [
    "lookahead",
    "look-ahead",
    "look ahead",
    "survivorship bias",
    "survivorship",
    "data snooping",
    "data-snooping",
    "p-hacking",
    "p hacking",
]

# Aşırı emin / yanıltıcı yatırım ifadeleri — varlığı uyarı doğurur.
OVERCONFIDENT_PHRASES: list[str] = [
    "kesinlikle",
    "garanti",
    "her zaman kazanır",
    "risk yok",
    "asla kaybetmez",
    "guaranteed",
    "always wins",
    "no risk",
    "%100 kazanç",
    "100% profit",
]

# "%<sayı>" desenini yakalar.
_PERCENT_RE = re.compile(r"%\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*%")


@dataclass
class MathVerifyResult:
    """Bir metnin matematik/istatistik doğrulama sonucu."""

    passed: bool
    issues: list[str] = field(default_factory=list)
    requires_review: bool = False


def _extract_percentages(text: str) -> list[float]:
    """Metindeki yüzde değerlerini float listesi olarak çıkar."""
    values: list[float] = []
    for match in _PERCENT_RE.finditer(text):
        raw = match.group(1) or match.group(2)
        if raw is None:
            continue
        try:
            values.append(float(raw.replace(",", ".")))
        except ValueError:
            continue
    return values


def _check_percentage_sanity(text: str) -> list[str]:
    """Yüzde değerlerinin makul aralıkta olup olmadığını kontrol et.

    Risk yüzdesi bağlamında %100'ün çok üstündeki getiri iddiaları
    (örn. >%1000 yıllık) şüpheli olarak işaretlenir.
    """
    issues: list[str] = []
    lowered = text.lower()
    percentages = _extract_percentages(text)

    has_return_context = any(
        kw in lowered for kw in ("getiri", "return", "kâr", "kar", "profit", "yıllık", "annual")
    )
    if has_return_context:
        for pct in percentages:
            if pct > 1000:
                issues.append(f"şüpheli yüksek getiri iddiası (%{pct:g})")

    has_risk_context = "risk" in lowered
    if has_risk_context:
        for pct in percentages:
            if pct > 100:
                issues.append(f"risk yüzdesi %100'ü aşıyor (%{pct:g}) — tutarsız olabilir")
    return issues


def verify_math_content(text: str) -> MathVerifyResult:
    """Bir metni matematik/istatistik açısından doğrula.

    Geriye dönen sonuç:
      - `issues`: bulunan tüm uyarılar
      - `requires_review`: insan incelemesi gerekiyor mu
      - `passed`: aşırı emin yatırım ifadesi yoksa True (bunlar blocker)
    """
    if not text:
        return MathVerifyResult(passed=True)

    lowered = text.lower()
    issues: list[str] = []

    for flag in STATISTICAL_FLAGS:
        if flag in lowered:
            issues.append(f"istatistiksel risk işareti: '{flag}'")

    overconfident_found = False
    for phrase in OVERCONFIDENT_PHRASES:
        if phrase in lowered:
            issues.append(f"aşırı emin yatırım ifadesi: '{phrase}'")
            overconfident_found = True

    issues.extend(_check_percentage_sanity(text))

    requires_review = bool(issues)

    return MathVerifyResult(
        passed=not overconfident_found,
        issues=issues,
        requires_review=requires_review,
    )
