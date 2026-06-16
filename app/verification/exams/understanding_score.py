"""UnderstandingScore — objektif anlama-skoru toplayıcı.

Kaba "anlama %"nin (öz-değerlendirme/keyword) yerine, L3/L4/L5 sınavlarının
OBJEKTİF sonuçlarını tek bir geçme-oranına toplar:

    pass_rate = passed / (passed + failed)

'skipped' (LLM yok) ve 'no_data' (belirgin yön/veri yok) paydaya KATILMAZ —
ayrı raporlanır (şeffaflık; sahte yüksek skor üretmeyiz). Hiç notlanan sınav
yoksa skor 'insufficient_data' bayrağıyla döner (CLAUDE.md Kural 2).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.verification.exams.l3_application import ExamResult
from app.verification.exams.l5_composition import CompositionResult

__all__ = ["UnderstandingScore", "aggregate", "composition_to_result"]

_GRADED = ("passed", "failed")


@dataclass
class UnderstandingScore:
    total: int
    passed: int
    failed: int
    skipped: int
    no_data: int
    graded: int  # passed + failed (paydanın tamamı)
    pass_rate: float | None  # passed/graded (0-1); graded=0 ise None
    status: str  # "scored" | "insufficient_data"
    by_level: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def composition_to_result(comp: CompositionResult) -> ExamResult:
    """L5 CompositionResult'ı ortak ExamResult biçimine indirger.

    aday → passed; backtest 'veri yok' yüzünden reddedildiyse → skipped
    (test edilemedi); aksi halde substantif red → failed.
    """
    if comp.candidate:
        status = "passed"
    else:
        non_backtest_ok = all(g.passed for g in comp.gates if g.gate != "backtest")
        backtest_untested = any(
            g.gate == "backtest" and not g.passed and any("veri yok" in d for d in g.details)
            for g in comp.gates
        )
        status = "skipped" if (non_backtest_ok and backtest_untested) else "failed"
    return ExamResult(
        level="L5",
        name=comp.name,
        passed=comp.candidate,
        status=status,
        seed=0,
        detail={"gates": [g.gate for g in comp.gates if not g.passed]},
    )


def aggregate(results: list[ExamResult]) -> UnderstandingScore:
    by_level: dict[str, dict[str, int]] = {}
    counts = {"passed": 0, "failed": 0, "skipped": 0, "no_data": 0}

    for r in results:
        status = r.status if r.status in counts else "no_data"
        counts[status] += 1
        lvl = by_level.setdefault(r.level, {"passed": 0, "failed": 0, "skipped": 0, "no_data": 0})
        lvl[status] += 1

    graded = counts["passed"] + counts["failed"]
    pass_rate = (counts["passed"] / graded) if graded > 0 else None
    return UnderstandingScore(
        total=len(results),
        passed=counts["passed"],
        failed=counts["failed"],
        skipped=counts["skipped"],
        no_data=counts["no_data"],
        graded=graded,
        pass_rate=pass_rate,
        status="scored" if graded > 0 else "insufficient_data",
        by_level=by_level,
    )
