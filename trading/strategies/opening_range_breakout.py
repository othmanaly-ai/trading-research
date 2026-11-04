"""Experiment 002 (spec v1.0): long-only opening-range breakout, and the B3 comparator.

Both only decide from completed bars; trading.engine executes the plan.
"""

from dataclasses import asdict, dataclass

import pandas as pd

from trading.backtest import DayData
from trading.engine import Decision, EntryPlan, first_bad_minute

MINUTE = pd.Timedelta(minutes=1)


@dataclass(frozen=True)
class ORBConfig:
    name: str = "primary"
    range_minutes: int = 30           # E1
    signal_end_offset: int = 61       # E2: last signal bar starts at C - 61
    latest_entry_offset: int = 60     # hard latest actual entry at C - 60
    fallback_minutes: int = 2
    stop: str = "range_low"           # E3: "range_low" or "midpoint"
    volume_bars: int = 30

    def as_dict(self) -> dict:
        return asdict(self)


PRIMARY = ORBConfig()
ROBUSTNESS = (
    ORBConfig(name="range_15", range_minutes=15),
    ORBConfig(name="range_45", range_minutes=45),
    ORBConfig(name="midpoint_stop", stop="midpoint"),
)
CONFIGURATIONS = (PRIMARY,) + ROBUSTNESS


def opening_range(day: DayData, minutes: int, first_bad: pd.Timestamp):
    """(H, L) from bars [O, O + minutes - 1] if all exist and pass Checks(O + minutes); else None."""
    o = pd.Timestamp(day.session.open_utc)
    end = o + minutes * MINUTE
    if first_bad < end:
        return None
    bars = day.bars[(day.bars.index >= o) & (day.bars.index < end)]
    return float(bars["high"].max()), float(bars["low"].min())


class OpeningRangeBreakout:
    def __init__(self, config: ORBConfig = PRIMARY):
        self.config = config
        self.name = f"orb:{config.name}"

    def decide(self, day: DayData) -> Decision:
        cfg = self.config
        s = day.session
        o, c = pd.Timestamp(s.open_utc), pd.Timestamp(s.close_utc)
        fb = first_bad_minute(day)
        rng = opening_range(day, cfg.range_minutes, fb)
        if rng is None:
            return Decision(None, "data: incomplete opening range")
        H, L = rng
        stop = L if cfg.stop == "range_low" else (H + L) / 2
        b = day.bars
        last_signal = c - cfg.signal_end_offset * MINUTE
        t = o + cfg.range_minutes * MINUTE
        signal = None
        while t <= last_signal:
            if fb <= t:   # Checks(t + 1 min) fails: bar t missing or invalid (M2)
                return Decision(None, "data: check failed before signal",
                                {"m2_stop": True, "failed_check_minute_utc": str(t)})
            if float(b.at[t, "close"]) > H:
                signal = t
                break
            t += MINUTE
        if signal is None:
            return Decision(None, "no breakout")
        d = signal + MINUTE
        vol = b[(b.index >= d - cfg.volume_bars * MINUTE) & (b.index < d)]["volume"].median()
        latest = c - cfg.latest_entry_offset * MINUTE
        return Decision(EntryPlan(
            decision_time=d, decision_price=float(b.at[signal, "close"]), window_start=d,
            window_end=min(d + cfg.fallback_minutes * MINUTE, latest), stop=stop,
            median_volume=float(vol), info={"H": H, "L": L, "signal_bar_utc": str(signal)}))


class AlwaysLongB3:
    """B3: every OR-eligible session, scheduled entry at the O + 31 open, sized at O + 31
    from the completed 10:00 bar, stop at L, same exit and account controls."""
    name = "B3:always_long_1001"

    def __init__(self, config: ORBConfig = PRIMARY):
        self.config = config

    def decide(self, day: DayData) -> Decision:
        o = pd.Timestamp(day.session.open_utc)
        fb = first_bad_minute(day)
        rng = opening_range(day, self.config.range_minutes, fb)
        if rng is None:
            return Decision(None, "data: incomplete opening range")
        H, L = rng
        m = o + (self.config.range_minutes + 1) * MINUTE           # O + 31
        if fb < m:                                                # Checks(m) fails
            return Decision(None, "B3: invalid entry minute (data check)")
        b = day.bars
        if m not in b.index:
            return Decision(None, "B3: no bar at entry minute")
        vol = b[(b.index >= m - 30 * MINUTE) & (b.index < m)]["volume"].median()
        return Decision(EntryPlan(
            decision_time=m, decision_price=float(b.at[m - MINUTE, "close"]), window_start=m,
            window_end=m, stop=L, median_volume=float(vol), info={"H": H, "L": L}))
