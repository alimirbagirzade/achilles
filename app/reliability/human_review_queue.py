"""Human review queue — sends low-confidence answers for human inspection.

Adds items to the review queue on low confidence score or detected failure.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass

from app.memory.retrieval_service import RetrievedChunk
from app.memory.sqlite_store import SqliteStore


def _make_review_id(question: str) -> str:
    ts = dt.datetime.now(dt.UTC).isoformat()
    text = f"{question[:50]}_{ts}"
    return "rev_" + hashlib.md5(text.encode()).hexdigest()[:12]


@dataclass
class ReviewItem:
    """İnceleme kuyruğundaki tek bir öğe."""

    review_id: str
    question: str
    context_json: str  # JSON olarak serileştirilmiş chunk listesi
    answer: str
    confidence_score: float
    status: str  # "pending" | "approved" | "rejected"


class HumanReviewQueue:
    """İnsan inceleme kuyruğu.

    Düşük güvenli cevapları işaretler ve listeleyebilir.
    Depolama için hafıza içi liste kullanır (SqliteStore entegrasyonu için hazır).
    """

    def __init__(self, store: SqliteStore | None = None) -> None:
        self._store = store or SqliteStore()
        self._queue: list[ReviewItem] = []  # Hafıza içi fallback

    def submit(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        answer: str,
        confidence: float,
    ) -> str:
        """Cevabı inceleme kuyruğuna ekle.

        Args:
            question: Kullanıcı sorusu.
            chunks: Cevabın dayandığı chunk'lar.
            answer: Üretilen cevap metni.
            confidence: Güven skoru (0.0–1.0).

        Returns:
            review_id dizesi.
        """
        review_id = _make_review_id(question)

        context_data = [
            {
                "chunk_id": c.chunk_id,
                "paper_id": c.paper_id,
                "text": c.text[:300],
            }
            for c in chunks
        ]
        context_json = json.dumps(context_data, ensure_ascii=False)

        item = ReviewItem(
            review_id=review_id,
            question=question,
            context_json=context_json,
            answer=answer,
            confidence_score=confidence,
            status="pending",
        )
        self._queue.append(item)

        return review_id

    def list_pending(self) -> list[ReviewItem]:
        """Bekleyen inceleme öğelerini döndür.

        Returns:
            status="pending" olan ReviewItem listesi.
        """
        return [item for item in self._queue if item.status == "pending"]

    def approve(self, review_id: str) -> bool:
        """İnceleme öğesini onayla."""
        for item in self._queue:
            if item.review_id == review_id:
                item.status = "approved"
                return True
        return False

    def reject(self, review_id: str) -> bool:
        """İnceleme öğesini reddet."""
        for item in self._queue:
            if item.review_id == review_id:
                item.status = "rejected"
                return True
        return False
