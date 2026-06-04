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
from app.memory.retrieval_service import RetrievalService, RetrievedChunk

_BILINGUAL_FORMAT = """\
Answer using the following bilingual format (English first, Turkish below each section):

1. Short Answer / Kısa Cevap
2. Sources Used / Kullanılan Kaynaklar
   - paper_id, chunk_id, section, page_number (if available)
3. Context Quality / Bağlam Kalitesi
   - Is the context complete? / Bağlam tam mı?
   - Any cut formula or argument? / Formül veya argüman kesilmiş mi?
4. Academic Finding / Akademik Bulgu
5. Formula or Argument Analysis / Formül veya Argüman Analizi
   - Formula / Formül
   - Variable meanings / Değişkenlerin anlamı
   - Context / Bağlam
   - Limitations / Sınırlamalar
6. Trading Hypothesis / Trading Hipotezi
   - Only if applicable / Yalnızca uygulanabilirse
   - If not applicable, write: "This finding cannot be directly converted to a trading rule."
     / "Bu bulgu doğrudan trading kuralına çevrilemez."
7. Test Plan / Test Planı
   - Market, timeframe, data, indicator, backtest method, out-of-sample, costs
   / Piyasa, zaman dilimi, veri, indikatör, backtest yöntemi, OOS, maliyetler
8. Risks / Riskler
   - Overfit, data leakage, look-ahead bias, survivorship bias, spread/slippage
9. Next Step / Sonraki Adım

Do NOT invent any source, formula, dataset, or conclusion not present in the retrieved context.
Kaynaklarda olmayan herhangi bir kaynak, formül, veri seti veya sonuç uydurmayın.
"""


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
        retriever: RetrievalService | None = None,
        llm: LocalLLM | None = None,
    ) -> None:
        self.retriever = retriever or RetrievalService()
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
            system = load_prompt("rag_answer")
        except FileNotFoundError:
            system = (
                "Answer ONLY from the provided sources. Do not invent facts. "
                "Use bilingual format (English + Turkish).\n"
                "Yalnızca verilen kaynaklara dayan. Gerçek uydurmayın. "
                "İki dilli format kullan (İngilizce + Türkçe)."
            )

        prompt = (
            f"SOURCES / KAYNAKLAR:\n{context}\n\nQUESTION / SORU: {question}\n\n{_BILINGUAL_FORMAT}"
        )

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
