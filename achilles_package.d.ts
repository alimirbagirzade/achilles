/**
 * Achilles Package (.achpkg) TypeScript type definitions.
 *
 * An .achpkg file is a JSON document produced by `achilles export-package`.
 * It bundles a trading strategy as Pine Script + Python code along with
 * backtest results so the Entropia front-end can load, display and simulate it.
 *
 * Usage (Node / browser):
 *   const pkg: AchillesPackage = JSON.parse(fs.readFileSync("strategy.achpkg", "utf-8"));
 */

// ---------------------------------------------------------------------------
// Indicator definition
// ---------------------------------------------------------------------------

/** A single indicator used in the strategy. */
export interface IndicatorSpec {
  /** Short identifier, e.g. "ema_fast" */
  name: string;
  /** Indicator type, e.g. "EMA" | "SMA" | "RSI" | "ATR" | "MACD" | "BB" */
  indicator: string;
  /** Look-back period (number of bars) */
  period: number;
  /** DataFrame column that stores the computed values */
  column: string;
}

// ---------------------------------------------------------------------------
// Cost assumptions
// ---------------------------------------------------------------------------

/** Transaction cost assumptions embedded in the strategy. */
export interface CostSpec {
  /** Per-trade commission as a decimal fraction, e.g. 0.001 = 0.1% */
  commission: number;
  /** Round-trip slippage as a decimal fraction, e.g. 0.0005 */
  slippage: number;
}

// ---------------------------------------------------------------------------
// Backtest metrics
// ---------------------------------------------------------------------------

/**
 * Subset of backtest metrics attached to the package.
 * All fields are optional — only those computed for the latest backtest are set.
 */
export interface BacktestMetrics {
  /** Total return as a percentage, e.g. 23.4 means +23.4% */
  total_return_pct?: number;
  /** Annualised Sharpe ratio */
  sharpe?: number;
  /** Maximum peak-to-trough drawdown as a percentage (negative), e.g. -18.5 */
  max_drawdown_pct?: number;
  /** Total number of completed trades */
  n_trades?: number;
  /** Win rate as a percentage, e.g. 54.3 means 54.3% winning trades */
  win_rate_pct?: number;
  /** Sortino ratio */
  sortino?: number;
  /** Profit factor (gross profit / gross loss) */
  profit_factor?: number;
  /** Annualised return as a percentage */
  annual_return_pct?: number;
  /** Additional arbitrary metrics produced by the backtester */
  [key: string]: number | undefined;
}

// ---------------------------------------------------------------------------
// Code bundle
// ---------------------------------------------------------------------------

/** The two code representations bundled in the package. */
export interface CodeBundle {
  /**
   * TradingView Pine Script v5 source code.
   * Paste directly into the Pine Script editor.
   */
  pine: string;
  /**
   * Python module source code.
   * Exposes `compute_signals(df: pd.DataFrame) -> pd.DataFrame`.
   */
  python: string;
}

// ---------------------------------------------------------------------------
// Root document
// ---------------------------------------------------------------------------

/** Verdict returned by the Achilles evaluator after backtesting. */
export type BacktestVerdict = "pass" | "fail" | "inconclusive" | null;

/**
 * Root structure of an Achilles Package file (.achpkg).
 *
 * @example
 * ```ts
 * import type { AchillesPackage } from "./achilles_package";
 *
 * async function loadPackage(url: string): Promise<AchillesPackage> {
 *   const res = await fetch(url);
 *   return res.json() as Promise<AchillesPackage>;
 * }
 * ```
 */
export interface AchillesPackage {
  /** Format version — always "1" for the current schema. */
  achilles_package_version: string;

  /** Human-readable strategy name, e.g. "MomentumVolatilityFilter_v1". */
  name: string;

  /** Semantic version of this specific package build, e.g. "1.0.0". */
  version: string;

  /**
   * Package content type.
   * - `"strategy"` — entry + exit rules with cost assumptions
   * - `"indicator"` — standalone indicator (no trade rules)
   */
  type: "strategy" | "indicator";

  /** Origin system that produced this package. Always `"achilles_research"`. */
  source: string;

  /** ISO-8601 UTC timestamp of when the package was exported. */
  created_at: string;

  /**
   * Result of the last Achilles backtest evaluation.
   * `null` when no backtest has been run yet.
   */
  backtest_verdict: BacktestVerdict;

  /**
   * Key performance metrics from the last backtest.
   * Empty object `{}` when no backtest has been run.
   */
  backtest_metrics: BacktestMetrics;

  /** Pine Script v5 and Python source code. */
  code: CodeBundle;
}

// ---------------------------------------------------------------------------
// Convenience helpers (re-exports for consumers)
// ---------------------------------------------------------------------------

export type { AchillesPackage as default };
