"""QueryExpander testleri — kural tabanlı sorgu genişletme."""

from __future__ import annotations

from app.brain.query_expander import QueryExpander


def test_expander_returns_multiple_queries() -> None:
    """expand() en az 3 alternatif + orijinal sorguyu döndürmeli."""
    expander = QueryExpander()
    results = expander.expand("backtest strategy")
    assert len(results) >= 4, f"Beklenen >= 4 sorgu, alınan: {len(results)}"
    assert results[0] == "backtest strategy", "İlk eleman orijinal sorgu olmalı"


def test_expander_trading_domain() -> None:
    """Finans alanı sorgusu: ATR veya regime terimi içermeli."""
    expander = QueryExpander()
    results = expander.expand("volatilite filtreli momentum")
    # Tüm sonuçları küçük harfe çevir
    all_text = " ".join(r.lower() for r in results)
    assert (
        "atr" in all_text
        or "regime" in all_text
        or "volatility" in all_text
        or "clustering" in all_text
    ), f"Trading terimleri beklendi, alınan: {results}"


def test_expander_no_duplicates() -> None:
    """Aynı sorgu iki kez listelenmemeli."""
    expander = QueryExpander()
    results = expander.expand("momentum")
    lower_results = [r.lower() for r in results]
    assert len(lower_results) == len(set(lower_results)), "Tekrar eden sorgular var"


def test_expander_minimum_three_alternatives() -> None:
    """Bilinmeyen alan için bile 3+ alternatif üretilmeli."""
    expander = QueryExpander()
    results = expander.expand("completely unknown niche term xyz")
    # Orijinal + en az 3 alternatif
    assert len(results) >= 4, f"Minimum 4 sonuç beklendi, alınan: {len(results)}"
