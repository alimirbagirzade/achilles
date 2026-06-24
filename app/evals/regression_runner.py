"""Regression test runner — automated testing against the golden dataset.

Can be run standalone; tests the full pipeline with sample questions.
"""

from __future__ import annotations

from app.evals.answer_eval import AnswerEvaluator
from app.evals.golden_dataset import GoldenDataset
from app.evals.retrieval_eval import RetrievalEvaluator

# Bir sorunun "geçti" sayılması için minimum recall@5 (gerilemeyi yakalamak için).
_RECALL_PASS_THRESHOLD = 0.5


class RegressionRunner:
    """Altın veri setiyle retrieval ve cevap kalitesini test eden koşucu.

    Tüm soruları çalıştırır, özet rapor üretir.
    """

    def __init__(
        self,
        dataset: GoldenDataset,
        retrieval_eval: RetrievalEvaluator,
        answer_eval: AnswerEvaluator,
    ) -> None:
        self._dataset = dataset
        self._retrieval_eval = retrieval_eval
        self._answer_eval = answer_eval

    def run(self) -> dict:
        """Tüm örnek sorular üzerinde değerlendirme çalıştır.

        Returns:
            {"passed": int, "failed": int, "results": list} formatında özet.
        """
        # Enjekte edilen veri setinin sorularını kullan (eskiden statik get_sample_questions()
        # çağrılıp ctor'a verilen `dataset` sessizce yok sayılıyordu). Varsayılan GoldenDataset
        # zaten örnek sorulara düşer → davranış geriye uyumlu.
        questions = self._dataset.questions
        retrieval_results = self._retrieval_eval.evaluate(questions)

        results = []
        passed = 0
        failed = 0

        for q, r_result in zip(questions, retrieval_results, strict=False):
            # Retrieval değerlendirme: anlamlı eşik (recall_5 ∈ [0,1] olduğundan
            # ">= 0.0" totoloji idi → hiçbir gerilemeyi yakalamazdı, Kural 2 ihlali).
            retrieval_ok = r_result.recall_5 >= _RECALL_PASS_THRESHOLD

            # Cevap değerlendirme (boş cevapla mock)
            answer_result = self._answer_eval.evaluate(
                question=q,
                answer_text="",
                chunks=[],
            )

            item = {
                "question_id": q.question_id,
                "question": q.question_text[:60],
                "recall_5": round(r_result.recall_5, 3),
                "recall_10": round(r_result.recall_10, 3),
                "precision_5": round(r_result.precision_5, 3),
                "mrr": round(r_result.mrr, 3),
                "ndcg": round(r_result.ndcg, 3),
                "citation_accuracy": round(answer_result.citation_accuracy, 3),
                "grounding_score": round(answer_result.grounding_score, 3),
                "abstention_correct": answer_result.abstention_correct,
                "hallucination_detected": answer_result.hallucination_detected,
                "passed": retrieval_ok,
            }
            results.append(item)

            if retrieval_ok:
                passed += 1
            else:
                failed += 1

        self._print_summary(passed, failed, results)

        return {"passed": passed, "failed": failed, "results": results}

    def _print_summary(self, passed: int, failed: int, results: list[dict]) -> None:
        """Özet raporu yazdır."""
        total = passed + failed
        print(f"\n{'=' * 60}")
        print(f"RAG Regresyon Testi — {total} soru")
        print(f"  Geçen: {passed} | Kalan: {failed}")
        print(f"{'=' * 60}")
        for r in results:
            status = "OK" if r["passed"] else "FAIL"
            print(
                f"  [{status}] {r['question_id']} "
                f"R@5={r['recall_5']:.2f} "
                f"MRR={r['mrr']:.2f} "
                f"Grnd={r['grounding_score']:.2f}"
            )
        print(f"{'=' * 60}\n")


if __name__ == "__main__":  # pragma: no cover
    from unittest.mock import MagicMock

    # Mock objelerle hızlı test
    mock_retrieval_eval = MagicMock(spec=RetrievalEvaluator)
    mock_retrieval_eval.evaluate.return_value = []

    mock_answer_eval = MagicMock(spec=AnswerEvaluator)
    mock_answer_eval.evaluate.return_value = MagicMock(
        question_id="mock",
        citation_accuracy=1.0,
        grounding_score=1.0,
        abstention_correct=True,
        hallucination_detected=False,
    )

    dataset = GoldenDataset()
    runner = RegressionRunner(dataset, mock_retrieval_eval, mock_answer_eval)
    summary = runner.run()
    print(f"Özet: {summary['passed']} geçti, {summary['failed']} kaldı")
