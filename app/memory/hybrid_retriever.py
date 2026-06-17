"""Hybrid retrieval — combines semantic and BM25 scores.

Blends semantic (Chroma) and keyword (BM25) results using an alpha weight
parameter into a single ranked list.
"""

from __future__ import annotations

from app.memory.bm25_index import BM25Index
from app.memory.retrieval_service import RetrievalService, RetrievedChunk


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Skor sözlüğünü 0–1 aralığına normalize et."""
    if not scores:
        return {}
    min_s = min(scores.values())
    max_s = max(scores.values())
    rng = max_s - min_s
    if rng == 0:
        # Tüm skorlar eşit → nötr 0.5 (1.0 değil): alpha karışımı anlamını korur,
        # tek kaynak hibrit sıralamayı domine etmez.
        return dict.fromkeys(scores, 0.5)
    return {k: (v - min_s) / rng for k, v in scores.items()}


class HybridRetriever:
    """Semantik + BM25 hibrit retrieval.

    Her iki kaynaktan gelen sonuçları alpha ile ağırlıklandırır:
        final_score = alpha * semantic_score + (1 - alpha) * bm25_score

    Args:
        semantic: Semantik retrieval servisi (ChromaDB tabanlı).
        bm25: BM25 arama indeksi.
    """

    def __init__(
        self,
        semantic: RetrievalService,
        bm25: BM25Index,
    ) -> None:
        self._semantic = semantic
        self._bm25 = bm25

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = 0.7,
    ) -> list[RetrievedChunk]:
        """Hibrit skor ile en iyi chunk'ları döndür.

        Args:
            query: Kullanıcı sorgusu.
            top_k: Döndürülecek maksimum chunk sayısı.
            alpha: Semantik ağırlığı (0.0–1.0). BM25 ağırlığı = 1 - alpha.

        Returns:
            Hibrit skora göre sıralanmış RetrievedChunk listesi.
        """
        # Semantik retrieval
        try:
            semantic_chunks = self._semantic.retrieve(query, top_k=top_k * 2)
        except Exception:
            semantic_chunks = []

        # BM25 retrieval
        try:
            bm25_results = self._bm25.search(query, top_k=top_k * 2)
        except Exception:
            bm25_results = []

        # Semantik skorları topla (distance → skor)
        semantic_scores: dict[str, float] = {}
        chunk_by_id: dict[str, RetrievedChunk] = {}
        for chunk in semantic_chunks:
            score = 1.0 - (chunk.distance or 1.0)
            semantic_scores[chunk.chunk_id] = max(0.0, score)
            chunk_by_id[chunk.chunk_id] = chunk

        # BM25 skorları
        bm25_scores: dict[str, float] = dict(bm25_results)

        # Normalize
        sem_norm = _normalize_scores(semantic_scores)
        bm25_norm = _normalize_scores(bm25_scores)

        # Tüm bilinene chunk'ları topla
        all_ids = set(sem_norm.keys()) | set(bm25_norm.keys())
        combined: dict[str, float] = {}

        for cid in all_ids:
            s_score = sem_norm.get(cid, 0.0)
            b_score = bm25_norm.get(cid, 0.0)
            combined[cid] = alpha * s_score + (1 - alpha) * b_score

        # Sırala — SONRA top_k'yi yalnız metni elimizde olan (semantik) chunk'larla doldur.
        # BM25-only id'ler için METİN yok; boş-text stub döndürmek RAG alıntısını bozar
        # (Kural 7'ye aykırı "kaynak var" izlenimi) → ATLANIR. ANCAK top_k kesimi bu
        # filtreden ÖNCE yapılırsa BM25-only id'ler slot çalıp gerçek-metinli chunk'ları
        # düşürür; bu yüzden önce sırala, sonra metinli olanlarla top_k'ye kadar doldur.
        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)

        result: list[RetrievedChunk] = []
        for cid, _ in ranked:
            if cid in chunk_by_id:
                result.append(chunk_by_id[cid])
                if len(result) >= top_k:
                    break

        return result
