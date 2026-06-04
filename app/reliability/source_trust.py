"""Source trust scorer — produces a trust score based on paper metadata.

Considers peer-reviewed journals, known publishers, and recency.
"""

from __future__ import annotations

from dataclasses import dataclass

# Bilinen güvenilir kaynak türleri
_TRUSTED_SOURCES: set[str] = {
    "arxiv",
    "ssrn",
    "nature",
    "science",
    "journal of finance",
    "review of financial studies",
    "journal of financial economics",
    "management science",
    "quantitative finance",
    "mathematical finance",
}

_CURRENT_YEAR = 2026
_MAX_AGE_YEARS = 30  # 30 yıldan eski → güven düşür


@dataclass
class TrustScore:
    """Kaynak güven skoru."""

    source_id: str
    source_type: str
    trust_score: float  # 0.0–1.0
    reason: str


def _year_score(year_str: str | None) -> float:
    """Yayın yılına göre güven skoru."""
    if not year_str:
        return 0.5
    try:
        year = int(year_str[:4])
    except (ValueError, TypeError):
        return 0.5
    age = max(0, _CURRENT_YEAR - year)
    if age > _MAX_AGE_YEARS:
        return 0.3
    # Lineer azalma: yeni = 1.0, 30 yıllık = 0.3
    return max(0.3, 1.0 - (age / _MAX_AGE_YEARS) * 0.7)


def _source_type_score(source: str | None) -> float:
    """Kaynak türüne göre güven skoru."""
    if not source:
        return 0.4
    src_lower = source.lower()
    if any(trusted in src_lower for trusted in _TRUSTED_SOURCES):
        return 1.0
    if src_lower in ("manual", "pdf"):
        return 0.6
    return 0.5


def _author_score(authors: str | None) -> float:
    """Yazar bilgisine göre güven skoru."""
    if not authors or authors in ("{}", "[]", "null", ""):
        return 0.3
    return 0.8


class SourceTrustScorer:
    """Makale metadata'sına dayalı güven puanlayıcı."""

    def score(self, paper_id: str, metadata: dict) -> TrustScore:
        """Makale için güven skoru hesapla.

        Args:
            paper_id: Makale kimliği.
            metadata: Makale metadata sözlüğü (year, source, authors, title vb.).

        Returns:
            TrustScore nesnesi.
        """
        year_s = _year_score(metadata.get("year"))
        src_s = _source_type_score(metadata.get("source"))
        auth_s = _author_score(metadata.get("authors"))

        # Ağırlıklı ortalama
        score = year_s * 0.30 + src_s * 0.50 + auth_s * 0.20
        score = round(max(0.0, min(1.0, score)), 4)

        reasons = []
        if year_s < 0.5:
            reasons.append("eski yayın")
        if src_s < 0.6:
            reasons.append("bilinmeyen kaynak")
        if auth_s < 0.5:
            reasons.append("yazar bilgisi eksik")

        reason = ", ".join(reasons) if reasons else "güvenilir kaynak"

        return TrustScore(
            source_id=paper_id,
            source_type=metadata.get("source", "unknown"),
            trust_score=score,
            reason=reason,
        )
