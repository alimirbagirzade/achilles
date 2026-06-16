"""UnderstandingScore testleri — objektif geçme-oranı; skipped/no_data paydaya girmez."""

from __future__ import annotations

from app.verification.exams.l3_application import ExamResult
from app.verification.exams.l5_composition import CompositionResult, GateResult
from app.verification.exams.understanding_score import (
    aggregate,
    composition_to_result,
)


def _r(level: str, status: str) -> ExamResult:
    return ExamResult(level=level, name="x", passed=(status == "passed"), status=status, seed=0)


def test_pass_rate_skipped_haric() -> None:
    results = [
        _r("L3", "passed"),
        _r("L3", "passed"),
        _r("L3", "failed"),
        _r("L4", "skipped"),  # paydaya girmez
        _r("L4", "no_data"),  # paydaya girmez
    ]
    score = aggregate(results)
    assert score.total == 5
    assert score.passed == 2
    assert score.failed == 1
    assert score.skipped == 1
    assert score.no_data == 1
    assert score.graded == 3
    assert abs(score.pass_rate - 2 / 3) < 1e-9
    assert score.status == "scored"


def test_hic_notlanan_yoksa_insufficient() -> None:
    score = aggregate([_r("L3", "skipped"), _r("L4", "skipped")])
    assert score.pass_rate is None
    assert score.status == "insufficient_data"
    assert score.graded == 0


def test_by_level_kirilimi() -> None:
    score = aggregate([_r("L3", "passed"), _r("L4", "failed"), _r("L4", "passed")])
    assert score.by_level["L3"]["passed"] == 1
    assert score.by_level["L4"]["failed"] == 1
    assert score.by_level["L4"]["passed"] == 1


def test_composition_aday_passed() -> None:
    comp = CompositionResult(
        name="rte",
        candidate=True,
        verdict="candidate",
        gates=[
            GateResult("math", True),
            GateResult("novelty", True),
            GateResult("backtest", True),
        ],
    )
    assert composition_to_result(comp).status == "passed"


def test_composition_veri_yok_skipped() -> None:
    comp = CompositionResult(
        name="rte",
        candidate=False,
        verdict="rejected",
        gates=[
            GateResult("math", True),
            GateResult("novelty", True),
            GateResult("backtest", False, ["veri yok — backtest sertifikalanamadı (aday değil)"]),
        ],
    )
    # math+novelty geçti ama test edilemedi → skipped (paydaya girmez)
    assert composition_to_result(comp).status == "skipped"


def test_composition_substantif_red_failed() -> None:
    comp = CompositionResult(
        name="kotu",
        candidate=False,
        verdict="rejected",
        gates=[
            GateResult("math", False, ["RSI kuralı aralık dışı"]),
            GateResult("novelty", True),
            GateResult("backtest", False, ["matematik kapısı geçilmedi — backtest atlandı"]),
        ],
    )
    assert composition_to_result(comp).status == "failed"
