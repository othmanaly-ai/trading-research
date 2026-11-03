"""Day-by-day simulation of experiment 001 (SPEC sections 5-10).

Leakage rule: at the decision time T the signal, sizing and data checks see
only bars whose interval ended at or before T (bar start + 1 minute <= T).
Fills always come from bars that start at or after T.
"""

import statistics
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from trading.costs import CostModel
from trading.risk import RiskLimits, RiskState, size_position
from trading.sessions import Session
from trading.strategies.intraday_momentum import MINUTE, Params, signal
from trading.validate import check_bars, has_problems

MISSING_EXIT_WINDOW = pd.Timedelta(minutes=10)


@dataclass
class DayData:
    session: Session
    bars: pd.DataFrame          # bars_to_frame() output (adjusted prices)
    official_close: float | None

    def __post_init__(self):
        self.bars = self.bars.set_index(self.bars["timestamp_utc"], drop=False).sort_index()


@dataclass(frozen=True)
class StressOptions:
    entry_fail_rate: float = 0.0
    late_exit_rate: float = 0.0
    fill_fraction: float = 1.0
    seed: int = 0


@dataclass
class Trade:
    date: date
    direction: int
    shares: int
    binding_cap: str
    entry_time: pd.Timestamp
    entry_price: float
    entry_fill: float
    exit_time: pd.Timestamp
    exit_price: float
    exit_fill: float
    exit_reason: str
    stop_price: float | None
    r1: float
    sigma30: float
    equity_before: float
    gross_pnl: float
    net_pnl: float
    flags: list = field(default_factory=list)

    @property
    def notional(self) -> float:
        return self.shares * self.entry_price

    @property
    def minutes_held(self) -> float:
        return (self.exit_time - self.entry_time).total_seconds() / 60


@dataclass
class DayResult:
    session: Session
    equity_before: float
    trade: Trade | None = None
    skip_reason: str | None = None

    @property
    def net_pnl(self) -> float:
        return self.trade.net_pnl if self.trade else 0.0


@dataclass
class BacktestResult:
    days: list[DayResult]
    start_equity: float
    end_equity: float

    @property
    def trades(self) -> list[Trade]:
        return [d.trade for d in self.days if d.trade]


def last30_return(day: DayData | None) -> float | None:
    if day is None:
        return None
    c = pd.Timestamp(day.session.close_utc)
    first, last = c - 30 * MINUTE, c - MINUTE
    if first not in day.bars.index or last not in day.bars.index:
        return None
    return float(day.bars.at[last, "close"]) / float(day.bars.at[first, "open"]) - 1


def _exit_without_stop(day, nxt, scanned, params, close_t):
    """(time, reference price, reason, flags) for the scheduled close-out."""
    last_t = close_t - MINUTE
    if params.exit_mode == "moc" and day.official_close is not None:
        return close_t, day.official_close, "time exit (MOC)", []
    if last_t in scanned.index:
        return close_t, float(scanned.at[last_t, "close"]), "time exit", []
    if len(scanned) and scanned.index[-1] >= close_t - MISSING_EXIT_WINDOW:
        t = scanned.index[-1]
        return t + MINUTE, float(scanned.at[t, "close"]), "time exit", ["missing exit bar"]
    if nxt is not None and len(nxt.bars):
        t = nxt.bars.index[0]
        return t, float(nxt.bars.at[t, "open"]), "halt: exit next open", ["halted; held overnight"]
    t = scanned.index[-1]
    return t + MINUTE, float(scanned.at[t, "close"]), "time exit", ["missing exit bar", "no next session"]


