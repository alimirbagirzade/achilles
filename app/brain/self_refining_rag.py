"""Self-Refining RAG.

Each round detects incomplete formulas or arguments; expands with adjacent
chunks if context quality is insufficient.
"""

from __future__ import annotations

from app.brain.multi_query_retriever import MultiQueryRetriever
from app.memory.contextual_chunker import ChunkQualityFlags, ContextualChunker
from app.memory.reranker import Reranker
from app.memory.retrieval_service import RetrievedChunk


def _quality_issues(flags: list[ChunkQualityFlags]) -> list[str]:
    """Kalite sorunlarını dize listesi olarak döndür."""
    issues: list[str] = []
    for f in flags:
        if f.has_incomplete_formula:
            issues.append(f"Eksik formül: {f.chunk_id}")
        if f.has_incomplete_argument:
            issues.append(f"Eksik argüman: {f.chunk_id}")
    return issues


def _build_quality_report(
    issues: list[str],
    chunks_count: int,
    round_num: int,
) -> str:
    """İnsan okunabilir kalite raporu oluştur."""
    if not issues:
        return (
            f"[Tur {round_num}] Kalite iyi. "
            f"Toplam {chunks_count} chunk getirildi, sorun tespit edilmedi."
        )
    issue_lines = "\n  - ".join(issues)
    return (
        f"[Tur {round_num}] {chunks_count} chunk; "
        f"{len(issues)} sorun tespit edildi:\n  - {issue_lines}"
    )


class SelfRefiningRAG:
    """Çok turlu, kendi kendini iyileştiren RAG.

    Her turda:
    1. Retrieval + reranking yapılır.
    2. Bağlam kalitesi (eksik formül / argüman) kontrol edilir.
    3. Sorun varsa komşu chunk'larla genişleme denenir.
    """

    def __init__(
        self,
        retriever: MultiQueryRetriever,
        reranker: Reranker,
        chunker_annotator: ContextualChunker,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._annotator = chunker_annotator

    def retrieve_and_refine(
        self,
        query: str,
        top_k: int = 5,
        max_rounds: int = 2,
    ) -> tuple[list[RetrievedChunk], str]:
        """Retrieval + iyileştirme döngüsü.

        Args:
            query: Kullanıcı sorgusu.
            top_k: Her turda getirilecek chunk sayısı.
            max_rounds: Maksimum iyileştirme turu sayısı.

        Returns:
            (nihai_chunk_listesi, kalite_raporu) çifti.
        """
        chunks: list[RetrievedChunk] = []
        report = ""

        for round_num in range(1, max_rounds + 1):
            # Retrieval
            chunks = self._retriever.retrieve(query, top_k=top_k)

            # Reranking
            chunks = self._reranker.rerank(query, chunks)

            # Bağlam kalitesi değerlendirmesi
            from app.ingestion.chunker import TextChunk

            synthetic_text_chunks = [
                TextChunk(
                    paper_id=c.paper_id,
                    chunk_index=int(c.chunk_id.split("_c")[-1]) if "_c" in c.chunk_id else i,
                    text=c.text,
                    page_number=c.page_number,
                    section_name=c.section_name,
                )
                for i, c in enumerate(chunks)
            ]

            flags = self._annotator.annotate(synthetic_text_chunks)
            issues = _quality_issues(flags)
            report = _build_quality_report(issues, len(chunks), round_num)

            if not issues:
                break

            # Sorun varsa komşu chunk ID'lerini ekle (sonraki turda genişleme)
            # Şu an top_k'yı artırarak yeniden dene
            top_k = min(top_k + 3, 20)

        return chunks, report
