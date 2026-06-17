"""Over-fetch + yeniden sıralama (rerank) ile retrieval sarmalayıcı.

`RetrievalService` ile **aynı arayüzü** (`retrieve(query, top_k)`) sunar; böylece
`RagAnswerer` ve eval kodu somut sınıfa değil arayüze bağlanır ve "robust RAG"
yolu tek yerde toplanır.

Çalışma mantığı (LLM-free, çevrimdışı testlerle uyumlu):
1. Dense retrieval'dan `top_k * overfetch` aday çek (geniş havuz).
2. Heuristik `Reranker` ile yeniden sırala (semantik + anahtar kelime + bölüm
   önceliği + formül varlığı).
3. İlk `top_k` adayı döndür.

`rag_rerank` ayarı kapalıysa düz dense retrieval'a indirger (davranış değişmez).
Bu, "yazılı ama bağlanmamış" `Reranker`'ı canlı yola alan Faz A2 adımıdır;
eğitim gerektirmez (bkz. docs/RAG_EGITIM_YENIDEN_TASARIM.md).
"""

from __future__ import annotations

from typing import Protocol

from app.config import get_settings
from app.memory.reranker import Reranker
from app.memory.retrieval_service import RetrievalService, RetrievedChunk


class RerankerLike(Protocol):
    """Heuristik `Reranker` ve `CrossEncoderReranker` bu arayüzü uygular."""

    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]: ...


class RerankingRetriever:
    """Dense retrieval + heuristik rerank (over-fetch → rerank → truncate).

    Args:
        base: Temel (dense) retrieval servisi. Verilmezse `RetrievalService()`.
        reranker: Yeniden sıralayıcı. Verilmezse `Reranker()`.
        overfetch: Aday çarpanı; `None` → `settings.rag_overfetch`.
        enabled: Rerank açık mı; `None` → `settings.rag_rerank`. Kapalıysa düz
            dense retrieval döner.
    """

    def __init__(
        self,
        base: RetrievalService | None = None,
        reranker: RerankerLike | None = None,
        overfetch: int | None = None,
        enabled: bool | None = None,
        hybrid: bool | None = None,
        rrf: bool | None = None,
    ) -> None:
        self.settings = get_settings()
        self.base = base or RetrievalService()
        self.reranker: RerankerLike = reranker or self._default_reranker()
        self.overfetch = overfetch if overfetch is not None else self.settings.rag_overfetch
        self.enabled = enabled if enabled is not None else self.settings.rag_rerank
        # Hibrit: dense aday havuzunu BM25 (keyword) eşleşmeleriyle genişlet (Faz A3).
        self.hybrid = hybrid if hybrid is not None else self.settings.rag_hybrid
        # RRF füzyon modu (opt-in): dense ve BM25 sıralı listelerini Reciprocal Rank
        # Fusion ile birleştirir (heuristik/cross-encoder rerank yerine). Skor
        # kalibrasyonu gerektirmez → karşılaştırılamaz skorlu kaynaklarda sağlam.
        # Varsayılan kapalı → mevcut over-fetch+rerank davranışı değişmez.
        self.rrf = rrf if rrf is not None else self.settings.rag_rrf

    def _default_reranker(self) -> RerankerLike:
        # Cross-encoder OPT-IN (Faz A8); açıksa onu kullan (model yoksa kendi içinde
        # heuristiğe düşer). Kapalıysa doğrudan heuristik Reranker.
        if self.settings.rag_cross_encoder:
            from app.memory.cross_encoder_reranker import CrossEncoderReranker

            return CrossEncoderReranker()
        return Reranker()

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        k = top_k or self.settings.rag_top_k

        if not self.enabled:
            return self.base.retrieve(query, top_k=k)

        # RRF füzyon modu (opt-in): dense + BM25 sıralı listelerini RRF ile birleştir.
        if self.rrf:
            return self._rrf_retrieve(query, k)

        # Geniş aday havuzu çek (en az k; ideal olarak k * overfetch).
        candidate_k = max(k, k * max(1, self.overfetch))
        candidates = self.base.retrieve(query, top_k=candidate_k)

        # Hibrit: BM25 keyword adaylarını ekle (dense'in kaçırdığı teknik terimler:
        # ATR, Sharpe, RSI…). Korpus boş/erişilemezse sessizce dense-only kalır.
        if self.hybrid:
            candidates = self._add_bm25_candidates(query, candidates, candidate_k)

        if not candidates:
            return []

        ranked = self.reranker.rerank(query, candidates)
        return ranked[:k]

    def _rrf_retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        """Dense ve BM25 sıralı listelerini Reciprocal Rank Fusion ile birleştir.

        Heuristik/cross-encoder rerank yerine saf sıra-füzyonu uygular (deterministik,
        LLM-free). BM25 korpusu boş/erişilemezse veya hibrit kapalıysa dense-only'e
        düşer (davranış güvenli). Metni olmayan (BM25-only, chunk_map'te yok) id'ler
        atlanır — boş kaynak RAG alıntısını bozmasın (Kural 7).
        """
        from app.memory.bm25_corpus import get_corpus_bm25
        from app.memory.rank_fusion import fuse_ranked

        candidate_k = max(k, k * max(1, self.overfetch))
        dense = self.base.retrieve(query, top_k=candidate_k)
        chunk_by_id: dict[str, RetrievedChunk] = {c.chunk_id: c for c in dense}
        dense_ids = [c.chunk_id for c in dense]

        bm25_ids: list[str] = []
        if self.hybrid:
            bm25, chunk_map = get_corpus_bm25()
            if bm25 is not None:
                for cid, _score in bm25.search(query, candidate_k):
                    bm25_ids.append(cid)
                    if cid not in chunk_by_id and cid in chunk_map:
                        chunk_by_id[cid] = chunk_map[cid]

        ranked_lists = [lst for lst in (dense_ids, bm25_ids) if lst]
        if not ranked_lists:
            return []

        fused = fuse_ranked(ranked_lists, k=self.settings.rag_rrf_k)
        out = [chunk_by_id[cid] for cid in fused if cid in chunk_by_id]
        return out[:k]

    def _add_bm25_candidates(
        self, query: str, candidates: list[RetrievedChunk], candidate_k: int
    ) -> list[RetrievedChunk]:
        from app.memory.bm25_corpus import get_corpus_bm25

        bm25, chunk_map = get_corpus_bm25()
        if bm25 is None:
            return candidates
        have = {c.chunk_id for c in candidates}
        for cid, _score in bm25.search(query, candidate_k):
            if cid not in have and cid in chunk_map:
                candidates.append(chunk_map[cid])
                have.add(cid)
        return candidates
