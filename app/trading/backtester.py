"""Backtest engine for Strategy IR.

A transparent, vectorized, long/flat backtester:
- computes required indicator columns
- evaluates entry/exit rules to a position series (no look-ahead: signals on
  bar t act on bar t+1's open->close return)
- applies commission + slippage per position change
- reports return, Sharpe, Sortino, max drawdown, profit factor, win rate, trades

This is deliberately simple and auditable. It is NOT a live trading engine.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.config import get_settings
from app.memory.sqlite_store import SqliteStore
from app.trading.indicators import compute_indicator
from app.trading.strategy_ir import StrategyIR, parse_rule

_BARS_PER_YEAR = {
    "1m": 525600,
    "5m": 105120,
    "15m": 35040,
    "1h": 8760,
    "4h": 2190,
    "1d": 252,
}


@dataclass
class BacktestMetrics:
    n_trades: int
    total_return_pct: float
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    profit_factor: float
    win_rate_pct: float
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "n_trades": self.n_trades,
            "total_return_pct": self.total_return_pct,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "max_drawdown_pct": self.max_drawdown_pct,
            "profit_factor": self.profit_factor,
            "win_rate_pct": self.win_rate_pct,
            **self.extra,
        }


def _compute_columns(df: pd.DataFrame, ir: StrategyIR) -> pd.DataFrame:
    out = df.copy()
    # Explicitly listed indicators
    computed = {ind.column for ind in ir.indicators}
    for ind in ir.indicators:
        out[ind.column] = compute_indicator(ind.name, df, ind.period)
    # Auto-compute any indicator column referenced in rules but not listed
    for col in ir.required_columns() - computed - set(df.columns):
        # col format: "{name}_{period}" e.g. ema_50 → EMA period 50
        parts = col.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            name, period = parts[0].upper(), int(parts[1])
            try:
                out[col] = compute_indicator(name, df, period)
            except Exception:
                out[col] = np.nan
    return out


def _eval_rules(df: pd.DataFrame, rules: list[str]) -> pd.Series:
    if not rules:
        return pd.Series(False, index=df.index)
    mask = pd.Series(True, index=df.index)
    ops = {
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }
    for rule in rules:
        lhs, op, rhs = parse_rule(rule)
        left = df[lhs]
        right = float(rhs) if rhs.replace(".", "", 1).lstrip("-").isdigit() else df[rhs]
        mask &= ops[op](left, right)
    return mask.fillna(False)


def _position_series(df: pd.DataFrame, ir: StrategyIR) -> pd.Series:
    entry = _eval_rules(df, ir.entry_rules)
    exit_ = _eval_rules(df, ir.exit_rules)
    pos = np.zeros(len(df))
    holding = 0
    for i in range(len(df)):
        if holding == 0 and entry.iloc[i]:
            holding = 1
        elif holding == 1 and exit_.iloc[i]:
            holding = 0
        pos[i] = holding
    return pd.Series(pos, index=df.index)


def _metrics(returns: pd.Series, position: pd.Series, timeframe: str) -> BacktestMetrics:
    equity = (1 + returns).cumprod()
    total_return = float(equity.iloc[-1] - 1) * 100 if len(equity) else 0.0

    ann = _BARS_PER_YEAR.get(timeframe, 35040)
    mean, std = returns.mean(), returns.std()
    sharpe = float((mean / std) * np.sqrt(ann)) if std and not np.isnan(std) else 0.0
    downside = returns[returns < 0].std()
    sortino = (
        float((mean / downside) * np.sqrt(ann)) if downside and not np.isnan(downside) else 0.0
    )

    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    max_dd = float(dd.min()) * 100 if len(dd) else 0.0

    # trades = transitions 0->1
    trades = int(((position.shift(1).fillna(0) == 0) & (position == 1)).sum())
    trade_rets = returns[position.shift(1).fillna(0) == 1]
    wins = trade_rets[trade_rets > 0].sum()
    losses = -trade_rets[trade_rets < 0].sum()
    profit_factor = float(wins / losses) if losses > 0 else (float("inf") if wins > 0 else 0.0)
    win_rate = float((trade_rets > 0).mean() * 100) if len(trade_rets) else 0.0

    return BacktestMetrics(
        n_trades=trades,
        total_return_pct=round(total_return, 4),
        sharpe=round(sharpe, 4),
        sortino=round(sortino, 4),
        max_drawdown_pct=round(max_dd, 4),
        profit_factor=round(profit_factor, 4) if np.isfinite(profit_factor) else 999.0,
        win_rate_pct=round(win_rate, 4),
        extra={"final_equity": round(float(equity.iloc[-1]) if len(equity) else 1.0, 4)},
    )


@dataclass
class BacktestResult:
    ir: StrategyIR
    metrics: BacktestMetrics
    equity_curve: pd.Series


def run_backtest(df: pd.DataFrame, ir: StrategyIR) -> BacktestResult:
    enriched = _compute_columns(df, ir)
    position = _position_series(enriched, ir)

    bar_ret = enriched["close"].pct_change().fillna(0.0)
    # no look-ahead: yesterday's position earns today's return
    strat_ret = position.shift(1).fillna(0.0) * bar_ret

    # transaction costs on position changes
    turnover = position.diff().abs().fillna(0.0)
    cost = turnover * (ir.costs.commission + ir.costs.slippage)
    net_ret = strat_ret - cost

    metrics = _metrics(net_ret, position, ir.timeframe)
    equity = (1 + net_ret).cumprod()
    return BacktestResult(ir=ir, metrics=metrics, equity_curve=equity)


def persist_backtest(
    result: BacktestResult,
    data_file: str,
    *,
    store: SqliteStore | None = None,
    verdict: str | None = None,
    notes: str | None = None,
) -> str:
    store = store or SqliteStore()
    settings = get_settings()
    ir = result.ir
    m = result.metrics

    # ensure strategy row exists
    strategy_id = f"strat_{uuid.uuid4().hex[:10]}"
    store.save_strategy(
        strategy_id=strategy_id,
        name=ir.name,
        market=ir.market,
        timeframe=ir.timeframe,
        ir_json=ir.model_dump_json(),
        origin="manual",
    )

    backtest_id = f"bt_{uuid.uuid4().hex[:10]}"
    store.save_backtest(
        backtest_id=backtest_id,
        strategy_id=strategy_id,
        data_file=data_file,
        period_start=str(result.equity_curve.index[0]) if len(result.equity_curve) else None,
        period_end=str(result.equity_curve.index[-1]) if len(result.equity_curve) else None,
        n_trades=m.n_trades,
        total_return_pct=m.total_return_pct,
        sharpe=m.sharpe,
        sortino=m.sortino,
        max_drawdown_pct=m.max_drawdown_pct,
        profit_factor=m.profit_factor,
        win_rate_pct=m.win_rate_pct,
        metrics_json=json.dumps(m.to_dict()),
        verdict=verdict,
        notes=notes,
    )

    report = settings.reports_dir / "backtests" / f"{ir.name}_{backtest_id}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(
            {"strategy": ir.model_dump(), "metrics": m.to_dict(), "verdict": verdict},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return backtest_id
