"""Technical indicators.

Implemented in pure pandas/numpy so the backtest works even if the optional
``ta`` package is not installed. Functions return pandas Series aligned to the
input index.
"""

from __future__ import annotations

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
    raise ValueError(f"Bilinmeyen gösterge: {name}")
