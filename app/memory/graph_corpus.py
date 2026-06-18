"""Korpus geneli term–chunk grafı — Chroma'dan lazy kurulur, chunk sayısına göre cache'lenir.

`graph_retriever` (SPRIG-lite PPR) için korpus grafını sağlar. `bm25_corpus` ile aynı deseni
izler: Chroma tüm chunk metnini tuttuğundan graf ingestion'a dokunmadan canlı yola alınır;
koleksiyon chunk sayısı değişince (yeni makale) cache yeniden kurulur. Chroma boş/erişilemezse
`(None, {})` döner → çağıran dense-only'e geçer (graceful).
"""

from __future__ import annotations

from app.memory.chroma_store import ChromaStore
from app.memory.graph_retriever import TermChunkGraph, build_graph
from app.memory.retrieval_service import RetrievedChunk

# Modül düzeyi cache (process ömrü). Anahtar: chunk sayısı.
_cache: dict[str, object] = {"count": -1, "graph": None, "chunks": {}}


def get_corpus_graph(
    chroma: ChromaStore | None = None,
) -> tuple[TermChunkGraph | None, dict[str, RetrievedChunk]]:
    """Korpus term–chunk grafı + chunk_id→RetrievedChunk haritası döndür (cache'li).

    Returns:
        (graph, chunks). Korpus boş/erişilemezse (None, {}).
    """
    chroma = chroma or ChromaStore()
    try:
        count = chroma.count()
    except Exception:
        return None, {}
    if count == 0:
        return None, {}

    if _cache["count"] != count:
        texts: dict[str, str] = {}
        chunks: dict[str, RetrievedChunk] = {}
        try:
            rows = chroma.get_all()
        except Exception:
            return None, {}
        for row in rows:
            cid = row["chunk_id"]
            doc = row.get("document", "") or ""
            meta = row.get("metadata", {}) or {}
            if not doc:
                continue
            texts[cid] = doc
            chunks[cid] = RetrievedChunk(
                chunk_id=cid,
                paper_id=meta.get("paper_id", "?"),
                text=doc,
                page_number=meta.get("page_number"),
                section_name=meta.get("section_name") or None,
                title=meta.get("title") or None,
                distance=None,  # graf kaynaklı; reranker semantiği nötr sayar
            )
        _cache.update(count=count, graph=build_graph(texts), chunks=chunks)

    return _cache["graph"], _cache["chunks"]  # type: ignore[return-value]


def reset_cache() -> None:
    """Cache'i sıfırla (test izolasyonu / yeniden ingest sonrası)."""
    _cache.update(count=-1, graph=None, chunks={})
