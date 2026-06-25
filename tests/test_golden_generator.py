"""Golden-set üreticisi testleri — decontamination DETERMİNİSTİK (LLM'siz tam test).

generate_golden_questions LLM kullanır → sahte LLM ile sızıntı-filtresi + format doğrulanır.
"""

from __future__ import annotations

from app.evals.golden_generator import (
    _clean_question,
    generate_golden_questions,
    has_excessive_overlap,
)
from app.memory.retrieval_service import RetrievedChunk

_SRC = (
    "Volatility clustering means that large price changes tend to be followed by large "
    "changes and small changes by small changes, a hallmark of GARCH-type conditional "
    "heteroskedasticity in financial return series over time."
)


def _chunk(cid: str, text: str = _SRC, pid: str = "p1") -> RetrievedChunk:
    return RetrievedChunk(cid, pid, text, 1, "Methods", "T", 0.3)


# ---- has_excessive_overlap ----
def test_overlap_flags_copied_phrase() -> None:
    # 5+ kelimelik birebir kopya → sızıntılı
    q = "What does large price changes tend to be followed by large changes mean?"
    assert has_excessive_overlap(q, _SRC, n=5, max_hits=1) is True


def test_overlap_clean_paraphrase() -> None:
    q = "Why do turbulent market periods cluster together according to this passage?"
    assert has_excessive_overlap(q, _SRC, n=5, max_hits=1) is False


def test_overlap_short_question_not_flagged() -> None:
    assert has_excessive_overlap("Why?", _SRC, n=5) is False


# ---- _clean_question ----
def test_clean_question_strips_prefix_and_quotes() -> None:
    assert _clean_question('Soru: "Neden volatilite kümelenir?"') == "Neden volatilite kümelenir?"
    assert _clean_question("Question: what is GARCH?\nextra line") == "what is GARCH?"


# ---- generate_golden_questions (sahte LLM) ----
class _StubLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.calls = 0

    def generate(self, prompt: str, **kw: object) -> str:
        self.calls += 1
        return self._reply


def test_generate_keeps_clean_question() -> None:
    llm = _StubLLM("Why do turbulent market periods cluster according to this study?")
    qs = generate_golden_questions([_chunk("c1")], llm)
    assert len(qs) == 1
    assert qs[0].expected_chunk_ids == ["c1"]
    assert qs[0].expected_source_ids == ["p1"]
    assert "?" in qs[0].question_text


def test_generate_drops_leaky_question() -> None:
    # LLM pasajı kopyalarsa → decontaminate eler
    leaky = "Is it true that large price changes tend to be followed by large changes?"
    qs = generate_golden_questions([_chunk("c1")], _StubLLM(leaky))
    assert qs == []


def test_generate_drops_empty_and_non_question() -> None:
    assert generate_golden_questions([_chunk("c1")], _StubLLM("")) == []
    assert generate_golden_questions([_chunk("c1")], _StubLLM("bir ifade nokta")) == []


def test_generate_skips_short_chunk() -> None:
    short = _chunk("c1", text="kısa")
    assert generate_golden_questions([short], _StubLLM("Geçerli bir soru mu?")) == []
