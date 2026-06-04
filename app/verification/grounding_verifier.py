"""Grounding verifier — checks whether answer sentences are supported by chunks.

Evaluates each sentence individually; marks as SPECULATIVE if it
contains speculative markers like "hipotez" or "hypothesis".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.memory.retrieval_service import RetrievedChunk


class GroundingLevel(Enum):
    """Bir cümlenin chunk'lardaki dayanak düzeyi."""

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    SPECULATIVE = "speculative"


@dataclass
class GroundingResult:
    """Tek bir cümle için dayanak değerlendirmesi."""

    claim: str
    level: GroundingLevel
    evidence_chunk_id: str | None


# Spekülatif işaretçiler
_SPECULATIVE_RE = re.compile(
    r"\b(hipotez|hypothesis|possibly|might|could|speculative|muhtemelen|olabilir)\b",
    re.IGNORECASE,
)

# Cümle bölücü
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _tokenize(text: str) -> set[str]:
    """4+ karakterli küçük harf token seti."""
    return set(re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ]{4,}", text.lower()))


def _find_supporting_chunk(
    sentence_tokens: set[str],
    chunks: list[RetrievedChunk],
    min_overlap: int = 3,
) -> RetrievedChunk | None:
    """Cümleyi destekleyen ilk chunk'ı bul."""
    best: tuple[int, RetrievedChunk | None] = (0, None)
    for chunk in chunks:
        chunk_tokens = _tokenize(chunk.text)
        overlap = len(sentence_tokens & chunk_tokens)
        if overlap > best[0]:
            best = (overlap, chunk)
    if best[0] >= min_overlap:
        return best[1]
    return None


class GroundingVerifier:
    """Cevap cümlelerinin chunk dayanaklarını doğrulayan sınıf."""

    def verify(
        self,
        answer_text: str,
        chunks: list[RetrievedChunk],
    ) -> list[GroundingResult]:
        """Cevaptaki her cümle için dayanak seviyesini belirle.

        Args:
            answer_text: Doğrulanacak cevap metni.
            chunks: Retrieval'dan gelen gerçek chunk'lar.

        Returns:
            Her anlamlı cümle için GroundingResult listesi.
        """
        sentences = _SENTENCE_SPLIT.split(answer_text)
        results: list[GroundingResult] = []

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue

            # Spekülatif mi?
            if _SPECULATIVE_RE.search(sentence):
                results.append(
                    GroundingResult(
                        claim=sentence,
                        level=GroundingLevel.SPECULATIVE,
                        evidence_chunk_id=None,
                    )
                )
                continue

            s_tokens = _tokenize(sentence)
            if not s_tokens:
                continue

            supporting = _find_supporting_chunk(s_tokens, chunks, min_overlap=3)

            if supporting:
                # Güçlü destek (≥5 token örtüşmesi)
                overlap = len(s_tokens & _tokenize(supporting.text))
                level = (
                    GroundingLevel.SUPPORTED if overlap >= 5 else GroundingLevel.PARTIALLY_SUPPORTED
                )
                results.append(
                    GroundingResult(
                        claim=sentence,
                        level=level,
                        evidence_chunk_id=supporting.chunk_id,
                    )
                )
            else:
                results.append(
                    GroundingResult(
                        claim=sentence,
                        level=GroundingLevel.UNSUPPORTED,
                        evidence_chunk_id=None,
                    )
                )

        return results
