"""Split paper text into retrieval-friendly chunks.

Strategy: paragraph-aware greedy packing up to ``chunk_size`` characters with
``chunk_overlap`` carry-over. Each chunk knows which page it (mostly) came from
so retrieval results can cite a page number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import get_settings
from app.ingestion.pdf_parser import ParsedPdf

_TOKEN_DIVISOR = 4  # rough chars-per-token estimate
_HEADING_RE = re.compile(
    r"^\s*(abstract|introduction|related work|methodology|methods|data|results|"
    r"discussion|conclusion|references)\b",
    re.IGNORECASE,
)


@dataclass
class TextChunk:
    paper_id: str
    chunk_index: int
    text: str
    page_number: int | None = None
    section_name: str | None = None

    @property
    def chunk_id(self) -> str:
        return f"{self.paper_id}_c{self.chunk_index:04d}"

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def token_estimate(self) -> int:
        return max(1, self.char_count // _TOKEN_DIVISOR)


def _detect_section(text: str) -> str | None:
    for line in text.splitlines()[:3]:
        m = _HEADING_RE.match(line)
        if m:
            return m.group(1).lower()
    return None


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(
    paper_id: str,
    text: str,
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
    page_number: int | None = None,
) -> list[TextChunk]:
    settings = get_settings()
    size = chunk_size or settings.chunk_size
    over = overlap if overlap is not None else settings.chunk_overlap

    chunks: list[TextChunk] = []
    buf = ""
    idx = 0
    for para in _split_paragraphs(text):
        if len(buf) + len(para) + 2 <= size:
            buf = f"{buf}\n\n{para}" if buf else para
            continue
        if buf:
            chunks.append(
                TextChunk(
                    paper_id=paper_id,
                    chunk_index=idx,
                    text=buf,
                    page_number=page_number,
                    section_name=_detect_section(buf),
                )
            )
            idx += 1
            tail = buf[-over:] if over else ""
            buf = f"{tail}\n\n{para}" if tail else para
        else:
            # single oversized paragraph: hard-split
            for j in range(0, len(para), size):
                piece = para[j : j + size]
                chunks.append(
                    TextChunk(
                        paper_id=paper_id,
                        chunk_index=idx,
                        text=piece,
                        page_number=page_number,
                        section_name=_detect_section(piece),
                    )
                )
                idx += 1
            buf = ""
    if buf:
        chunks.append(
            TextChunk(
                paper_id=paper_id,
                chunk_index=idx,
                text=buf,
                page_number=page_number,
                section_name=_detect_section(buf),
            )
        )
    return chunks


def chunk_parsed_pdf(paper_id: str, parsed: ParsedPdf, **kwargs) -> list[TextChunk]:
    """Chunk page-by-page so chunks retain page numbers, then re-index globally."""
    all_chunks: list[TextChunk] = []
    running = 0
    for page_no, page_text in enumerate(parsed.pages, start=1):
        if not page_text.strip():
            continue
        page_chunks = chunk_text(paper_id, page_text, page_number=page_no, **kwargs)
        for c in page_chunks:
            c.chunk_index = running
            running += 1
            all_chunks.append(c)
    return all_chunks
