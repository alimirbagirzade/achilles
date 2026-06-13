"""Hibrit retrieval (Faz A3) testleri — BM25 korpus + RerankingRetriever hybrid.

Çevrimdışı: sahte Chroma + stub base. Chroma/Ollama gerektirmez.
"""

from __future__ import annotations

from app.memory.bm25_corpus import get_corpus_bm25, reset_cache
from app.memory.bm25_index import BM25Index
from app.memory.reranker import Reranker
from app.memory.reranking_retriever import RerankingRetriever
from app.memory.retrieval_service import RetrievedChunk


def _chunk(cid: str, text: str, distance: float | None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=cid,
        paper_id="p",
        text=text,
        page_number=1,
        section_name="results",
        title="T",
        distance=distance,
    )


class _FakeChroma:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def count(self) -> int:
        return len(self._rows)

    def get_all(self) -> list[dict]:
        return self._rows


class _StubBase:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        return list(self._chunks)


# --------------------------------------------------------------- bm25_corpus
def test_get_corpus_bm25_builds_and_searches() -> None:
    reset_cache()
    rows = [
        {
            "chunk_id": "p_c0",
            "document": "ATR average true range volatility",
            "metadata": {"paper_id": "p"},
        },
        {
            "chunk_id": "p_c1",
            "document": "Sharpe ratio risk adjusted return",
            "metadata": {"paper_id": "p"},
        },
    ]
    bm25, chunks = get_corpus_bm25(chroma=_FakeChroma(rows))
    assert bm25 is not None
    assert len(chunks) == 2
    hits = bm25.search("Sharpe ratio", top_k=2)
    assert hits and hits[0][0] == "p_c1"
    assert chunks["p_c1"].text.startswith("Sharpe")
    reset_cache()


def test_get_corpus_bm25_empty_returns_none() -> None:
    reset_cache()
    bm25, chunks = get_corpus_bm25(chroma=_FakeChroma([]))
    assert bm25 is None
    assert chunks == {}


# --------------------------------------------------- RerankingRetriever hybrid
def test_hybrid_adds_bm25_keyword_candidate(monkeypatch) -> None:
    # Dense yalnız 'momentum' chunk'ı döner; BM25 korpusunda 'ATR' chunk'ı var ama
    # dense kaçırmış → hibrit onu eklemeli.
    dense = [_chunk("p_c0", "momentum persistence in returns", 0.2)]
    bm25 = BM25Index()
    bm25.add_document("p_c9", "ATR average true range filter for volatility")
    chunk_map = {"p_c9": _chunk("p_c9", "ATR average true range filter for volatility", None)}
    monkeypatch.setattr(
        "app.memory.bm25_corpus.get_corpus_bm25", lambda chroma=None: (bm25, chunk_map)
    )

    rr = RerankingRetriever(base=_StubBase(dense), reranker=Reranker(), enabled=True, hybrid=True)
    out = rr.retrieve("ATR filter", top_k=5)

    assert "p_c9" in {c.chunk_id for c in out}  # keyword adayı dahil edildi


def test_hybrid_graceful_when_corpus_empty(monkeypatch) -> None:
    dense = [_chunk("p_c0", "x momentum y", 0.2)]
    monkeypatch.setattr("app.memory.bm25_corpus.get_corpus_bm25", lambda chroma=None: (None, {}))
    rr = RerankingRetriever(base=_StubBase(dense), reranker=Reranker(), enabled=True, hybrid=True)
    out = rr.retrieve("ATR", top_k=5)
    assert [c.chunk_id for c in out] == ["p_c0"]  # dense-only'e düşer


def test_hybrid_off_skips_bm25(monkeypatch) -> None:
    called = {"n": 0}

    def _spy(chroma=None):
        called["n"] += 1
        return None, {}

    monkeypatch.setattr("app.memory.bm25_corpus.get_corpus_bm25", _spy)
    rr = RerankingRetriever(
        base=_StubBase([_chunk("p_c0", "momentum", 0.2)]),
        reranker=Reranker(),
        enabled=True,
        hybrid=False,
    )
    rr.retrieve("ATR", top_k=5)
    assert called["n"] == 0  # hybrid kapalı → BM25'e hiç gidilmez
