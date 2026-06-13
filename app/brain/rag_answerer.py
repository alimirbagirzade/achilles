"""RAG answerer.

Produces a bilingual (English + Turkish) answer structure:
1. Short Answer / Kısa Cevap
2. Sources Used / Kullanılan Kaynaklar
3. Context Quality / Bağlam Kalitesi
4. Academic Finding / Akademik Bulgu
5. Formula or Argument Analysis / Formül veya Argüman Analizi
6. Trading Hypothesis / Trading Hipotezi
7. Test Plan / Test Planı
8. Risks / Riskler
9. Next Step / Sonraki Adım

The model is explicitly instructed NOT to invent sources. If no chunks are
retrieved, it must say so rather than hallucinate.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.brain.local_llm import LLMUnavailable, LocalLLM
from app.brain.prompt_loader import load_prompt
from app.memory.reranking_retriever import RerankingRetriever
from app.memory.retrieval_service import RetrievedChunk, Retriever

# NOT: Cevap formatı ARTIK tek kaynakta — app/prompts/rag_answer.md (sistem
# prompt'u olarak yüklenir). Eskiden burada ayrı bir _BILINGUAL_FORMAT vardı ve
# .md ile çatışıyordu (model iki farklı format alıyordu); birleştirildi (Faz A4).
# Kullanıcı prompt'una format enjekte edilmez; yalnız KAYNAKLAR + SORU verilir.

_FALLBACK_SYSTEM = (
    "Yalnızca verilen KAYNAKLAR'a dayan; kaynak yoksa 'kaynak bulunamadı' de, uydurma. "
    "Her iddiadan sonra [paper_id:chunk_id] satır-içi atıf ver. İki dilli (EN+TR) "
    "yapısal cevap: Kısa Cevap, Kaynaklar, Akademik Bulgu, Trading Hipotezi (test "
    "edilmemiş), Test Planı (OOS+maliyet+look-ahead yok), Riskler. Yatırım tavsiyesi verme."
)


@dataclass
class RagAnswer:
    question: str
    answer: str
    sources: list[RetrievedChunk]
    llm_used: bool


def _format_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for c in chunks:
        head = f"{c.citation}"
        if c.title:
            head += f" — {c.title}"
        blocks.append(f"{head}\n{c.text}")
    return "\n\n---\n\n".join(blocks)


class RagAnswerer:
    def __init__(
        self,
        retriever: Retriever | None = None,
        llm: LocalLLM | None = None,
    ) -> None:
        # Varsayılan: over-fetch + heuristik rerank (robust RAG yolu). Stub/özel
        # retriever enjekte edilirse aynen kullanılır (test izolasyonu korunur).
        self.retriever = retriever or RerankingRetriever()
        self.llm = llm or LocalLLM()

    def answer(self, question: str, top_k: int | None = None) -> RagAnswer:
        chunks = self.retriever.retrieve(question, top_k=top_k)

        if not chunks:
            return RagAnswer(
                question=question,
                answer=(
                    "No sources found. No article chunks in memory to support this query.\n"
                    "Please ingest the relevant PDFs first.\n\n"
                    "---\n\n"
                    "Kaynak bulunamadı. Hafızada bu soruya dayanak oluşturacak chunk yok.\n"
                    "Önce ilgili PDF'leri ingest edin."
                ),
                sources=[],
                llm_used=False,
            )

        context = _format_context(chunks)
        try:
            system = load_prompt("rag_answer")  # tek kaynak format + grounding kuralları
        except FileNotFoundError:
            system = _FALLBACK_SYSTEM

        # Format sistem prompt'undan gelir; kullanıcı prompt'u yalnız bağlam + soru.
        prompt = f"SOURCES / KAYNAKLAR:\n{context}\n\nQUESTION / SORU: {question}"

        try:
            text = self.llm.generate(prompt, system=system, temperature=0.2)
            return RagAnswer(question=question, answer=text, sources=chunks, llm_used=True)
        except LLMUnavailable:
            # Graceful degradation: still return retrieved sources.
            cites = "\n".join(f"- {c.citation} {c.title or ''}".strip() for c in chunks)
            text = (
                "[LLM offline — retrieval results only"
                " / LLM çevrimdışı — yalnızca retrieval sonuçları]\n\n"
                "Available sources / Kullanılabilir kaynaklar:\n" + cites
            )
            return RagAnswer(question=question, answer=text, sources=chunks, llm_used=False)
