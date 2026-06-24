"""Regresyon çalıştırıcı testleri."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.evals.answer_eval import AnswerEvalResult, AnswerEvaluator
from app.evals.golden_dataset import GoldenDataset
from app.evals.regression_runner import RegressionRunner
from app.evals.retrieval_eval import RetrievalEvalResult, RetrievalEvaluator


def _mock_retrieval_eval(questions: list) -> list:
    return [
        RetrievalEvalResult(
            question_id=q.question_id,
            recall_5=0.0,
            recall_10=0.0,
            precision_5=0.0,
            mrr=0.0,
            ndcg=0.0,
        )
        for q in questions
    ]


def _mock_answer_eval(question, answer_text, chunks) -> AnswerEvalResult:
    return AnswerEvalResult(
        question_id=question.question_id,
        citation_accuracy=1.0,
        grounding_score=1.0,
        abstention_correct=True,
        hallucination_detected=False,
    )


def test_runner_with_sample_data() -> None:
    """GoldenDataset.get_sample_questions() + mock değerlendiriciler → hatasız çalışmalı."""
    mock_retrieval = MagicMock(spec=RetrievalEvaluator)
    mock_retrieval.evaluate.side_effect = _mock_retrieval_eval

    mock_answer = MagicMock(spec=AnswerEvaluator)
    mock_answer.evaluate.side_effect = _mock_answer_eval

    dataset = GoldenDataset()
    runner = RegressionRunner(dataset, mock_retrieval, mock_answer)
    result = runner.run()

    assert isinstance(result, dict)
    assert "passed" in result
    assert "failed" in result
    assert "results" in result
    assert isinstance(result["results"], list)
    # 5 örnek soru olmalı
    assert len(result["results"]) == 5
    # passed + failed = toplam
    assert result["passed"] + result["failed"] == 5


def test_runner_result_keys() -> None:
    """Her sonuç öğesi gerekli anahtarları içermeli."""
    mock_retrieval = MagicMock(spec=RetrievalEvaluator)
    mock_retrieval.evaluate.side_effect = _mock_retrieval_eval

    mock_answer = MagicMock(spec=AnswerEvaluator)
    mock_answer.evaluate.side_effect = _mock_answer_eval

    dataset = GoldenDataset()
    runner = RegressionRunner(dataset, mock_retrieval, mock_answer)
    result = runner.run()

    required_keys = {
        "question_id",
        "question",
        "recall_5",
        "recall_10",
        "precision_5",
        "mrr",
        "ndcg",
        "passed",
    }
    for item in result["results"]:
        assert required_keys.issubset(item.keys()), (
            f"Eksik anahtarlar: {required_keys - item.keys()}"
        )


def test_runner_uses_injected_dataset_questions() -> None:
    """Enjekte edilen GoldenDataset'in soruları kullanılmalı (eskiden ctor'a verilen dataset
    sessizce yok sayılıp her zaman statik get_sample_questions() koşuluyordu)."""
    from app.evals.golden_dataset import GoldenQuestion

    custom = [
        GoldenQuestion(
            question_id="custom_001",
            question_text="özel enjekte soru",
            domain="general",
            expected_answer="",
            expected_source_ids=[],
            expected_chunk_ids=[],
            answer_type="factual",
            difficulty="easy",
        )
    ]
    mock_retrieval = MagicMock(spec=RetrievalEvaluator)
    mock_retrieval.evaluate.side_effect = _mock_retrieval_eval
    mock_answer = MagicMock(spec=AnswerEvaluator)
    mock_answer.evaluate.side_effect = _mock_answer_eval

    runner = RegressionRunner(GoldenDataset(custom), mock_retrieval, mock_answer)
    result = runner.run()

    # 5 statik örnek DEĞİL, enjekte edilen tek özel soru koşulmalı.
    assert len(result["results"]) == 1
    assert result["results"][0]["question_id"] == "custom_001"
