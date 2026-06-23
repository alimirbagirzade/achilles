"""RLM Controller tests (offline).

Stub retriever + stub LLM enjekte edilir → orkestrasyon mantığı Ollama olmadan
doğrulanır. Mutlak kurallar denetlenir: eksik kaynakta uydurma yok (kural 7),
desteklenmeyen iddia nihai cevaba girmez (kural 4), trading uyarısı zorunlu (kural 1).
"""

from __future__ import annotations

import pytest

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
    # KOŞULSUZ: status ne olursa olsun trading-içerikli çıktı uyarı taşımalı (kural 1).
    assert "yatırım tavsiyesi değildir" in res.final_answer
    assert "canlı sinyal değildir" in res.final_answer


def test_trading_disclaimer_survives_classifier_misroute():
    """Classifier trading sorusunu MATH/UNCERTAINTY'ye düşürse bile uyarı kaçmamalı.

    Kural 1 yaptırımı içerik-tabanlı (_apply_trading_guard) — görev tipinden bağımsız.
    """
    chunks = [
        _chunk(i, text="Momentum stratejisi Sharpe oranı backtest getiri volatilite rejimi.")
        for i in range(3)
    ]
    draft = "Momentum stratejisi yüksek Sharpe üretir [paper_x:paper_x::c0000]."
    ctrl = RlmController(retriever=_StubRetriever(chunks), llm=_StubLLM(draft))

    # "Sharpe ... hesapla" → MATH; "güvenilir mi" → UNCERTAINTY (ikisi de TRADING değil)
    for q in (
        "Bu momentum stratejisinin Sharpe oranını hesapla",
        "Bu al-sat stratejisi güvenilir mi",
    ):
        res = ctrl.answer(q, write_report=False)
        assert res.task_type != "trading_reasoning"  # bilerek başka tipe düşüyor
        assert "yatırım tavsiyesi değildir" in res.final_answer, f"uyarı kaçtı: {q}"
        assert "canlı sinyal değildir" in res.final_answer


def test_unsupported_claim_not_in_final_answer():
    """Kural 4: desteklenmeyen iddia nihai cevaba GİRMEZ (uçtan uca controller testi)."""
    chunks = [_chunk(i) for i in range(3)]
    # 1 destekli (chunk kelimeleriyle örtüşür) + 1 tamamen alakasız (sıfır örtüşme) cümle.
    draft = (
        "Volatilite kümelenmesi momentum kalıcılığını etkiler [paper_x:paper_x::c0000]. "
        "Kuantum bilgisayarlar kripto madenciliğini tamamen değiştirecektir."
    )
    ctrl = RlmController(retriever=_StubRetriever(chunks), llm=_StubLLM(draft))
    res = ctrl.answer("Momentum kalıcı mı?", write_report=False)

    assert res.status in ("answered", "answered_with_limitation")
    assert "kuantum" not in res.final_answer.lower()  # desteksiz cümle çıkarıldı
    assert any("kuantum" in c.lower() for c in res.unsupported_claims)


def test_abstained_status_not_high_confidence():
    """Çekimser kalınan çıktı yüksek güven rozeti taşımamalı (tutarlı metadata)."""
    chunks = [_chunk(i) for i in range(3)]
    # Atıfsız + chunk'larla örtüşmeyen taslak → tüm iddialar UNSUPPORTED → abstain.
    draft = "Kuantum bilgisayarlar kripto madenciliğini tamamen değiştirecektir."
    ctrl = RlmController(retriever=_StubRetriever(chunks), llm=_StubLLM(draft))
    res = ctrl.answer("Bilinmeyen bir konu hakkında?", write_report=False)

    assert res.status == "abstained"
    assert res.confidence_level == "Low"  # decision 'answer' olsa bile abstain'de Low
    assert res.final_confidence == 0.0  # çekimserde cevaba güven yok (etiket+sayı tutarlı)


def test_non_trading_answer_has_no_disclaimer():
    """Trading-dışı içerikli cevap yatırım uyarısı TAŞIMAMALI (aşırı-tetikleme regresyonu).

    'return' gibi jenerik kelimeler guard'dan çıkarıldı → akademik (ör. Bayes) cevap
    yanlış-bağlam uyarı taşımaz; uyarı yalnız gerçek trading/sinyal içeriğinde görünür.
    """
    chunks = [
        RetrievedChunk(
            chunk_id=f"p::c{i:04d}",
            paper_id="p",
            text="Bayes teoremi koşullu olasılığı önsel ve olabilirlik çarpımıyla günceller.",
            page_number=i + 1,
            section_name="Methods",
            title="Bayesian Inference Primer",
            distance=0.1 * i,
        )
        for i in range(3)
    ]
    draft = "Bayes teoremi koşullu olasılığı önsel ve olabilirlik ile günceller [p:p::c0000]."
    ctrl = RlmController(retriever=_StubRetriever(chunks), llm=_StubLLM(draft))
    res = ctrl.answer("Bayes teoremi nasıl çalışır?", write_report=False)

    assert res.status in ("answered", "answered_with_limitation")
    assert "yatırım tavsiyesi değildir" not in res.final_answer  # trading-dışı → uyarı yok


