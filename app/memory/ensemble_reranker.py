"""Ensemble reranker — consensus ordering from multiple reranking rounds.

Applies multiple rounds with slight score perturbation to produce a stable ranking.
"""

from __future__ import annotations

import random

from app.memory.reranker import Reranker
from app.memory.retrieval_service import RetrievedChunk

_PERTURBATION_SCALE = 0.05  # Maksimum skor rastgele gürültü


class EnsembleReranker:
    """Birden fazla reranking turuyla konsensüs sıralaması üretiyor.

    Her tur hafif skor pertürbasyonu ile çalıştırılır; sonuçlar oy çoğunluğuyla
    birleştirilir.

    Args:
        reranker: Temel Reranker örneği.
    """

    def __init__(self, reranker: Reranker) -> None:
        self._reranker = reranker
        self._rng = random.Random(42)  # Deterministik

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        runs: int = 2,
    ) -> list[RetrievedChunk]:
        """Çoklu tur reranking ile konsensüs sıralaması döndür.

        Args:
            query: Kullanıcı sorgusu.
            chunks: Yeniden sıralanacak chunk listesi.
            runs: Kaç tur çalıştırılacağı.

        Returns:
            Konsensüs sıralamasına göre düzenlenmiş RetrievedChunk listesi.
        """
        if not chunks or runs <= 1:
            return self._reranker.rerank(query, chunks)

        # Her tur için sıralama pozisyonlarını kaydet
        # chunk_id → toplam sıra puanı (düşük = iyi)
        rank_accumulator: dict[str, float] = {c.chunk_id: 0.0 for c in chunks}

        chunk_by_id: dict[str, RetrievedChunk] = {c.chunk_id: c for c in chunks}

        for _run in range(runs):
            # Hafif pertürbasyon: distance'ları küçük gürültüyle boz
            perturbed = []
            for chunk in chunks:
                noise = self._rng.uniform(-_PERTURBATION_SCALE, _PERTURBATION_SCALE)
                original_dist = chunk.distance
                new_dist = None
                if original_dist is not None:
                    new_dist = max(0.0, original_dist + noise)

                perturbed.append(
                    RetrievedChunk(
                        chunk_id=chunk.chunk_id,
                        paper_id=chunk.paper_id,
                        text=chunk.text,
                        page_number=chunk.page_number,
                        section_name=chunk.section_name,
                        title=chunk.title,
                        distance=new_dist,
                    )
                )

            ranked = self._reranker.rerank(query, perturbed)

            # Sıra puanı ekle (1. sıra = 1 puan, vb.)
            for pos, chunk in enumerate(ranked, start=1):
                rank_accumulator[chunk.chunk_id] += pos

        # Toplam sıra puanına göre sırala (düşük puan = iyi)
        sorted_ids = sorted(rank_accumulator.items(), key=lambda x: x[1])

        return [chunk_by_id[cid] for cid, _ in sorted_ids if cid in chunk_by_id]
