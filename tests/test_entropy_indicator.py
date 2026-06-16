"""Entropi göstergesi testleri — yönsel ikili Shannon entropisi (look-ahead'siz, [0,1])."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.trading.indicators import compute_indicator, entropy
from app.verification.exams.registry import get_spec, list_specs


def test_aralik_0_1() -> None:
    rng = np.random.default_rng(0)
    close = pd.Series(100 + rng.standard_normal(200).cumsum())
    h = entropy(close, 10).dropna()
    assert (h >= -1e-9).all()
    assert (h <= 1 + 1e-9).all()


def test_alternating_maks_belirsizlik() -> None:
    # Tam dönüşümlü up/down → her pencerede p=0.5 → entropi 1.0
    close = pd.Series([100.0, 101.0, 100.0, 101.0, 100.0, 101.0, 100.0, 101.0])
    h = entropy(close, 4).dropna()
    assert np.allclose(h.to_numpy(), 1.0, atol=1e-9)


def test_monoton_trend_sifir_entropi() -> None:
    # Sürekli artış → tam-trend penceresi p=1 → entropi 0
    close = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    h = entropy(close, 3)
    assert abs(h.iloc[-1]) < 1e-12  # son pencere tamamen yukarı → 0


def test_warmup_nan() -> None:
    close = pd.Series([100.0, 101.0, 102.0, 101.0, 103.0])
    h = entropy(close, 3)
    assert h.iloc[:2].isna().all()  # ilk period-1 değer tanımsız
    assert not h.iloc[2:].isna().any()


def test_compute_indicator_entropy() -> None:
    close = pd.Series(100 + np.random.default_rng(7).standard_normal(50).cumsum())
    df = pd.DataFrame({"close": close})
    pd.testing.assert_series_equal(compute_indicator("ENTROPY", df, 8), entropy(close, 8))


def test_registry_entropy_kayitli() -> None:
    spec = get_spec("ENTROPY")
    assert spec.name == "ENTROPY"
    assert "ENTROPY" in {s.name for s in list_specs()}