def test_controller_is_deterministic_for_same_input():
    """Kural 6: aynı girdi → aynı sınıflandırma/durum/cevap (stub LLM deterministik)."""
    chunks = [_chunk(i) for i in range(3)]
    a = RlmController(retriever=_StubRetriever(chunks), llm=_StubLLM(_GOOD_DRAFT)).answer(
        "Momentum kalıcı mı?", write_report=False
    )
    b = RlmController(retriever=_StubRetriever(chunks), llm=_StubLLM(_GOOD_DRAFT)).answer(
        "Momentum kalıcı mı?", write_report=False
    )
    assert a.task_type == b.task_type
    assert a.status == b.status
    assert a.evidence_score == b.evidence_score
    assert a.final_answer == b.final_answer


class _RecordingLLM:
    """generate() çağrısının kwarg'larını kaydeden stub."""

    def __init__(self) -> None:
        self.kwargs: dict = {}

    def active_backend(self) -> str:
        return "stub"

    def generate(self, prompt: str, **kwargs: object) -> str:
        self.kwargs = kwargs
        return _GOOD_DRAFT


def test_draft_llm_call_is_bounded():
    """Taslak LLM çağrısı max_tokens + timeout ile SINIRLI olmalı (yavaş CPU'da asılı kalmasın).

    Determinizm (seed) da iletilmeli.
    """
    chunks = [_chunk(i) for i in range(3)]
    llm = _RecordingLLM()
    RlmController(retriever=_StubRetriever(chunks), llm=llm, store=RlmStore()).answer(
        "Momentum kalıcı mı?", write_report=False
    )
    assert llm.kwargs.get("max_tokens") and 0 < llm.kwargs["max_tokens"] <= 2000
    assert llm.kwargs.get("timeout") and 0 < llm.kwargs["timeout"] <= 600
    assert llm.kwargs.get("seed") == 42


class _BoomRetriever:
    """Retrieval sırasında beklenmeyen hata fırlatan stub (Chroma/IO çökmesi taklidi)."""

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        raise RuntimeError("retrieval patladı")


def test_unexpected_error_marks_run_failed_not_running():
    """Beklenmeyen hata run'ı 'running' asılı BIRAKMAZ → 'failed' işaretlenir + yeniden fırlatılır.

    (Gerçek smoke testte timeout'la kesilen run sonsuza dek 'running' kalmıştı; bu kapı
    yakalanabilir hataları kapatır. Audit/rlm-runs gerçeği yansıtmalı.)
    """
    store = RlmStore()
    ctrl = RlmController(retriever=_BoomRetriever(), llm=_StubLLM(_GOOD_DRAFT), store=store)
    with pytest.raises(RuntimeError):
        ctrl.answer("Momentum kalıcı mı?", write_report=False)

    runs = store.list_runs(limit=10)
    assert any(r["status"] == "failed" for r in runs)
    assert all(r["status"] != "running" for r in runs)  # hiçbir run asılı kalmadı


def test_stale_running_run_is_reaped():
    """Dış-kill/timeout ile 'running' asılı kalan run reaper ile 'failed' olur."""
    from app.rlm.rlm_store import RlmRun

    store = RlmStore()
    with store.session() as s:
        s.add(
            RlmRun(
                run_id="rlm_staletest0001",
                user_query="q",
                task_type="general_paper_question",
                model_name="m",
                status="running",
                created_at="2000-01-01T00:00:00+00:00",  # çok eski
            )
        )
    reaped = store.mark_stale_running_failed(max_age_minutes=60)
    assert reaped >= 1
    assert store.get_run("rlm_staletest0001")["status"] == "failed"


def test_reaper_protects_fresh_running_run():
    """Genç (aktif/eşzamanlı) 'running' run reaper'dan korunur — yaş eşiği."""
    from app.rlm.rlm_store import RlmRun, _utcnow

    store = RlmStore()
    with store.session() as s:
        s.add(
            RlmRun(
                run_id="rlm_freshtest0001",
                user_query="q",
                task_type="general_paper_question",
                model_name="m",
                status="running",
                created_at=_utcnow(),  # şimdi → korunmalı
            )
        )
    store.mark_stale_running_failed(max_age_minutes=60)
    assert store.get_run("rlm_freshtest0001")["status"] == "running"  # dokunulmadı
