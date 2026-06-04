"""Multi-query retrieval — merged results across expanded queries.

Runs a separate retrieval for each expanded query; deduplicates by chunk_id,
keeping the highest score per chunk.
"""

from __future__ import annotations

from app.brain.query_expander import QueryExpander
from app.memory.retrieval_service import RetrievalService, RetrievedChunk


class MultiQueryRetriever:
    """Genişletilmiş sorgular üzerinden birleştirilmiş retrieval.

    Retrieval Service ile QueryExpander'ı birleştirir: her sorgu varyantı için
    ayrı retrieval yapılır, ardından sonuçlar chunk_id'ye göre tekilleştirilir
    ve skorla sıralanır.
    """

    def __init__(
        self,
        retriever: RetrievalService,
        expander: QueryExpander | None = None,
    ) -> None:
        self._retriever = retriever
        self._expander = expander or QueryExpander()

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Genişletilmiş sorgu listesi üzerinden tekilleştirilmiş chunk listesi döndür.

        Args:
            query: Orijinal kullanıcı sorgusu.
            top_k: Son listede kaç chunk döneceği.

        Returns:
            En yüksek skordan en düşüğe sıralanmış, tekilleştirilmiş RetrievedChunk listesi.
        """
        expanded = self._expander.expand(query)

        # chunk_id → (chunk, best_score) haritası
        best: dict[str, tuple[RetrievedChunk, float]] = {}

        for q in expanded:
            try:
                chunks = self._retriever.retrieve(q, top_k=top_k)
            except Exception:
                # Bir sorgu başarısız olursa diğerlerine devam et
                continue

            for chunk in chunks:
                # distance küçük = benzerlik yüksek → skoru tersine çevir
                score = 1.0 - (chunk.distance or 1.0)
                cid = chunk.chunk_id
                if cid not in best or score > best[cid][1]:
                    best[cid] = (chunk, score)

        merged = sorted(best.values(), key=lambda x: x[1], reverse=True)
        return [c for c, _ in merged[:top_k]]
