"""Strategy interface and a shared full-account session executor (experiment 002 onward).

A SessionStrategy only *decides*: it returns an EntryPlan built from bars completed by
its decision time. The executor turns the plan into a simulated fill, enforces the
account limits, scans stops and risk breaches on completed bars, and exits at the
scheduled bar's open, carrying a position to the next actual bar when no in-session
bar remains. No broker code is involved.

Experiment 001 keeps its original engine (trading/backtest.py) so its recorded results
stay byte-identical.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

import numpy as np
import pandas as pd

from trading.backtest import BacktestResult, DayData, DayResult, Trade, _net_if_closed
from trading.costs import CostModel
from trading.risk import RiskLimits, RiskState, size_position
from trading.sessions import Session

MINUTE = pd.Timedelta(minutes=1)
UNRESOLVED = "unresolved: halt or missing data"
CARRY = "involuntary overnight carry"
PROVISIONAL = "provisional valuation; not a verified liquidation"


def first_bad_minute(day: DayData) -> pd.Timestamp:
    """Earliest minute from the open whose bar is missing or fails structural checks
    (duplicate, non-finite, invalid OHLC, non-positive price, negative volume). Checks(T)
    passes exactly when this minute is >= T. Returns the close if every bar is good."""
    s = day.session
    o, c = pd.Timestamp(s.open_utc), pd.Timestamp(s.close_utc)
    b = day.bars
    expected = pd.date_range(o, c, freq="1min", inclusive="left")
    dup = b.index[b.index.duplicated()]
    good = b[~b.index.duplicated(keep=False)]
    vals = good[["open", "high", "low", "close", "volume"]].astype(float)
    ok = (np.isfinite(vals).all(axis=1)
          & (good["high"] >= good[["open", "close", "low"]].max(axis=1))
          & (good["low"] <= good[["open", "close", "high"]].min(axis=1))
          & (good[["open", "high", "low", "close"]] > 0).all(axis=1)
          & (good["volume"] >= 0))
    good_minutes = set(good.index[ok.to_numpy()])
    for t in expected:
        if t not in good_minutes or t in dup:
            return t
    return c


def checks(day: DayData, T: pd.Timestamp, first_bad: pd.Timestamp | None = None) -> bool:
    """Checks(T): every minute from the open to T - 1 has a structurally valid bar."""
    return (first_bad if first_bad is not None else first_bad_minute(day)) >= T


@dataclass(frozen=True)
class EntryPlan:
    decision_time: pd.Timestamp
    decision_price: float
    window_start: pd.Timestamp          # first bar start eligible for the fill
    window_end: pd.Timestamp            # last bar start eligible (inclusive)
    stop: float
    median_volume: float
    info: dict = field(default_factory=dict)


@dataclass
class Decision:
    plan: EntryPlan | None
    reason: str | None = None
    info: dict = field(default_factory=dict)


class SessionStrategy(Protocol):
    name: str

    def decide(self, day: DayData) -> Decision: ...


def acceptance_limit(limits: RiskLimits, costs: CostModel, equity: float, shares: int, stop: float,
                     gross_in_use: float = 0.0) -> float:
    """Highest fill reference price at which the sized order still meets the approved
    notional, gross exposure, cash and planned-risk (including round-trip costs) limits."""
    k = (2 * costs.per_side_bp + costs.sell_fee_bp) / 1e4
    return min(limits.max_notional * equity / shares,
               (limits.max_gross_exposure * equity - gross_in_use) / shares,
               equity / shares,
               (limits.risk_per_trade * equity / shares + stop) / (1 + k))


def _carry(nxt: DayData | None, last_bar_t: pd.Timestamp, last_close: float, reason: str):
    if nxt is not None and len(nxt.bars):
        t = nxt.bars.index[0]
        return t, float(nxt.bars.at[t, "open"]), f"{reason} ({CARRY})", [UNRESOLVED, CARRY], last_close
    return (last_bar_t + MINUTE, last_close, f"{reason} (no later data)",
            ["unresolved: no later data", PROVISIONAL], last_close)


def execute_plan(day: DayData, nxt: DayData | None, plan: EntryPlan, equity: float, risk: RiskState,
                 costs: CostModel, limits: RiskLimits, exit_mode: str = "c1_open"):
    """Return (Trade, None) or (None, skip_reason)."""
    s = day.session
    c = pd.Timestamp(s.close_utc)
    b = day.bars
    window = b[(b.index >= plan.window_start) & (b.index <= plan.window_end)]
    if not len(window):
        expired = plan.window_end < plan.window_start + 2 * MINUTE
        return None, "entry expired (no bar by C-60)" if expired else "data: no entry price"
    e = window.index[0]
    price = float(b.at[e, "open"])
    if price <= plan.stop:
        return None, "invalid stop at entry"
    rt = plan.decision_price * (2 * costs.per_side_bp + costs.sell_fee_bp) / 1e4
    shares, cap = size_position(limits, equity, plan.decision_price, plan.decision_price - plan.stop,
                                plan.median_volume, rt, gross_in_use=0.0, positions_in_use=0)
    if shares < 1:
        return None, f"risk: size below 1 share ({cap} cap)"
    # Invariant 2: a marketable limit at the next bar's open; only the open is used.
    if price > acceptance_limit(limits, costs, equity, shares, plan.stop):
        return None, "risk: gap beyond executable limit"

    scan = b[(b.index >= e) & (b.index <= c - 2 * MINUTE)]
    later = list(b[(b.index > e) & (b.index < c)].index)
    exit_info, carry_mark = None, None
    for t, bar in scan.iterrows():
        if bar["low"] <= plan.stop:
            exit_info = (t + MINUTE, min(float(bar["open"]), plan.stop), "stop", [])
            break
        breach = risk.observe(s.date, equity + _net_if_closed(costs, 1, shares, price, float(bar["close"])))
        if breach:
            nexts = [x for x in later if x > t]
            if nexts:
                exit_info = (nexts[0], float(b.at[nexts[0], "open"]), breach, [])
            else:
                *exit_info, carry_mark = _carry(nxt, t, float(bar["close"]), breach)
            break
    if exit_info is None:
        last_t = c - MINUTE
        if exit_mode == "moc" and day.official_close is not None:
            exit_info = (c, float(day.official_close), "time exit (MOC sensitivity)", [])
        elif last_t in b.index:
            exit_info = (last_t, float(b.at[last_t, "open"]), "time exit", [])
        else:
            lt = b[b.index < c].index[-1]
            *exit_info, carry_mark = _carry(nxt, lt, float(b.at[lt, "close"]), "time exit")
    exit_t, exit_price, reason, flags = exit_info
    net = _net_if_closed(costs, 1, shares, price, exit_price)
    return Trade(
        date=s.date, direction=1, shares=shares, binding_cap=cap, entry_time=e, entry_price=price,
        entry_fill=costs.fill_price(price, 1), exit_time=exit_t, exit_price=exit_price,
        exit_fill=costs.fill_price(exit_price, -1), exit_reason=reason, stop_price=plan.stop,
        r1=float("nan"), sigma30=float("nan"), equity_before=equity,
        gross_pnl=shares * (exit_price - price), net_pnl=net, flags=flags,
        carry_mark_price=carry_mark if UNRESOLVED in flags or PROVISIONAL in flags else None,
    ), None


@dataclass
class EngineResult(BacktestResult):
    halted: bool = False
    halt_event: dict | None = None
    max_drawdown_intraday: float = 0.0
    session_info: dict = field(default_factory=dict)   # date -> decision info (e.g. M2 records)

    @property
    def provisional_trades(self) -> list[Trade]:
        return [t for t in self.trades if PROVISIONAL in t.flags]


def run_strategy(days: dict[date, DayData], sessions: list[Session], start: date, end: date,
                 strategy: SessionStrategy, costs: CostModel, limits: RiskLimits,
                 start_equity: float, exit_mode: str = "c1_open") -> EngineResult:
    """Full simulated account with every control. `sessions` must include the session after `end`
    when its data exists, so a carried position can exit there."""
    risk = RiskState(limits, peak_equity=start_equity)
    equity = start_equity
    results, info = [], {}
    for i, session in enumerate(sessions):
        if not start <= session.date <= end:
            continue
        block = risk.block_reason(equity, session.date)
        if block:
            results.append(DayResult(session, equity, skip_reason=block))
            continue
        day = days.get(session.date)
        if day is None:
            results.append(DayResult(session, equity, skip_reason="data: session missing"))
            continue
        decision = strategy.decide(day)
        if decision.info:
            info[str(session.date)] = decision.info
        if decision.plan is None:
            results.append(DayResult(session, equity, skip_reason=decision.reason))
            continue
        nxt_session = sessions[i + 1] if i + 1 < len(sessions) else None
        nxt = days.get(nxt_session.date) if nxt_session else None
        trade, reason = execute_plan(day, nxt, decision.plan, equity, risk, costs, limits, exit_mode)
        results.append(DayResult(session, equity, trade=trade, skip_reason=reason))
        if trade is None:
            continue
        if CARRY in trade.flags and nxt_session is not None:
            # The next session starts at the carried position's mark at this session's last bar.
            risk.start_day(nxt_session.date, equity + _net_if_closed(
                costs, 1, trade.shares, trade.entry_price, trade.carry_mark_price))
            equity += trade.net_pnl
            risk.observe(nxt_session.date, equity)
        else:
            equity += trade.net_pnl
            risk.observe(session.date, equity)       # realized result, including exit overshoot
    return EngineResult(results, start_equity, equity, halted=risk.halted, halt_event=risk.halt_event,
                        max_drawdown_intraday=risk.max_drawdown_seen, session_info=info)
