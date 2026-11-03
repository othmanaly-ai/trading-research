"""SYNTHETIC FIXTURES ONLY. Made-up minute bars on real calendar dates, used to
check the software and drive the DEMO REPLAY dashboard. They are not market
data and say nothing about any real price, the strategy's returns, or market
behavior."""

from datetime import timedelta

import numpy as np
import pandas as pd

from trading.backtest import DayData
from trading.sessions import Session
from trading.validate import bars_to_frame


def make_day(session: Session, prev_close: float, morning: float, last30: float,
             volume: int = 10_000, noise: float = 0.0, rng=None) -> DayData:
    """Price ramps by `morning` over the first 30 minutes, stays flat, then ramps
    by `last30` over the final 30 minutes. `noise` adds a random walk (per-minute
    standard deviation as a fraction of price) on top, for a less artificial chart."""
    n = session.regular_minutes
    path = np.empty(n)
    path[:30] = prev_close * (1 + morning * np.arange(1, 31) / 30)
    flat = path[29]
    path[30:n - 30] = flat
    path[n - 30:] = flat * (1 + last30 * np.arange(1, 31) / 30)
    if noise:
        path *= 1 + np.cumsum(rng.normal(0, noise, n))
    opens = np.concatenate([[prev_close], path[:-1]])
    bars = []
    for i in range(n):
        o, c = float(opens[i]), float(path[i])
        t = session.open_utc + timedelta(minutes=i)
        bars.append({"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": o, "c": c,
                     "h": max(o, c) * 1.0001, "l": min(o, c) * 0.9999,
                     "v": volume, "n": 50, "vw": (o + c) / 2})
    return DayData(session, bars_to_frame(bars), official_close=float(path[-1]))


def make_days(sessions: list[Session], seed: int = 0, start_price: float = 100.0,
              volume: int = 10_000, noise: float = 0.0) -> dict:
    rng = np.random.default_rng(seed)
    days, prev = {}, start_price
    for s in sessions:
        day = make_day(s, prev, morning=rng.normal(0, 0.005), last30=rng.normal(0, 0.002),
                       volume=volume, noise=noise, rng=rng)
        days[s.date] = day
        prev = day.official_close
    return days


def replace_day(days: dict, sessions: list[Session], d, morning: float, last30: float) -> DayData:
    """Rebuild one day with chosen moves, chained to the previous official close."""
    i = next(k for k, s in enumerate(sessions) if s.date == d)
    prev = days[sessions[i - 1].date].official_close
    days[d] = make_day(sessions[i], prev, morning, last30)
    return days[d]


def utc(ts: str) -> pd.Timestamp:
    return pd.Timestamp(ts, tz="UTC")
