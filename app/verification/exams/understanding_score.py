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
from typing import Any, Protocol

from app.verification.exams.l3_application import ExamResult
from app.verification.exams.l5_composition import CompositionResult

__all__ = [
    "RagAnswerLike",
    "UnderstandingScore",
    "aggregate",
    "composition_to_result",
    "rag_answers_to_results",
    "score_indicator_exams",
]


class RagAnswerLike(Protocol):
    """RagExamRunner.ExamAnswer'ın yapısal arabirimi (ağır import'tan kaçınmak için)."""

    question_type: str
    requires_abstention: bool
    answer_text: str
    citation_score: float
    grounding_score: float
    abstention_correct: bool
    hallucination_detected: bool


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


def rag_answers_to_results(answers: list[RagAnswerLike]) -> list[ExamResult]:
    """RAG sınavı (citation/grounding/abstention) cevaplarını merdiven sonuçlarına çevirir.

    - abstention soruları → "Taban" (Dürüstlük): doğru çekimserlik mi.
    - diğerleri → L1 (Çıkarım/retrieval: doğru kaynağı buldu/alıntıladı mı) + L2
      (Sadakat: cevap dayanaklı mı, halüsinasyon yok mu).
    Cevap yoksa (retrieval boş) → L1/L2 'no_data' (test edilemedi, paydaya girmez).
    """
    out: list[ExamResult] = []
    for a in answers:
        no_answer = not (a.answer_text or "").strip()
        if a.requires_abstention:
            p = bool(a.abstention_correct)
            out.append(_mk("Taban", a.question_type, p, {"abstention_correct": p}))
            continue
        if no_answer:
            out.append(_mk_status("L1", a.question_type, "no_data"))
            out.append(_mk_status("L2", a.question_type, "no_data"))
            continue
        l1 = a.citation_score >= 0.3
        out.append(_mk("L1", a.question_type, l1, {"citation_score": a.citation_score}))
        l2 = a.grounding_score >= 0.4 and not a.hallucination_detected
        out.append(
            _mk(
                "L2",
                a.question_type,
                l2,
                {"grounding_score": a.grounding_score, "hallucination": a.hallucination_detected},
            )
        )
    return out


def _mk(level: str, name: str, passed: bool, detail: dict[str, Any]) -> ExamResult:
    return ExamResult(
        level=level,
        name=name,
        passed=passed,
        status="passed" if passed else "failed",
        seed=0,
        detail=detail,
    )


def _mk_status(level: str, name: str, status: str) -> ExamResult:
    return ExamResult(level=level, name=name, passed=False, status=status, seed=0, detail={})


def score_indicator_exams(seed: int = 0) -> UnderstandingScore:
    """L3+L4 sınavlarını tüm registry spec'lerinde koşar → objektif UnderstandingScore.

    Kaba öz-değerlendirme %'sinin yerine geçen objektif skor (CLI + web ortak yolu).
    LLM gerektirir; çevrimdışıysa sınavlar 'skipped' olur → graded=0 → status
    'insufficient_data' (sahte yüksek skor üretmeyiz, CLAUDE.md Kural 2).
    """
    from app.verification.exams.l3_application import ApplicationExam
    from app.verification.exams.l4_counterfactual import CounterfactualExam
    from app.verification.exams.registry import list_specs

    l3 = ApplicationExam()
    l4 = CounterfactualExam()
    results: list[ExamResult] = []
    for spec in list_specs():
        results.append(l3.run(spec, seed=seed))
        results.append(l4.run(spec, seed=seed))
    return aggregate(results)


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
