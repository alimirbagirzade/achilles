"""Korpus geneli BM25 indeksi — Chroma'dan lazy kurulur, chunk sayısına göre cache'lenir.

Hibrit retrieval (Faz A3) için: dense (semantik) aday havuzunu keyword (BM25)
eşleşmeleriyle genişletir. `BM25Index` yazılıydı ama hiç doldurulmuyordu; bu modül
onu ingestion'a dokunmadan canlı yola alır (Chroma zaten tüm chunk metnini tutar).

Cache, koleksiyon chunk sayısı değişince yeniden kurulur (yeni makale eklenince).
Chroma boş/erişilemezse `(None, {})` döner → çağıran dense-only'e geçer (graceful).
"""

from __future__ import annotations

from app.memory.bm25_index import BM25Index
from app.memory.chroma_store import ChromaStore
from app.memory.retrieval_service import RetrievedChunk

# Modül düzeyi cache (process ömrü). Anahtar: chunk sayısı.
_cache: dict[str, object] = {"count": -1, "bm25": None, "chunks": {}}

# Modül düzeyi paylaşılan ChromaStore: get_corpus_bm25 her çağrıda YENİ ChromaStore()
# yaratıyordu → her çağrı SOĞUK koleksiyon yüklemesi (~10s count()) ödüyordu; BM25
# cache dolu olsa bile count() kontrolü her sorguda bu maliyeti tekrarlıyordu (canlı
# RAG ~18s/sorgu). Paylaşılan örnek ile count() ilk çağrıdan sonra ISINIR (~50ms).
_shared_chroma: ChromaStore | None = None


def _corpus_chroma() -> ChromaStore:
    global _shared_chroma
    if _shared_chroma is None:
        _shared_chroma = ChromaStore()
    return _shared_chroma


def get_corpus_bm25(
    chroma: ChromaStore | None = None,
) -> tuple[BM25Index | None, dict[str, RetrievedChunk]]:
    """Korpus BM25 indeksi + chunk_id→RetrievedChunk haritası döndür (cache'li).

    Returns:
        (bm25, chunks). Korpus boş/erişilemezse (None, {}).
    """
    chroma = chroma or _corpus_chroma()
    try:
        count = chroma.count()
    except Exception:
        return None, {}
    if count == 0:
        return None, {}

    if _cache["count"] != count:
        bm25 = BM25Index()
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
            bm25.add_document(cid, doc)
            chunks[cid] = RetrievedChunk(
                chunk_id=cid,
                paper_id=meta.get("paper_id", "?"),
                text=doc,
                page_number=meta.get("page_number"),
                section_name=meta.get("section_name") or None,
                title=meta.get("title") or None,
                distance=None,  # BM25 kaynaklı; reranker semantiği nötr (0.5) sayar
            )
        _cache.update(count=count, bm25=bm25, chunks=chunks)

    return _cache["bm25"], _cache["chunks"]  # type: ignore[return-value]


def reset_cache() -> None:
    """Cache'i sıfırla (test izolasyonu / yeniden ingest sonrası)."""
    global _shared_chroma
    _cache.update(count=-1, bm25=None, chunks={})
    _shared_chroma = None
