"""Adapter eval verdict mantığı — v5 disiplin-regresyon koruması (küçük-n accept yasağı).

v5 dersi: eval n=1 örnekle 'accept' demişti (istatistiksel temel yok). `_decide_verdict`
artık min_n altında 'accept' vermez; regresyon ise her n'de raporlanır (güvenli yön).
Tamamen çevrimdışı — saf karar fonksiyonu, torch gerektirmez.
"""

from __future__ import annotations

from app.training.adapter_eval import _MIN_EVAL_N, _decide_verdict


def test_regression_rejected_at_any_n() -> None:
    # adapter base'in altında → tek örnekte bile reject (güvenli yön)
    assert _decide_verdict(0.8, 0.5, n=1) == "reject"
    assert _decide_verdict(0.8, 0.5, n=100) == "reject"


def test_small_n_improvement_is_inconclusive_not_accept() -> None:
    # v5 senaryosu: tek soruda adapter daha iyi görünür → ASLA accept
    assert _decide_verdict(0.0, 1.0, n=1) == "inconclusive"
    assert _decide_verdict(0.5, 0.9, n=_MIN_EVAL_N - 1) == "inconclusive"


def test_sufficient_n_improvement_accepts() -> None:
    assert _decide_verdict(0.5, 0.9, n=_MIN_EVAL_N) == "accept"
    assert _decide_verdict(0.5, 0.6, n=20) == "accept"


def test_equality_is_inconclusive() -> None:
    assert _decide_verdict(0.7, 0.7, n=50) == "inconclusive"


def test_custom_min_n_threshold() -> None:
    assert _decide_verdict(0.5, 0.9, n=8, min_n=10) == "inconclusive"
    assert _decide_verdict(0.5, 0.9, n=10, min_n=10) == "accept"
