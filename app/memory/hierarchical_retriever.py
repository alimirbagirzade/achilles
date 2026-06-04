"""Hierarchical retrieval — enriches results with adjacent chunks and section context.

Augments initial retrieval results with previous/next chunks and other chunks
from the same section for broader context coverage.
"""

from __future__ import annotations

from app.memory.retrieval_service import RetrievalService, RetrievedChunk


class HierarchicalRetriever:
    """Hiyerarşik retrieval servisi.

    İlk chunk listesini alır; ardından:
    1. Her chunk için önceki/sonraki chunk'ı ekler.
    2. Aynı bölümdeki (section_name) diğer chunk'ları ekler.
    3. Sonuçları tekilleştirir.

    Komşu chunk bilgisi SqliteStore'dan veya chunk_id kuralından türetilir.
    SqliteStore verilmezse chunk_id'deki index bilgisi kullanılır.
    """

    def __init__(
        self,
        retriever: RetrievalService,
        store: object | None = None,  # SqliteStore | None
    ) -> None:
        self._retriever = retriever
        self._store = store  # opsiyonel SqliteStore

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Hiyerarşik olarak zenginleştirilmiş chunk listesi döndür.

        Args:
            query: Kullanıcı sorgusu.
            top_k: Başlangıç retrieval için chunk sayısı.

        Returns:
            Zenginleştirilmiş, tekilleştirilmiş RetrievedChunk listesi.
        """
        base_chunks = self._retriever.retrieve(query, top_k=top_k)
        if not base_chunks:
            return []

        enriched: dict[str, RetrievedChunk] = {c.chunk_id: c for c in base_chunks}

        # Komşu chunk'ları ekle (store varsa gerçek komşular, yoksa ID tahmini)
        for chunk in list(base_chunks):
            for neighbor_id in self._get_neighbor_ids(chunk):
                if neighbor_id not in enriched:
                    neighbor = self._fetch_chunk_by_id(neighbor_id, chunk)
                    if neighbor:
                        enriched[neighbor_id] = neighbor

        # Bölüm bağlamını ekle
        sections_seen: set[str] = set()
        for chunk in list(base_chunks):
            if chunk.section_name and chunk.section_name not in sections_seen:
                sections_seen.add(chunk.section_name)
                section_chunks = self._get_section_chunks(
                    chunk.paper_id, chunk.section_name, base_chunks
                )
                for sc in section_chunks:
                    if sc.chunk_id not in enriched:
                        enriched[sc.chunk_id] = sc

        # Orijinal sıralamayı koruyarak eklenenleri arkaya koy
        result = list(base_chunks)
        original_ids = {c.chunk_id for c in base_chunks}
        for cid, chunk in enriched.items():
            if cid not in original_ids:
                result.append(chunk)

        return result

    # ------------------------------------------------------------------
    # Yardımcı metodlar
    # ------------------------------------------------------------------

    def _get_neighbor_ids(self, chunk: RetrievedChunk) -> list[str]:
        """Chunk ID'sinden önceki/sonraki chunk ID'lerini tahmin et."""
        # chunk_id formatı: {paper_id}_c{index:04d}
        cid = chunk.chunk_id
        try:
            prefix, idx_str = cid.rsplit("_c", 1)
            idx = int(idx_str)
            neighbors = []
            if idx > 0:
                neighbors.append(f"{prefix}_c{idx - 1:04d}")
            neighbors.append(f"{prefix}_c{idx + 1:04d}")
            return neighbors
        except (ValueError, AttributeError):
            return []

    def _fetch_chunk_by_id(self, chunk_id: str, reference: RetrievedChunk) -> RetrievedChunk | None:
        """SqliteStore'dan veya yer tutucu olarak chunk getir."""
        if self._store is not None:
            try:
                from sqlalchemy import select

                from app.memory.sqlite_store import Chunk, SqliteStore

                store: SqliteStore = self._store  # type: ignore[assignment]
                with store.session() as session:
                    row = session.scalar(select(Chunk).where(Chunk.chunk_id == chunk_id))
                    if row:
                        return RetrievedChunk(
                            chunk_id=row.chunk_id,
                            paper_id=row.paper_id,
                            text=row.text,
                            page_number=row.page_number,
                            section_name=row.section_name,
                            title=reference.title,
                            distance=None,
                        )
            except Exception:
                pass
        return None

    def _get_section_chunks(
        self,
        paper_id: str,
        section_name: str,
        existing: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        """Aynı bölümdeki, henüz listede olmayan chunk'ları getir."""
        if self._store is None:
            return []
        try:
            from sqlalchemy import select

            from app.memory.sqlite_store import Chunk, SqliteStore

            store: SqliteStore = self._store  # type: ignore[assignment]
            existing_ids = {c.chunk_id for c in existing}
            with store.session() as session:
                rows = list(
                    session.scalars(
                        select(Chunk)
                        .where(
                            Chunk.paper_id == paper_id,
                            Chunk.section_name == section_name,
                        )
                        .limit(10)
                    )
                )
                result = []
                for row in rows:
                    if row.chunk_id not in existing_ids:
                        result.append(
                            RetrievedChunk(
                                chunk_id=row.chunk_id,
                                paper_id=row.paper_id,
                                text=row.text,
                                page_number=row.page_number,
                                section_name=row.section_name,
                                title=None,
                                distance=None,
                            )
                        )
                return result
        except Exception:
            return []
