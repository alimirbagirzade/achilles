"""RLM Controller tests (offline).

Stub retriever + stub LLM enjekte edilir → orkestrasyon mantığı Ollama olmadan
doğrulanır. Mutlak kurallar denetlenir: eksik kaynakta uydurma yok (kural 7),
desteklenmeyen iddia nihai cevaba girmez (kural 4), trading uyarısı zorunlu (kural 1).
"""

from __future__ import annotations

from app.brain.local_llm import LLMUnavailable
from app.memory.retrieval_service import RetrievedChunk
from app.rlm.claim_extractor import extract_claims
from app.rlm.evidence_builder import EvidenceSufficiencyScorer
from app.rlm.rlm_controller import RlmController
from app.rlm.rlm_store import RlmStore
from app.rlm.task_classifier import TaskClassifier
from app.verification.grounding_verifier import GroundingLevel, GroundingResult


# --------------------------------------------------------------------------
# Stubs
# --------------------------------------------------------------------------
def _chunk(i: int, *, text: str | None = None, section: str = "Results") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"paper_x::c{i:04d}",
        paper_id="paper_x",
        text=text or f"Volatilite kümelenmesi momentum kalıcılığını etkiler ({i}).",
        page_number=i + 1,
        section_name=section,
        title="Vol Clustering & Momentum",
        distance=0.1 * i,
    )


class _StubRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        return list(self._chunks)


class _StubLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def active_backend(self) -> str:
        return "stub"

    def generate(self, prompt: str, *, system: str | None = None, **_: object) -> str:
        return self.response


class _UnavailableLLM:
    def active_backend(self) -> str:
        return "stub"

    def generate(self, prompt: str, *, system: str | None = None, **_: object) -> str:
        raise LLMUnavailable("ollama down")


# Taslak: chunk kelime dağarcığını yeniden kullanır → grounding SUPPORTED bulur.
_GOOD_DRAFT = (
    "Volatilite kümelenmesi momentum kalıcılığını güçlü biçimde etkiler [paper_x:paper_x::c0000]."
)


# --------------------------------------------------------------------------
# TaskClassifier
# --------------------------------------------------------------------------
def test_task_classifier_is_deterministic_and_rule_based():
    tc = TaskClassifier()
    assert tc.classify("İki makale çelişiyor mu?") == "contradiction_check"
    assert tc.classify("Bu formülün değişkenleri nedir?") == "formula_explanation"
    assert tc.classify("Makaleleri karşılaştır ve sentezle") == "multi_paper_synthesis"
    assert tc.classify("Momentum stratejisi sinyali nasıl?") == "trading_reasoning"
    assert tc.classify("Bu makalenin ana metodolojisi?", ["p1"]) == "single_paper_analysis"
    assert tc.classify("Genel bir soru") == "general_paper_question"
    # aynı girdi → aynı çıktı
    assert tc.classify("Momentum stratejisi sinyali nasıl?") == "trading_reasoning"


def test_trading_plan_allows_hypothesis_but_never_live_signal():
    tc = TaskClassifier()
    plan = tc.plan("trading_reasoning")
    assert plan.allow_trading_hypothesis is True
    assert plan.allow_trading_signal is False


# --------------------------------------------------------------------------
# EvidenceSufficiencyScorer
# --------------------------------------------------------------------------
def test_evidence_zero_when_no_chunks():
    rep = EvidenceSufficiencyScorer().score("soru", [])
    assert rep.score == 0.0
    assert rep.decision == "insufficient"


def test_evidence_increases_with_chunks():
    scorer = EvidenceSufficiencyScorer()
    few = scorer.score("momentum volatilite", [_chunk(0)])
    many = scorer.score("momentum volatilite", [_chunk(i) for i in range(6)])
    assert many.score > few.score
    assert 0.0 <= many.score <= 100.0


# --------------------------------------------------------------------------
# claim_extractor
# --------------------------------------------------------------------------
def test_claim_extractor_maps_levels_and_drops_unsupported():
    groundings = [
        GroundingResult("desteklenen iddia", GroundingLevel.SUPPORTED, "c1"),
        GroundingResult("desteksiz iddia", GroundingLevel.UNSUPPORTED, None),
    ]
    claims = extract_claims(groundings)
    supported = [c for c in claims if c.is_supported]
    assert len(supported) == 1
    assert supported[0].support_status == "supported"
    assert claims[1].support_status == "unsupported"
    assert claims[1].is_supported is False


# --------------------------------------------------------------------------
# RlmController — uçtan uca (offline)
# --------------------------------------------------------------------------
def test_insufficient_evidence_abstains_no_hallucination():
    ctrl = RlmController(retriever=_StubRetriever([]), llm=_StubLLM(_GOOD_DRAFT))
    res = ctrl.answer("Bilinmeyen konu?", write_report=False)
    assert res.status == "abstained"
    assert res.evidence_score == 0.0
    assert "yeterli kaynak yok" in res.final_answer.lower()
    assert res.supported_claims == []


def test_answer_with_sources_produces_grounded_envelope():
    chunks = [_chunk(i) for i in range(3)]
    ctrl = RlmController(retriever=_StubRetriever(chunks), llm=_StubLLM(_GOOD_DRAFT))
    res = ctrl.answer("Momentum kalıcı mı?", write_report=False)

    assert res.status in ("answered", "answered_with_limitation")
    assert res.supported_claims  # en az bir desteklenen iddia
    assert "Kaynak dayanakları" in res.final_answer
    assert "paper_x" in res.final_answer
    # run kalıcı olarak loglandı
    runs = RlmStore().list_runs(limit=5)
    assert any(r["run_id"] == res.run_id for r in runs)


def test_no_llm_path_returns_retrieval_only_without_claims():
    chunks = [_chunk(i) for i in range(3)]
    ctrl = RlmController(retriever=_StubRetriever(chunks), llm=_UnavailableLLM())
    res = ctrl.answer("Momentum kalıcı mı?", write_report=False)

    assert res.status == "no_llm"
    assert res.supported_claims == []
    assert "LLM çevrimdışı" in res.final_answer
    assert "paper_x" in res.final_answer  # kaynaklar yine de gösterilir


def test_trading_answer_always_carries_disclaimer():
    chunks = [
        _chunk(
            i,
            text=(
                "Momentum stratejisi volatilite rejiminde getiri üretir; "
                "backtest sonuçları kalıcılığı gösterir."
            ),
        )
        for i in range(3)
    ]
    draft = (
        "Momentum stratejisi volatilite rejiminde getiri üretir ve kalıcılığı "
        "gösterir [paper_x:paper_x::c0000]."
    )
    ctrl = RlmController(retriever=_StubRetriever(chunks), llm=_StubLLM(draft))
    res = ctrl.answer("Momentum trading stratejisi sinyali güçlü mü?", write_report=False)

    assert res.task_type == "trading_reasoning"
    if res.status in ("answered", "answered_with_limitation"):
        assert "yatırım tavsiyesi değildir" in res.final_answer
        assert "canlı sinyal değildir" in res.final_answer
