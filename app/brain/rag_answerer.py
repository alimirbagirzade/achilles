"""RAG answerer.

Produces the project-mandated answer structure:
1. Kısa cevap (short answer)
2. Kullanılan kaynaklar (sources used)
3. Akademik bulgu (academic finding)
4. Trading hipotezi (trading hypothesis)
5. Test edilmesi gereken noktalar (what to test)

The model is explicitly instructed NOT to invent sources. If no chunks are
retrieved, it must say so rather than hallucinate.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.brain.local_llm import LLMUnavailable, LocalLLM
from app.brain.prompt_loader import load_prompt
from app.memory.retrieval_service import RetrievalService, RetrievedChunk


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
                    "Kaynak bulunamadı. Hafızada bu soruya dayanak oluşturacak "
                    "makale chunk'ı yok. Önce ilgili PDF'leri ingest edin."
                ),
                sources=[],
                llm_used=False,
            )

        context = _format_context(chunks)
        try:
            system = load_prompt("rag_answer")
        except FileNotFoundError:
            system = "Sadece verilen kaynaklara dayan; kaynak yoksa uydurma."

        prompt = (
            f"KAYNAKLAR:\n{context}\n\n"
            f"SORU: {question}\n\n"
            "Yukarıdaki kaynaklara DAYANARAK cevap ver. Şu formatı kullan:\n"
            "1. Kısa cevap\n2. Kullanılan kaynaklar (paper_id:chunk_id)\n"
            "3. Akademik bulgu\n4. Trading hipotezi\n5. Test edilmesi gereken noktalar\n"
            "Kaynaklarda olmayan bir şey iddia etme."
        )

        try:
            text = self.llm.generate(prompt, system=system, temperature=0.2)
            return RagAnswer(question=question, answer=text, sources=chunks, llm_used=True)
        except LLMUnavailable:
            # Graceful degradation: still return retrieved sources.
            cites = "\n".join(f"- {c.citation} {c.title or ''}".strip() for c in chunks)
            text = (
                "[LLM çevrimdışı — yalnızca retrieval sonuçları gösteriliyor]\n\n"
                "Kullanılabilir kaynaklar:\n" + cites
            )
            return RagAnswer(question=question, answer=text, sources=chunks, llm_used=False)
