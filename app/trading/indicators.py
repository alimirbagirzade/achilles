"""Technical indicators.

Implemented in pure pandas/numpy so the backtest works even if the optional
``ta`` package is not installed. Functions return pandas Series aligned to the
input index.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    # Kayıpsız pencere (avg_loss==0 & avg_gain>0) = güçlü yükseliş → RSI=100 (aşırı-alım).
    # replace(0→NaN) yüzünden NaN kalıp fillna(50) ile yanlışlıkla 50 oluyordu. Düz seri
    # (gain=loss=0) ve gerçek warmup (bar 0, diff=NaN) → 50 (nötr konvansiyon).
    out = out.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    return out.fillna(50.0)


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(
        axis=1
    )
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def bollinger(
    close: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = sma(close, period)
    std = close.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def _binary_entropy(p: pd.Series) -> pd.Series:
    """İkili Shannon entropisi H(p) = -(p·log2 p + (1-p)·log2(1-p)); aralık [0,1]."""
    p_clip = p.clip(0.0, 1.0)
    q = 1.0 - p_clip
    out = pd.Series(0.0, index=p.index, dtype=float)
    mask = (p_clip > 0.0) & (p_clip < 1.0)
    out[mask] = -(p_clip[mask] * np.log2(p_clip[mask]) + q[mask] * np.log2(q[mask]))
    out[p.isna()] = np.nan  # warmup penceresi tanımsız
    return out


def entropy(close: pd.Series, period: int = 14) -> pd.Series:
    """Yönsel ikili Shannon entropisi — bir penceredeki yön belirsizliği (rejim sinyali).

    Pencere içindeki yukarı-hareket (close artışı) oranı p ise:
    H = -(p·log2 p + (1-p)·log2(1-p)), aralık [0,1]. p=0.5 → 1 (maks. belirsizlik /
    çalkantı / rejim geçişi), p=0 veya 1 → 0 (net trend). Yalnız geçmiş pencereyi
    kullanır (look-ahead yok). Markov rejim + entropi sentezinin yapı taşı.
    """
    delta = close.diff()
    up = (delta > 0).astype(float)
    p_up = up.rolling(period).mean()
    return _binary_entropy(p_up)


def _ordinal_codes(values: np.ndarray, order: int) -> np.ndarray:
    """Her t için [t-order+1..t] penceresinin ordinal (sıralama) desen kodu (0..order!-1).

    İlk ``order-1`` konum -1 (tanımsız). Kodlama Lehmer (faktöriyel sayı sistemi);
    eşit değerlerde 'stable' argsort → deterministik (CLAUDE.md Kural 6). Döngü yalnız
    küçük ``order`` üzerindedir, veri ekseni vektörizedir.
    """
    n = values.shape[0]
    codes = np.full(n, -1, dtype=np.int64)
    if n < order:
        return codes
    windows = np.lib.stride_tricks.sliding_window_view(values, order)  # (n-order+1, order)
    perms = np.argsort(windows, axis=1, kind="stable")  # ordinal desen
    idx = np.zeros(perms.shape[0], dtype=np.int64)
    for i in range(order):
        smaller = (perms[:, i + 1 :] < perms[:, i : i + 1]).sum(axis=1)
        idx += smaller * math.factorial(order - 1 - i)
    codes[order - 1 :] = idx
    return codes


def permutation_entropy(close: pd.Series, period: int = 14, order: int = 3) -> pd.Series:
    """Bandt-Pompe permütasyon entropisi (normalize [0,1]) — ordinal-desen karmaşıklığı.

    Her bar için son ``period`` ordinal deseni (gömme boyutu ``order``) sayılır; desen
    dağılımının Shannon entropisi log2(order!) ile normalize edilir. 0 = tam düzenli /
    öngörülebilir (monoton), 1 = maksimum karmaşıklık / rastgelelik. Yalnız geçmiş
    pencereyi kullanır (look-ahead yok). ENTROPY yön ORANINI yakalar; bu, ardışık fiyat
    seviyelerinin SIRALAMA yapısını — entropi+Markov sentezinin ikinci yapı taşı.
    """
    if order < 2:
        raise ValueError("permutation_entropy: order >= 2 olmalı")
    values = close.to_numpy(dtype=float)
    codes = _ordinal_codes(values, order)
    n_patterns = math.factorial(order)
    # one-hot: geçersiz (-1) satırlar tüm-sıfır → rolling sayımına katkı vermez.
    onehot = np.zeros((values.shape[0], n_patterns), dtype=float)
    valid = codes >= 0
    onehot[np.where(valid)[0], codes[valid]] = 1.0
    counts = pd.DataFrame(onehot, index=close.index).rolling(period).sum()
    total = counts.sum(axis=1)
    probs = counts.div(total, axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        logp = np.log2(probs.where(probs > 0))
    pe = -(probs * logp).sum(axis=1) / np.log2(n_patterns)
    pe[total < period] = np.nan  # tam pencere yoksa (yetersiz geçerli desen) tanımsız
    return pe


# Registry used by the strategy engine to compute indicators by name.
def compute_indicator(name: str, df: pd.DataFrame, period: int = 14) -> pd.Series:
    name = name.upper()
    if name == "EMA":
        return ema(df["close"], period)
    if name == "SMA":
        return sma(df["close"], period)
    if name == "RSI":
        return rsi(df["close"], period)
    if name == "ATR":
        return atr(df["high"], df["low"], df["close"], period)
    if name == "MACD":
        return macd(df["close"])[0]
    if name == "ENTROPY":
        return entropy(df["close"], period)
    if name == "PERMENTROPY":
        return permutation_entropy(df["close"], period)
    raise ValueError(f"Bilinmeyen gösterge: {name}")
