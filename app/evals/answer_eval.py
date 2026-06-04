"""Answer evaluator — measures citation, grounding, and abstention quality."""

from __future__ import annotations

from dataclasses import dataclass

from app.evals.golden_dataset import GoldenQuestion
from app.memory.retrieval_service import RetrievedChunk
from app.verification.abstention_policy import AbstentionPolicy
from app.verification.citation_verifier import CitationVerifier
from app.verification.confidence_scorer import ConfidenceReport
from app.verification.context_sufficiency import ContextSufficiencyClassifier
from app.verification.grounding_verifier import GroundingLevel, GroundingVerifier


@dataclass
class AnswerEvalResult:
    """Tek bir soru-cevap çifti için değerlendirme sonucu."""

    question_id: str
    citation_accuracy: float  # Geçerli atıf oranı
    grounding_score: float  # Dayanak skoru
    abstention_correct: bool  # Çekimser kalma kararı doğru mu?
    hallucination_detected: bool  # Desteksiz iddia var mı?


class AnswerEvaluator:
    """Cevap kalitesini çok boyutlu değerlendiren sınıf."""

    def __init__(
        self,
        citation_verifier: CitationVerifier,
        grounding_verifier: GroundingVerifier,
        abstention_policy: AbstentionPolicy,
    ) -> None:
        self._citation = citation_verifier
        self._grounding = grounding_verifier
        self._abstention = abstention_policy

    def evaluate(
        self,
        question: GoldenQuestion,
        answer_text: str,
        chunks: list[RetrievedChunk],
    ) -> AnswerEvalResult:
        """Bir soru için cevabı değerlendir.

        Args:
            question: Altın soru.
            answer_text: Değerlendirilecek cevap metni.
            chunks: Cevabın dayandığı chunk'lar.

        Returns:
            AnswerEvalResult nesnesi.
        """
        # Atıf doğrulaması
        citation_checks = self._citation.verify(answer_text, chunks)
        if citation_checks:
            cit_acc = sum(1 for c in citation_checks if c.exists) / len(citation_checks)
        else:
            cit_acc = 1.0  # Atıf yoksa nötr

        # Dayanak doğrulaması
        grounding_results = self._grounding.verify(answer_text, chunks)
        if grounding_results:
            supported = sum(
                1
                for g in grounding_results
                if g.level in (GroundingLevel.SUPPORTED, GroundingLevel.PARTIALLY_SUPPORTED)
            )
            gnd_score = supported / len(grounding_results)
            hallucination = any(g.level == GroundingLevel.UNSUPPORTED for g in grounding_results)
        else:
            gnd_score = 1.0
            hallucination = False

        # Bağlam yeterliliği
        sufficiency_classifier = ContextSufficiencyClassifier()
        sufficiency = sufficiency_classifier.classify(question.question_text, chunks)

        # Basit güven raporu oluştur (tam scorer olmadan)
        confidence_score = cit_acc * 0.4 + gnd_score * 0.6
        decision = (
            "abstain" if confidence_score < 0.4 else "warn" if confidence_score < 0.7 else "answer"
        )

        confidence = ConfidenceReport(
            score=confidence_score,
            context_score=1.0 if sufficiency.can_answer else 0.0,
            citation_score=cit_acc,
            grounding_score=gnd_score,
            has_contradictions=False,
            formula_integrity=1.0,
            decision=decision,
        )

        abstention_decision = self._abstention.decide(confidence, sufficiency)

        # Çekimser kalma doğruluğu
        if question.allow_abstention:
            # Çekimser kalması beklenen soruda çekimser kaldıysa doğru
            abstain_correct = abstention_decision.should_abstain
        else:
            # Cevap verilmesi gereken soruda cevap verdiyse doğru
            abstain_correct = not abstention_decision.should_abstain

        return AnswerEvalResult(
            question_id=question.question_id,
            citation_accuracy=round(cit_acc, 4),
            grounding_score=round(gnd_score, 4),
            abstention_correct=abstain_correct,
            hallucination_detected=hallucination,
        )
