"""Retrieval audit log — persists every retrieval run to SQLite."""

from __future__ import annotations

import datetime as dt
import hashlib

from app.memory.retrieval_service import RetrievedChunk
from app.memory.sqlite_store import RagQuery, RetrievalResult, RetrievalRun, SqliteStore


def _make_run_id(query: str, method: str) -> str:
    ts = dt.datetime.now(dt.UTC).isoformat()
    text = f"{query[:50]}_{method}_{ts}"
    return "run_" + hashlib.md5(text.encode()).hexdigest()[:12]


def _make_query_id(query: str) -> str:
    return "qry_" + hashlib.md5(query.encode()).hexdigest()[:12]


def _make_result_id(run_id: str, chunk_id: str) -> str:
    return "res_" + hashlib.md5(f"{run_id}_{chunk_id}".encode()).hexdigest()[:12]


class RetrievalAuditLog:
    """Retrieval çalışmalarını kalıcı olarak kaydeden denetim günlüğü.

    Her çağrı yeni bir RetrievalRun ve ilgili RetrievalResult kayıtları oluşturur.
    """

    def __init__(self, store: SqliteStore | None = None) -> None:
        self._store = store or SqliteStore()

    def log(
        self,
        query: str,
        method: str,
        top_k: int,
        chunks: list[RetrievedChunk],
    ) -> str:
        """Retrieval çalışmasını kaydet.

        Args:
            query: Kullanıcı sorgusu.
            method: Kullanılan yöntem (örn. "semantic", "hybrid", "multi_query").
            top_k: İstenen chunk sayısı.
            chunks: Getirilen chunk'lar.

        Returns:
            Oluşturulan retrieval_run_id.
        """
        query_id = _make_query_id(query)
        run_id = _make_run_id(query, method)

        with self._store.session() as session:
            # Sorgu kaydı (yoksa oluştur)
            if session.get(RagQuery, query_id) is None:
                session.add(
                    RagQuery(
                        query_id=query_id,
                        original_query=query[:500],
                        expanded_queries_json="[]",
                    )
                )

            # Çalışma kaydı
            run = RetrievalRun(
                retrieval_run_id=run_id,
                query_id=query_id,
                retrieval_method=method,
                top_k=top_k,
                rerank_used=0,
                self_refinement_used=0,
            )
            session.add(run)

            # Sonuç kayıtları
            for rank, chunk in enumerate(chunks, start=1):
                result_id = _make_result_id(run_id, chunk.chunk_id)
                semantic_score = (
                    round(1.0 - chunk.distance, 4) if chunk.distance is not None else None
                )
                session.add(
                    RetrievalResult(
                        result_id=result_id,
                        retrieval_run_id=run_id,
                        paper_id=chunk.paper_id,
                        chunk_id=chunk.chunk_id,
                        semantic_score=semantic_score,
                        rerank_score=None,
                        final_rank=rank,
                        reason=None,
                    )
                )

        return run_id
