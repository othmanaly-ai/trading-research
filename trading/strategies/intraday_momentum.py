"""Experiment 001 signal (research/001_intraday_momentum/SPEC.md, section 4).

The signal only ever receives bars that had finished by the decision time;
the backtest engine is responsible for that filtering.
"""

from dataclasses import asdict, dataclass

import pandas as pd

MINUTE = pd.Timedelta(minutes=1)


@dataclass(frozen=True)
class Params:
    signal_from: str = "prev_close"   # D3: "prev_close" (published) or "open"
    signal_minutes: int = 30          # r1 measured to open + 30 min (10:00 ET)
    entry_offset_min: int = 30        # decision at close - 30 min
    entry_delay_min: int = 1          # fill at the open of the bar after the decision
    entry_fallback_min: int = 2       # use a later bar this many minutes at most
    exit_mode: str = "last_minute"    # D4: "last_minute" or "moc"
    stop_mult: float | None = 2.0     # D5: stop = stop_mult x sigma30; None = no stop
    sizing_mult: float = 2.0          # risk sizing distance when there is no stop
    sigma_lookback: int = 20
    long_only: bool = False           # D6

    def as_dict(self) -> dict:
        return asdict(self)


def signal(params: Params, prev_close: float | None, known_bars: pd.DataFrame,
           open_utc: pd.Timestamp) -> tuple[int, float | None, str | None]:
    """(direction, r1, skip_reason). direction is +1 long, -1 short, 0 none."""
    last_t = open_utc + (params.signal_minutes - 1) * MINUTE      # 09:59 ET bar
    if last_t not in known_bars.index:
        return 0, None, "data: missing 09:59 bar"
    p_end = float(known_bars.at[last_t, "close"])
    if params.signal_from == "open":
        if open_utc not in known_bars.index:
            return 0, None, "data: missing 09:30 bar"
        p_start = float(known_bars.at[open_utc, "open"])
    else:
        if prev_close is None:
            return 0, None, "data: missing previous close"
        p_start = prev_close
    r1 = p_end / p_start - 1
    if r1 > 0:
        return 1, r1, None
    if r1 < 0:
        return (0, r1, "signal: negative, long-only") if params.long_only else (-1, r1, None)
    return 0, r1, "signal: zero"
