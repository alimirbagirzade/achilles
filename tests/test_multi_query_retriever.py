"""MultiQueryRetriever testleri — deduplication ve birleştirme."""

from __future__ import annotations

from app.brain.multi_query_retriever import MultiQueryRetriever
from app.brain.query_expander import QueryExpander
from app.memory.retrieval_service import RetrievedChunk


class FakeRetrievalService:
    """Test için sahte RetrievalService; önceden tanımlı chunk listesi döndürür."""

    def __init__(self, chunks_per_query: dict[str, list[RetrievedChunk]] | None = None) -> None:
        self._chunks = chunks_per_query or {}
        self._default: list[RetrievedChunk] = []

    def set_default(self, chunks: list[RetrievedChunk]) -> None:
        self._default = chunks

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        return self._chunks.get(query, self._default)[:top_k]


def _make_chunk(chunk_id: str, distance: float = 0.3) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        paper_id=chunk_id.split("_c")[0] if "_c" in chunk_id else "paper1",
        text=f"Chunk content for {chunk_id}",
        page_number=1,
        section_name="introduction",
        title="Test Paper",
        distance=distance,
    )


def test_deduplication() -> None:
    """Aynı chunk iki farklı sorgudan gelirse sonuçta bir kez görünmeli."""
    shared_chunk = _make_chunk("paper1_c0001", distance=0.1)
    unique_chunk_a = _make_chunk("paper1_c0002", distance=0.2)
    unique_chunk_b = _make_chunk("paper1_c0003", distance=0.3)

    fake = FakeRetrievalService()
    fake.set_default([shared_chunk, unique_chunk_a, unique_chunk_b])

    expander = QueryExpander()
    retriever = MultiQueryRetriever(retriever=fake, expander=expander)

    results = retriever.retrieve("momentum strategy", top_k=10)
    chunk_ids = [c.chunk_id for c in results]

    # Her chunk_id yalnızca bir kez görünmeli
    assert len(chunk_ids) == len(set(chunk_ids)), f"Tekrar eden chunk'lar var: {chunk_ids}"


def test_best_score_kept() -> None:
    """Aynı chunk iki sorgudan gelirse en düşük distance (en yüksek skor) korunmalı."""
    chunk_good = _make_chunk("paper1_c0001", distance=0.1)
    chunk_bad = _make_chunk("paper1_c0001", distance=0.8)  # Aynı chunk_id, kötü skor

    fake = FakeRetrievalService(
        chunks_per_query={
            "volatility": [chunk_good],
            "vol": [chunk_bad],
        }
    )

    class FixedExpander:
        def expand(self, query: str) -> list[str]:
            return ["volatility", "vol"]

    retriever = MultiQueryRetriever(retriever=fake, expander=FixedExpander())
    results = retriever.retrieve("volatility", top_k=5)

    assert len(results) == 1
    # En iyi skor seçilmeli
    assert results[0].chunk_id == "paper1_c0001"
    assert results[0].distance == 0.1


def test_retrieval_returns_top_k() -> None:
    """top_k parametresi sonuç sayısını sınırlamalı."""
    chunks = [_make_chunk(f"paper1_c{i:04d}", distance=i * 0.1) for i in range(10)]

    fake = FakeRetrievalService()
    fake.set_default(chunks)

    expander = QueryExpander()
    retriever = MultiQueryRetriever(retriever=fake, expander=expander)

    results = retriever.retrieve("test query", top_k=3)
    assert len(results) <= 3
