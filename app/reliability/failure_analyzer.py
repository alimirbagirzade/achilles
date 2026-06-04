"""Failure analyzer — records and queries RAG answer failures in SQLite.

Classifies failures by type; produces suggested fixes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from app.memory.sqlite_store import FailureLog, SqliteStore


class FailureType(Enum):
    """RAG sistem hata tipleri."""

    BAD_RETRIEVAL = "bad_retrieval"
    BAD_CHUNKING = "bad_chunking"
    BAD_RERANKING = "bad_reranking"
    HALLUCINATED_CLAIM = "hallucinated_claim"
    WRONG_CITATION = "wrong_citation"
    FAILED_TO_ABSTAIN = "failed_to_abstain"


@dataclass
class FailureRecord:
    """Tek bir RAG hatasının kaydı."""

    question: str
    answer: str
    failure_type: FailureType
    root_cause: str
    suggested_fix: str = ""
    hallucination: bool = False
    wrong_citation: bool = False


def _make_failure_id(question: str, failure_type: str) -> str:
    text = f"{question[:100]}_{failure_type}"
    return "fail_" + hashlib.md5(text.encode()).hexdigest()[:12]


class FailureAnalyzer:
    """RAG hata kaydedici ve sorgulayıcı.

    SqliteStore üzerinden FailureLog tablosuna yazar ve okur.
    """

    def __init__(self, store: SqliteStore | None = None) -> None:
        self._store = store or SqliteStore()

    def record(self, failure: FailureRecord) -> str:
        """Hatayı SQLite'a kaydet.

        Args:
            failure: Kaydedilecek FailureRecord.

        Returns:
            Oluşturulan failure_id.
        """

        failure_id = _make_failure_id(failure.question, failure.failure_type.value)

        with self._store.session() as session:
            existing = session.get(FailureLog, failure_id)
            if existing:
                return failure_id

            log = FailureLog(
                failure_id=failure_id,
                question_text=failure.question[:500],
                answer_text=failure.answer[:1000],
                failure_type=failure.failure_type.value,
                root_cause=failure.root_cause,
                hallucination=1 if failure.hallucination else 0,
                wrong_citation=1 if failure.wrong_citation else 0,
                suggested_fix=failure.suggested_fix,
            )
            session.add(log)

        return failure_id

    def get_failures(self, failure_type: FailureType | None = None) -> list[FailureRecord]:
        """Kayıtlı hataları sorgula.

        Args:
            failure_type: Filtrelenecek hata tipi (None = hepsi).

        Returns:
            FailureRecord listesi.
        """
        from sqlalchemy import select

        with self._store.session() as session:
            q = select(FailureLog)
            if failure_type is not None:
                q = q.where(FailureLog.failure_type == failure_type.value)
            rows = list(session.scalars(q.order_by(FailureLog.created_at.desc())))

        return [
            FailureRecord(
                question=row.question_text,
                answer=row.answer_text,
                failure_type=FailureType(row.failure_type),
                root_cause=row.root_cause or "",
                suggested_fix=row.suggested_fix or "",
                hallucination=bool(row.hallucination),
                wrong_citation=bool(row.wrong_citation),
            )
            for row in rows
        ]
