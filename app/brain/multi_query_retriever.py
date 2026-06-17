"""Multi-query retrieval — merged results across expanded queries.

Runs a separate retrieval for each expanded query, then fuses the per-query ranked
lists with Reciprocal Rank Fusion (RRF) instead of a naive best-score dedup. RRF,
skor kalibrasyonu gerektirmeden birden çok sorgu varyantında üst sıralarda çıkan
chunk'ları ödüllendirir → tek varyantın domine etmesini engeller (daha sağlam füzyon).
"""

from __future__ import annotations

from app.brain.query_expander import QueryExpander
from app.memory.rank_fusion import DEFAULT_RRF_K, fuse_ranked
from app.memory.retrieval_service import RetrievalService, RetrievedChunk


class MultiQueryRetriever:
    """Genişletilmiş sorgular üzerinden RRF ile birleştirilmiş retrieval.

    Retrieval Service ile QueryExpander'ı birleştirir: her sorgu varyantı için ayrı
    retrieval yapılır, ardından varyant-başı sıralı listeler Reciprocal Rank Fusion
    (RRF) ile birleştirilir. Aynı chunk birden çok varyanttan gelirse görüntü için
    **en iyi (en düşük distance) varyantı** saklanır; sıralama RRF skoruna göredir.
    """

    def __init__(
        self,
        retriever: RetrievalService,
        expander: QueryExpander | None = None,
    ) -> None:
        self._retriever = retriever
        self._expander = expander or QueryExpander()

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Genişletilmiş sorgu listesi üzerinden RRF ile birleştirilmiş chunk listesi.

        Args:
            query: Orijinal kullanıcı sorgusu.
            top_k: Son listede kaç chunk döneceği.

        Returns:
            RRF skoruna göre azalan, tekilleştirilmiş RetrievedChunk listesi (en fazla
            ``top_k``). Eşit skorda chunk_id'ye göre kararlı (deterministik) sıralanır.
        """
        expanded = self._expander.expand(query)

        ranked_lists: list[list[str]] = []
        chunk_by_id: dict[str, RetrievedChunk] = {}

        for q in expanded:
            try:
                chunks = self._retriever.retrieve(q, top_k=top_k)
            except Exception:
                # Bir sorgu başarısız olursa diğerlerine devam et
                continue

            ids: list[str] = []
            for chunk in chunks:
                cid = chunk.chunk_id
                prev = chunk_by_id.get(cid)
                # Görüntü için en iyi (en düşük distance) varyantı sakla; sıralama RRF'le.
                # distance==0.0 falsy → `or 1.0` onu en kötü sayardı; açık None kontrolü.
                cur_d = chunk.distance if chunk.distance is not None else 1.0
                prev_d = prev.distance if prev is not None and prev.distance is not None else 1.0
                if prev is None or cur_d < prev_d:
                    chunk_by_id[cid] = chunk
                ids.append(cid)
            if ids:
                ranked_lists.append(ids)

        fused_ids = fuse_ranked(ranked_lists, k=DEFAULT_RRF_K)
        return [chunk_by_id[cid] for cid in fused_ids[:top_k] if cid in chunk_by_id]
