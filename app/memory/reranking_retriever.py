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

from app.config import get_settings
from app.memory.reranker import Reranker
from app.memory.retrieval_service import RetrievalService, RetrievedChunk


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
        reranker: Reranker | None = None,
        overfetch: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.settings = get_settings()
        self.base = base or RetrievalService()
        self.reranker = reranker or Reranker()
        self.overfetch = overfetch if overfetch is not None else self.settings.rag_overfetch
        self.enabled = enabled if enabled is not None else self.settings.rag_rerank

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        k = top_k or self.settings.rag_top_k

        if not self.enabled:
            return self.base.retrieve(query, top_k=k)

        # Geniş aday havuzu çek (en az k; ideal olarak k * overfetch).
        candidate_k = max(k, k * max(1, self.overfetch))
        candidates = self.base.retrieve(query, top_k=candidate_k)
        if not candidates:
            return []

        ranked = self.reranker.rerank(query, candidates)
        return ranked[:k]
