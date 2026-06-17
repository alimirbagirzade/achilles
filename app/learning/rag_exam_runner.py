"""rag_exam_runner.py — Soruları mevcut RagAnswerer'a sorar ve cevapları doğrular.

Mevcut verification altyapısını (citation_verifier, grounding_verifier, context_sufficiency)
yeniden kullanır. LLM olmadan çalışır; LLM varsa zenginleştirilmiş cevap üretir.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.brain.rag_answerer import RagAnswerer
from app.learning.question_generator import MasteryQuestion
from app.memory.sqlite_store import SqliteStore
from app.verification.citation_verifier import CitationVerifier
from app.verification.context_sufficiency import ContextSufficiencyClassifier
from app.verification.grounding_verifier import GroundingLevel, GroundingVerifier


@dataclass
class ExamAnswer:
    answer_id: str
    question_id: str
    test_id: str
    paper_id: str
    question_text: str
    question_type: str
    requires_abstention: bool
    answer_text: str
    cited_paper_ids: list[str] = field(default_factory=list)
    citation_score: float = 0.0
    grounding_score: float = 0.0
    context_sufficient: bool = False
    abstention_correct: bool = False
    hallucination_detected: bool = False
    passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_id": self.answer_id,
            "question_id": self.question_id,
            "test_id": self.test_id,
            "paper_id": self.paper_id,
            "answer_text": self.answer_text,
            "cited_paper_ids": self.cited_paper_ids,
            "citation_score": self.citation_score,
            "grounding_score": self.grounding_score,
            "context_sufficient": self.context_sufficient,
            "abstention_correct": self.abstention_correct,
            "hallucination_detected": self.hallucination_detected,
            "passed": self.passed,
        }


class RagExamRunner:
    """Soruları RAG sistemine sorar ve cevapları deterministik olarak doğrular."""

    def __init__(self, store: SqliteStore | None = None) -> None:
        self._store = store or SqliteStore()
        self._answerer = RagAnswerer()
        self._citation_v = CitationVerifier()
        self._grounding_v = GroundingVerifier()
        self._sufficiency = ContextSufficiencyClassifier()

    def run(self, questions: list[MasteryQuestion], paper_id: str) -> list[ExamAnswer]:
        """Her soru için RAG cevabı al ve doğrula."""
        return [self._run_one(q, paper_id) for q in questions]

    def _run_one(self, q: MasteryQuestion, paper_id: str) -> ExamAnswer:
        rag = self._answerer.answer(q.question_text)
        answer_text = rag.answer
        chunks = rag.sources

        cited_ids = list({c.paper_id for c in chunks})
        # LLM çevrimdışıyken answerer placeholder döndürür (llm_used=False); bu GERÇEK
        # akıl yürütme değil → no_answer say ki regular soru sahte "geçti" almasın (Kural 2).
        no_answer = (
            not answer_text.strip()
            or "No sources found" in answer_text
            or not getattr(rag, "llm_used", True)
        )

        # Abstention soruları: cevap VERMEMEK doğru davranıştır
        if q.requires_abstention:
            abstention_correct = no_answer or paper_id not in cited_ids
            return ExamAnswer(
                answer_id="ans_" + uuid.uuid4().hex[:12],
                question_id=q.question_id,
                test_id=q.test_id,
                paper_id=paper_id,
                question_text=q.question_text,
                question_type=q.question_type,
                requires_abstention=True,
                answer_text=answer_text,
                cited_paper_ids=cited_ids,
                abstention_correct=abstention_correct,
                passed=abstention_correct,
            )

        # Bağlam yeterliliği
        sufficiency = self._sufficiency.classify(q.question_text, chunks)
        context_ok = sufficiency.can_answer

        # Citation skoru: kaç chunks paper_id ile eşleşiyor?
        paper_chunks = [c for c in chunks if c.paper_id == paper_id]
        cit_score = min(1.0, len(paper_chunks) / max(1, len(chunks))) if chunks else 0.0

        # Grounding skoru
        grounding_results = self._grounding_v.verify(answer_text, chunks)
        if grounding_results:
            supported = sum(
                1
                for g in grounding_results
                if g.level in (GroundingLevel.SUPPORTED, GroundingLevel.PARTIALLY_SUPPORTED)
            )
            gnd_score = supported / len(grounding_results)
            hallucination = any(g.level == GroundingLevel.UNSUPPORTED for g in grounding_results)
        else:
            gnd_score = 1.0 if not no_answer else 0.0
            hallucination = False

        # Geçti mi?
        passed = (
            not no_answer
            and context_ok
            and cit_score >= 0.3
            and gnd_score >= 0.4
            and not hallucination
        )

        return ExamAnswer(
            answer_id="ans_" + uuid.uuid4().hex[:12],
            question_id=q.question_id,
            test_id=q.test_id,
            paper_id=paper_id,
            question_text=q.question_text,
            question_type=q.question_type,
            requires_abstention=False,
            answer_text=answer_text,
            cited_paper_ids=cited_ids,
            citation_score=round(cit_score, 4),
            grounding_score=round(gnd_score, 4),
            context_sufficient=context_ok,
            hallucination_detected=hallucination,
            passed=passed,
        )