def _simulate_day(i, sessions, days, sigma_hist, params, costs, limits, equity,
                  rng_draws, stress, direction_override):
    session = sessions[i]
    day = days.get(session.date)
    if day is None:
        return None, "data: session missing"
    open_t = pd.Timestamp(session.open_utc)
    close_t = pd.Timestamp(session.close_utc)
    decision_t = close_t - params.entry_offset_min * MINUTE
    known = day.bars[day.bars.index + MINUTE <= decision_t]

    if has_problems(check_bars(known)):
        return None, "data: structural check failed"
    window = pd.date_range(close_t - 60 * MINUTE, decision_t, freq="1min", inclusive="left")
    if window.difference(known.index).size:
        return None, "data: gap before decision"

    prev = days.get(sessions[i - 1].date) if i > 0 else None
    prev_close = prev.official_close if prev else None
    direction, r1, reason = signal(params, prev_close, known, open_t)
    if reason:
        return None, reason

    history = sigma_hist[max(0, i - params.sigma_lookback):i]
    if len(history) < params.sigma_lookback or any(r is None for r in history):
        return None, "warmup: insufficient sigma history"
    sigma30 = statistics.stdev(history)
    if direction_override is not None:
        direction = direction_override(session.date, direction)

    if rng_draws[0] < stress.entry_fail_rate:
        return None, "stress: entry order failed"
    entry_t = decision_t + params.entry_delay_min * MINUTE
    candidates = [entry_t + k * MINUTE for k in range(params.entry_fallback_min + 1)]
    entry_bar_t = next((t for t in candidates if t in day.bars.index and t < close_t), None)
    if entry_bar_t is None:
        return None, "data: no entry price"
    price = float(day.bars.at[entry_bar_t, "open"])

    # Size from the last price known at the decision, never from the fill.
    decision_price = float(known["close"].iloc[-1])
    stop_frac = (params.stop_mult or params.sizing_mult) * sigma30
    median_vol = float(known.loc[window, "volume"].median())
    shares, cap = size_position(limits, equity, decision_price, stop_frac * decision_price,
                                median_vol)
    stop_dist = stop_frac * price
    shares = int(shares * stress.fill_fraction)
    if shares < 1:
        return None, f"risk: size below 1 share ({cap} cap)"
    stop = price - direction * stop_dist if params.stop_mult else None

    scanned = day.bars[(day.bars.index >= entry_bar_t) & (day.bars.index < close_t)]
    exit_info = None
    entry_fill_est = costs.fill_price(price, direction)
    loss_limit = limits.daily_loss_limit * equity        # equity at the start of this day
    bar_times = list(scanned.index)
    for k, (t, bar) in enumerate(scanned.iterrows()):
        # Pessimistic: a stop touched anywhere in a bar (including the entry
        # bar) counts as hit; a bar opening beyond the stop fills at its open.
        if stop is not None and direction > 0 and bar["low"] <= stop:
            exit_info = (t + MINUTE, min(float(bar["open"]), stop), "stop", [])
            break
        if stop is not None and direction < 0 and bar["high"] >= stop:
            exit_info = (t + MINUTE, max(float(bar["open"]), stop), "stop", [])
            break
        # Daily loss limit, marked to market at each completed bar's close (unrealized
        # loss counts). A breach is only known once the bar ends, so the exit fills at
        # the next bar's open, the same one-minute delay as entries.
        unrealized = direction * shares * (float(bar["close"]) - entry_fill_est)
        if unrealized <= -loss_limit:
            if k + 1 < len(bar_times):
                nt = bar_times[k + 1]
                exit_info = (nt, float(scanned.at[nt, "open"]), "risk: daily loss limit", [])
            else:
                exit_info = (t + MINUTE, float(bar["close"]), "risk: daily loss limit",
                             ["no later bar; exited at breach bar close"])
            break
    if exit_info is None:
        nxt = days.get(sessions[i + 1].date) if i + 1 < len(sessions) else None
        exit_info = _exit_without_stop(day, nxt, scanned, params, close_t)
        if rng_draws[1] < stress.late_exit_rate and day.official_close is not None:
            exit_info = (close_t, day.official_close, "time exit", ["stress: late exit at close"])
    exit_t, exit_price, exit_reason, flags = exit_info

    entry_fill = costs.fill_price(price, direction)
    exit_fill = costs.fill_price(exit_price, -direction)
    sell_notional = shares * (exit_fill if direction > 0 else entry_fill)
    net = (direction * shares * (exit_fill - entry_fill)
           - costs.sell_fee(sell_notional) - 2 * costs.commission_per_order)
    return Trade(
        date=session.date, direction=direction, shares=shares, binding_cap=cap,
        entry_time=entry_bar_t, entry_price=price, entry_fill=entry_fill,
        exit_time=exit_t, exit_price=exit_price, exit_fill=exit_fill,
        exit_reason=exit_reason, stop_price=stop, r1=r1, sigma30=sigma30,
        equity_before=equity, gross_pnl=direction * shares * (exit_price - price),
        net_pnl=net, flags=flags,
    ), None


def run_backtest(days: dict[date, DayData], sessions: list[Session], start: date, end: date,
                 params: Params, costs: CostModel, limits: RiskLimits, start_equity: float,
                 stress: StressOptions = StressOptions(), direction_override=None) -> BacktestResult:
    """`sessions` must be every calendar session, including warm-up days before `start`."""
    sigma_hist = [last30_return(days.get(s.date)) for s in sessions]
    rng = np.random.default_rng(stress.seed)
    risk = RiskState(limits, peak_equity=start_equity)
    equity = start_equity
    results = []
    for i, session in enumerate(sessions):
        if not start <= session.date <= end:
            continue
        draws = rng.random(2)   # drawn every day so results don't depend on branch order
        block = risk.block_reason(equity, session.date)
        if block:
            results.append(DayResult(session, equity, skip_reason=block))
            continue
        trade, reason = _simulate_day(i, sessions, days, sigma_hist, params, costs, limits,
                                      equity, draws, stress, direction_override)
        results.append(DayResult(session, equity, trade=trade, skip_reason=reason))
        if trade:
            equity += trade.net_pnl
    return BacktestResult(results, start_equity, equity)
