"""Evaluation metrics fixed in SPEC section 14. Pure functions of backtest output."""

import math
from collections import Counter

import numpy as np
import pandas as pd

from trading.backtest import BacktestResult

TRADING_DAYS = 252


def daily_returns(result: BacktestResult) -> pd.Series:
    """Return on start-of-day equity for every session in the period (0 if no trade)."""
    return pd.Series([d.net_pnl / d.equity_before for d in result.days],
                     index=[d.session.date for d in result.days], dtype=float)


def equity_curve(result: BacktestResult) -> pd.Series:
    values = [result.start_equity] + [d.equity_before + d.net_pnl for d in result.days]
    return pd.Series(values, dtype=float)


def max_drawdown(equity: pd.Series) -> float:
    """Largest fall from a previous peak, as a positive fraction."""
    peaks = equity.cummax()
    return float(((peaks - equity) / peaks).max()) if len(equity) else 0.0


def sharpe(returns: pd.Series) -> float:
    sd = returns.std(ddof=1)
    if len(returns) < 2 or not sd or not math.isfinite(sd):
        return float("nan")
    return float(returns.mean() / sd * math.sqrt(TRADING_DAYS))


def bootstrap_sharpe_ci(returns: pd.Series, n: int = 2000, seed: int = 0) -> tuple[float, float]:
    if len(returns) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    x = returns.to_numpy()
    samples = x[rng.integers(0, len(x), size=(n, len(x)))]
    sd = samples.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.where(sd > 0, samples.mean(axis=1) / sd * math.sqrt(TRADING_DAYS), np.nan)
    s = s[np.isfinite(s)]
    if not len(s):
        return float("nan"), float("nan")
    return float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))


def summarize(result: BacktestResult, top_n: int = 10) -> dict:
    trades = result.trades
    pnl = np.array([t.net_pnl for t in trades], dtype=float)
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    rets = daily_returns(result)
    session_minutes = sum(d.session.regular_minutes for d in result.days)
    top = np.sort(pnl)[::-1][:top_n]
    total_pnl = float(pnl.sum())
    by_year = {}
    for year, r in rets.groupby([d.year for d in rets.index]):
        by_year[int(year)] = {
            "net_return": float((1 + r).prod() - 1),
            "trades": sum(1 for t in trades if t.date.year == year),
        }
    lo, hi = bootstrap_sharpe_ci(rets)
    return {
        "sessions": len(result.days),
        "trades": len(trades),
        "skips": dict(Counter(d.skip_reason for d in result.days if d.skip_reason)),
        "net_return": result.end_equity / result.start_equity - 1,
        "net_pnl": total_pnl,
        "mean_return_per_trade": float(np.mean([t.net_pnl / t.equity_before for t in trades]))
        if trades else float("nan"),
        "max_drawdown": max_drawdown(equity_curve(result)),
        "time_in_market": sum(t.minutes_held for t in trades) / session_minutes
        if session_minutes else 0.0,
        "avg_notional_to_equity": float(np.mean([t.notional / t.equity_before for t in trades]))
        if trades else 0.0,
        "win_rate": len(wins) / len(pnl) if len(pnl) else float("nan"),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
        "sharpe": sharpe(rets),
        "sharpe_ci95": [lo, hi],
        "by_year": by_year,
        f"top{top_n}_pnl": float(top.sum()),
        f"pnl_without_top{top_n}": total_pnl - float(top.sum()),
        f"top{top_n}_share_of_pnl": float(top.sum() / total_pnl) if total_pnl > 0 else None,
        "exit_reasons": dict(Counter(t.exit_reason for t in trades)),
        "flagged_trades": sum(1 for t in trades if t.flags),
    }


def random_direction_returns(long_rets: np.ndarray, short_rets: np.ndarray,
                             n_runs: int = 10000, seed: int = 0) -> np.ndarray:
    """Compounded net return of n_runs coin-flip direction sequences.

    long_rets / short_rets: per-day returns on equity if long / short on each
    day the strategy had a valid signal (same days, sizing, stop and costs).
    """
    rng = np.random.default_rng(seed)
    pick_long = rng.random((n_runs, len(long_rets))) < 0.5
    r = np.where(pick_long, long_rets, short_rets)
    return np.prod(1 + r, axis=1) - 1


def percentile_of(value: float, distribution: np.ndarray) -> float:
    return float((distribution < value).mean() * 100)
