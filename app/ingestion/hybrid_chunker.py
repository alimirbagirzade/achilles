"""Hybrid chunker — preserves section headers, avoids splitting LaTeX formulas.

Extends the existing chunk_text function; treats ## headings as section
boundaries and applies basic formula-preservation logic during chunking.
"""

from __future__ import annotations

import re

from app.config import get_settings
from app.ingestion.chunker import TextChunk

# ---------------------------------------------------------------------------
# Sabitler / desenler
# ---------------------------------------------------------------------------
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
_KNOWN_SECTION_RE = re.compile(
    r"^\s*(abstract|introduction|related work|methodology|methods|data|results|"
    r"discussion|conclusion|references)\b",
    re.IGNORECASE,
)

# LaTeX formül başlangıç / bitiş desenleri (inline ve display)
_FORMULA_OPEN_RE = re.compile(r"(\$\$|\\\[|\\\(|\\begin\{equation)")
_FORMULA_CLOSE_RE = re.compile(r"(\$\$|\\\]|\\\)|\\end\{equation\})")

_INCOMPLETE_MARKER = "[INCOMPLETE_FORMULA]"


def _is_heading(line: str) -> tuple[bool, str | None]:
    """Satır markdown başlık mı? (bool, başlık_metni)."""
    m = _HEADING_RE.match(line.strip())
    if m:
        return True, m.group(2).strip()
    return False, None


def _detect_section(text: str) -> str | None:
    """Chunk metnindeki ilk bilinen bölüm adını döndür."""
    for line in text.splitlines()[:5]:
        is_h, title = _is_heading(line)
        if is_h and title:
            m = _KNOWN_SECTION_RE.match(title)
            if m:
                return m.group(1).lower()
            return title.lower()
        m = _KNOWN_SECTION_RE.match(line)
        if m:
            return m.group(1).lower()
    return None


def _split_into_segments(text: str) -> list[tuple[str, str | None]]:
    """Metni bölüm başlıklarında kır.

    Returns:
        Liste: (metin_parçası, bölüm_adı) çiftleri.
    """
    segments: list[tuple[str, str | None]] = []
    current_section: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines(keepends=True):
        is_h, title = _is_heading(line.rstrip())
        if is_h and title:
            if current_lines:
                segments.append(("".join(current_lines), current_section))
                current_lines = []
            current_section = title.lower()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        segments.append(("".join(current_lines), current_section))

    return segments


def _is_inside_formula(buf: str) -> bool:
    """Buffer formül ortamı içinde mi?"""
    opens = len(_FORMULA_OPEN_RE.findall(buf))
    closes = len(_FORMULA_CLOSE_RE.findall(buf))
    return opens > closes


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


class HybridChunker:
    """Bölüm başlıklarını koruyan ve LaTeX formüllerini bölmeyen chunker.

    Mevcut TextChunk dataclass'ı ile tam uyumludur.
    """

    def chunk(
        self,
        paper_id: str,
        text: str,
        *,
        chunk_size: int | None = None,
        overlap: int | None = None,
        page_number: int | None = None,
    ) -> list[TextChunk]:
        """Metni hibrit stratejiyle chunklara böl.

        Args:
            paper_id: Makale kimliği.
            text: Ham metin.
            chunk_size: Karakter cinsinden maksimum chunk boyutu (None → settings).
            overlap: Karakter cinsinden örtüşme (None → settings).
            page_number: Sayfa numarası (isteğe bağlı).

        Returns:
            Sıralı TextChunk listesi.
        """
        settings = get_settings()
        size = chunk_size or settings.chunk_size
        over = overlap if overlap is not None else settings.chunk_overlap

        segments = _split_into_segments(text)
        chunks: list[TextChunk] = []
        idx = 0

        for segment_text, section_name in segments:
            paragraphs = _split_paragraphs(segment_text)
            buf = ""
            buf_has_open_formula = False

            for para in paragraphs:
                # Formül ortamı içindeyse bir sonraki paragrafla devam et
                if buf_has_open_formula:
                    buf = f"{buf}\n\n{para}" if buf else para
                    buf_has_open_formula = _is_inside_formula(buf)
                    continue

                if len(buf) + len(para) + 2 <= size:
                    buf = f"{buf}\n\n{para}" if buf else para
                    buf_has_open_formula = _is_inside_formula(buf)
                    continue

                if buf:
                    # Chunk'ı kapat; formül açıksa marker ekle
                    chunk_text = buf
                    if _is_inside_formula(chunk_text):
                        chunk_text = chunk_text + "\n" + _INCOMPLETE_MARKER

                    chunks.append(
                        TextChunk(
                            paper_id=paper_id,
                            chunk_index=idx,
                            text=chunk_text,
                            page_number=page_number,
                            section_name=section_name or _detect_section(chunk_text),
                        )
                    )
                    idx += 1

                    tail = buf[-over:] if over else ""
                    buf = f"{tail}\n\n{para}" if tail else para
                    buf_has_open_formula = _is_inside_formula(buf)
                else:
                    # Tek büyük paragraf: sabit boyutta böl
                    for j in range(0, len(para), size):
                        piece = para[j : j + size]
                        chunks.append(
                            TextChunk(
                                paper_id=paper_id,
                                chunk_index=idx,
                                text=piece,
                                page_number=page_number,
                                section_name=section_name or _detect_section(piece),
                            )
                        )
                        idx += 1
                    buf = ""
                    buf_has_open_formula = False

            if buf:
                chunk_text = buf
                if _is_inside_formula(chunk_text):
                    chunk_text = chunk_text + "\n" + _INCOMPLETE_MARKER

                chunks.append(
                    TextChunk(
                        paper_id=paper_id,
                        chunk_index=idx,
                        text=chunk_text,
                        page_number=page_number,
                        section_name=section_name or _detect_section(chunk_text),
                    )
                )
                idx += 1

        return chunks
