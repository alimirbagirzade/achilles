"""Korpus geneli BM25 indeksi — Chroma'dan lazy kurulur, chunk sayısına göre cache'lenir.

Hibrit retrieval (Faz A3) için: dense (semantik) aday havuzunu keyword (BM25)
eşleşmeleriyle genişletir. `BM25Index` yazılıydı ama hiç doldurulmuyordu; bu modül
onu ingestion'a dokunmadan canlı yola alır (Chroma zaten tüm chunk metnini tutar).

Cache, koleksiyon chunk sayısı değişince yeniden kurulur (yeni makale eklenince).
Chroma boş/erişilemezse `(None, {})` döner → çağıran dense-only'e geçer (graceful).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.memory.bm25_index import BM25Index
from app.memory.retrieval_service import RetrievedChunk

if TYPE_CHECKING:
    from app.memory.chroma_store import ChromaStore
    from app.memory.sqlite_store import SqliteStore

# Modül düzeyi cache (process ömrü). Anahtar: chunk sayısı.
_cache: dict[str, object] = {"count": -1, "bm25": None, "chunks": {}}

# Modül düzeyi paylaşılan SqliteStore (cache; her çağrıda yeni store yaratma).
_shared_store: SqliteStore | None = None


def _corpus_store() -> SqliteStore:
    global _shared_store
    if _shared_store is None:
        from app.memory.sqlite_store import SqliteStore

        _shared_store = SqliteStore()
    return _shared_store


def get_corpus_bm25(
    chroma: ChromaStore | None = None,
    store: SqliteStore | None = None,
) -> tuple[BM25Index | None, dict[str, RetrievedChunk]]:
    """Korpus BM25 indeksi + chunk_id→RetrievedChunk haritası döndür (cache'li).

    KAYNAK = SQLite (Chunk tablosu), Chroma DEĞİL. Önceki Chroma `get_all()` 91k id'yi
    bulk okur, eşzamanlı erişimde (öğrenme döngüsü/MCP/serving) SQLite-kilidine takılır ve
    BM25'i SESSİZCE öldürürdü (chunks=0 → hibrit dense-only'e düşer; Kural 7'ye aykırı sessiz
    çökme). SQLite WAL eşzamanlı-okumayı sorunsuz kaldırır → BM25 buradan kurulur (dayanıklı).
    `chroma` parametresi geriye-uyum için KORUNUR ama YOK SAYILIR. `store` test enjeksiyonu.

    Returns:
        (bm25, chunks). Korpus boş/erişilemezse (None, {}).
    """
    del chroma  # geriye-uyum imzası; kaynak artık SQLite
    st = store or _corpus_store()
    try:
        rows = st.list_all_chunks()
    except Exception:
        return None, {}
    count = len(rows)
    if count == 0:
        return None, {}

    if _cache["count"] != count:
        titles = {p.paper_id: p.title for p in st.list_papers()}
        bm25 = BM25Index()
        chunks: dict[str, RetrievedChunk] = {}
        for ch in rows:
            doc = ch.text or ""
            if not doc:
                continue
            bm25.add_document(ch.chunk_id, doc)
            chunks[ch.chunk_id] = RetrievedChunk(
                chunk_id=ch.chunk_id,
                paper_id=ch.paper_id,
                text=doc,
                page_number=ch.page_number,
                section_name=ch.section_name or None,
                title=titles.get(ch.paper_id),
                distance=None,  # BM25 kaynaklı; reranker semantiği nötr (0.5) sayar
            )
        _cache.update(count=count, bm25=bm25, chunks=chunks)

    return _cache["bm25"], _cache["chunks"]  # type: ignore[return-value]


def reset_cache() -> None:
    """Cache'i sıfırla (test izolasyonu / yeniden ingest sonrası)."""
    global _shared_store
    _cache.update(count=-1, bm25=None, chunks={})
    _shared_store = None
