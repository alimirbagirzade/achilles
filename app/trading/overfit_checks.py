"""Overfit / robustness checks for backtest results.

These are guardrails, not guarantees. They encode the project's skepticism:
too few trades, implausible profit factor, or catastrophic drawdown all reduce
confidence regardless of headline return.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.trading.backtester import BacktestMetrics, run_backtest
from app.trading.strategy_ir import StrategyIR


@dataclass
class OverfitReport:
    warnings: list[str]
    in_sample: BacktestMetrics | None = None
    out_sample: BacktestMetrics | None = None

    @property
    def degradation_pct(self) -> float | None:
        if not (self.in_sample and self.out_sample):
            return None
        a = self.in_sample.total_return_pct
        b = self.out_sample.total_return_pct
        if a == 0:
            return None
        return round((a - b) / abs(a) * 100, 2)


def static_checks(metrics: BacktestMetrics, min_trades: int = 30) -> list[str]:
    warnings: list[str] = []
    if metrics.n_trades < min_trades:
        warnings.append(
            f"Çok az işlem ({metrics.n_trades} < {min_trades}); istatistiksel anlam zayıf."
        )
    if metrics.profit_factor > 5 and metrics.n_trades < 100:
        warnings.append(
            f"Şüpheli yüksek profit factor ({metrics.profit_factor}); overfit ihtimali."
        )
    if metrics.max_drawdown_pct < -50:
        warnings.append(f"Aşırı drawdown ({metrics.max_drawdown_pct}%); risk kabul edilemez.")
    if metrics.sharpe > 4:
        warnings.append(f"Gerçekçi olmayan Sharpe ({metrics.sharpe}); look-ahead/leak kontrol et.")
    return warnings


def in_out_of_sample(df: pd.DataFrame, ir: StrategyIR, split: float = 0.7) -> OverfitReport:
    n = len(df)
    cut = int(n * split)
    in_df, out_df = df.iloc[:cut], df.iloc[cut:]

    in_res = run_backtest(in_df, ir)
    out_res = run_backtest(out_df, ir)

    warnings = static_checks(out_res.metrics)
    deg_in = in_res.metrics.total_return_pct
    deg_out = out_res.metrics.total_return_pct
    if deg_in > 0 and deg_out < 0:
        warnings.append("Örneklem-içi pozitif, örneklem-dışı negatif: klasik overfit işareti.")

    return OverfitReport(warnings=warnings, in_sample=in_res.metrics, out_sample=out_res.metrics)
