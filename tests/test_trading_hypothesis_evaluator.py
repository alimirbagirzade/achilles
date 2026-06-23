"""Trading hipotez değerlendiricisi testleri (CLAUDE.md Kural 1-4 denetimi, offline)."""

from __future__ import annotations

from app.evals.trading_hypothesis_evaluator import evaluate_hypothesis, evaluate_many

_GOOD = {
    "hypothesis_text": (
        "Yüksek volatilite rejiminde basit momentum sinyalleri zayıflayabilir; bu hipotez "
        "likidite filtresiyle backtest edilerek test edilmeli. Örneklem-dışı (out-of-sample) "
        "doğrulama yapılmalı ve komisyon + slippage maliyetleri dahil edilmeli. Pozisyon "
        "riski stop-loss ile sınırlanmalı."
    )
}


def test_good_hypothesis_is_candidate() -> None:
    res = evaluate_hypothesis(_GOOD)
    assert res.verdict == "candidate"
    assert res.score == 1.0
    assert all(res.checklist.values())


def test_advice_language_rejected() -> None:
    res = evaluate_hypothesis("Bu strateji %100 kazandırır, garanti kârlı, hemen al.")
    assert res.verdict == "rejected"
    assert res.checklist["no_advice"] is False
    assert any("Kural 1" in w for w in res.warnings)


def test_guaranteed_english_rejected() -> None:
    res = evaluate_hypothesis(
        "This is a risk-free, guaranteed, surefire strategy that always wins."
    )
    assert res.verdict == "rejected"
    assert res.checklist["no_advice"] is False


def test_missing_costs_needs_revision() -> None:
    text = (
        "Momentum zayıflayabilir; backtest ile test edilmeli, örneklem-dışı doğrula, "
        "riski stop-loss ile sınırla."
    )
    res = evaluate_hypothesis(text)
    assert res.verdict == "needs_revision"
    assert res.checklist["costs"] is False
    assert res.checklist["testable"] is True


def test_missing_oos_needs_revision() -> None:
    text = (
        "Momentum zayıflayabilir; backtest ile test edilmeli, komisyon ve slippage dahil, "
        "risk stop-loss ile yönetilmeli."
    )
    res = evaluate_hypothesis(text)
    assert res.verdict == "needs_revision"
    assert res.checklist["out_of_sample"] is False


def test_non_testable_directive_rejected() -> None:
    res = evaluate_hypothesis("Altını şimdi al, fiyat yükselecek.")
    assert res.verdict == "rejected"
    assert res.checklist["testable"] is False


def test_dict_with_separate_fields() -> None:
    res = evaluate_hypothesis(
        {
            "title": "Volatilite-momentum etkileşimi",
            "hypothesis_text": "Eğer volatilite yüksekse momentum zayıflar ise test edilmeli.",
            "risk_notes": "drawdown ve stop-loss dikkate alınmalı",
            "assumptions": ["komisyon ve slippage dahil", "örneklem-dışı doğrulama"],
        }
    )
    assert res.checklist["costs"] is True
    assert res.checklist["out_of_sample"] is True
    assert res.checklist["risk_noted"] is True


def test_evaluate_many_assigns_ids() -> None:
    res = evaluate_many([_GOOD, "garanti %100 kâr"])
    assert len(res) == 2
    assert res[0].hypothesis_id == "hyp_0"
    assert res[1].verdict == "rejected"


def test_advice_regex_variants_rejected() -> None:
    # tireli/fiil/boşluklu varyantlar da yakalanmalı (gate kör noktası kapatıldı)
    for text in (
        "This is a sure-fire strategy.",
        "This will guarantee profits next quarter.",
        "You simply can t lose with this setup.",
    ):
        res = evaluate_hypothesis(text)
        assert res.checklist["no_advice"] is False, text
        assert res.verdict == "rejected", text
