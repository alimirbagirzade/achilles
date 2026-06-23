"""Trading hipotez değerlendiricisi — bir fikrin "sinyal" değil "test edilebilir hipotez"
olduğunu denetler (CLAUDE.md Mutlak Kurallar 1-4).

Çıktı asla yatırım tavsiyesi DEĞİLDİR; bir hipotezin test edilmeye HAZIR olup
olmadığını puanlar. Salt-regex (eval/exec yok, Kural 5), deterministik.

Denetlenen maddeler:
- testable      : ölçülebilir/test edilebilir çerçeve var mı (Kural 2)
- costs         : komisyon/slippage/maliyet farkındalığı (Kural 3)
- out_of_sample : örneklem-dışı / look-ahead / walk-forward farkındalığı (Kural 2,4)
- no_advice     : "kesin/garanti/%100/risksiz" gibi tavsiye-kesinlik dili YOK (Kural 1)
- risk_noted    : risk notu var mı
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Kesinlik / tavsiye dili — VARSA hipotez reddedilir (Kural 1).
_ADVICE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"%\s*100|100\s*%|yüzde\s*yüz"),
    re.compile(r"(?i)\b(garanti|risksiz|kesin(likle)?|mutlaka)\b"),
    re.compile(r"(?i)\b(guaranteed|risk[\s-]?free|always wins?|surefire|can'?t lose)\b"),
    re.compile(r"(?i)\bkesin sinyal\b|\bal ve unut\b|\bhemen al\b|\bşimdi al\b"),
)
_TESTABLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(test|backtest|geri test|ölç|sına|doğrula|deneme|hipotez)\w*"),
    re.compile(r"(?i)\b(eğer|when|if)\b.*\b(ise|then|olur|artar|azalır)\b"),
)
_COST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(komisyon|slippage|kayma|işlem maliyet|maliyet|spread|ücret|fee)\w*"),
)
_OOS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(örneklem[\s-]?dışı|out[\s-]?of[\s-]?sample|oos|walk[\s-]?forward)\b"),
    re.compile(r"(?i)\b(look[\s-]?ahead|ileriye[\s-]?bakış|shift|gecikme|geciktir)\w*"),
)
_RISK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(risk|drawdown|stop[\s-]?loss|zarar|kayıp|pozisyon boyut)\w*"),
)

_TEXT_FIELDS = (
    "hypothesis_text",
    "hypothesis",
    "text",
    "title",
    "risk_notes",
    "assumptions",
    "required_data",
    "description",
)


@dataclass
class HypothesisEvalResult:
    """Tek bir trading hipotezinin değerlendirme sonucu (hipotez; tavsiye değil)."""

    hypothesis_id: str
    score: float  # 0.0–1.0
    verdict: str  # candidate / needs_revision / rejected
    checklist: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    note: str = "Bu bir test edilebilirlik puanıdır, yatırım tavsiyesi değildir."

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "score": self.score,
            "verdict": self.verdict,
            "checklist": self.checklist,
            "warnings": self.warnings,
            "note": self.note,
        }


def _collect_text(hypothesis: dict[str, Any] | str) -> str:
    if isinstance(hypothesis, str):
        return hypothesis
    parts: list[str] = []
    for key in _TEXT_FIELDS:
        val = hypothesis.get(key)
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list | tuple):
            parts.extend(str(v) for v in val)
    return "  ".join(parts)


def _any(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def evaluate_hypothesis(
    hypothesis: dict[str, Any] | str, *, hypothesis_id: str = ""
) -> HypothesisEvalResult:
    """Bir trading hipotezini test-edilebilirlik kuralları için değerlendir."""
    text = _collect_text(hypothesis)
    hid = hypothesis_id
    if not hid and isinstance(hypothesis, dict):
        hid = str(hypothesis.get("hypothesis_id") or hypothesis.get("id") or "")

    has_advice = _any(_ADVICE_PATTERNS, text)
    checklist = {
        "testable": _any(_TESTABLE_PATTERNS, text),
        "costs": _any(_COST_PATTERNS, text),
        "out_of_sample": _any(_OOS_PATTERNS, text),
        "no_advice": not has_advice,
        "risk_noted": _any(_RISK_PATTERNS, text),
    }
    warnings: list[str] = []
    if has_advice:
        warnings.append("Kesinlik/tavsiye dili tespit edildi (Kural 1) — hipotez reddedildi.")
    if not checklist["testable"]:
        warnings.append("Test edilebilir çerçeve yok — ölçülebilir koşul/backtest planı ekle.")
    if not checklist["costs"]:
        warnings.append("Maliyet (komisyon/slippage) farkındalığı yok (Kural 3).")
    if not checklist["out_of_sample"]:
        warnings.append("Örneklem-dışı / look-ahead farkındalığı yok (Kural 2,4).")
    if not checklist["risk_noted"]:
        warnings.append("Risk notu yok.")

    score = round(sum(1 for v in checklist.values() if v) / len(checklist), 4)

    # Verdict: tavsiye dili veya test-edilemezlik → HARD reddet (Kural 1,2).
    if has_advice or not checklist["testable"]:
        verdict = "rejected"
    elif not (checklist["costs"] and checklist["out_of_sample"]):
        verdict = "needs_revision"
    else:
        verdict = "candidate"

    return HypothesisEvalResult(
        hypothesis_id=hid or "hyp",
        score=score,
        verdict=verdict,
        checklist=checklist,
        warnings=warnings,
    )


def evaluate_many(
    hypotheses: list[dict[str, Any] | str],
) -> list[HypothesisEvalResult]:
    """Birden çok hipotezi sırayla değerlendir (deterministik)."""
    return [evaluate_hypothesis(h, hypothesis_id=f"hyp_{i}") for i, h in enumerate(hypotheses)]
