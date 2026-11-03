"""Outcome classification for executed trades (docs/PRODUCT_SPEC.md section 7).

The classifier re-scans the trade's 1-minute bars independently of the engine.
A bar only shows its range, not the order of prices inside it, so a bar that
reaches both the stop and the target is AMBIGUOUS and is never counted as a
target hit.
"""

import pandas as pd

TARGET_FIRST = "target_first"
STOP_FIRST = "stop_first"
AMBIGUOUS = "ambiguous"
NEITHER = "neither"
UNFILLABLE = "unfillable"

# Decision skip reasons that mean "decided to enter, but no executable price".
UNFILLABLE_REASONS = ("data: no entry price", "stress: entry order failed")


def classify_trade(bars: pd.DataFrame, entry_bar_t: pd.Timestamp, exit_time: pd.Timestamp,
                   direction: int, stop: float | None, target: float | None) -> str:
    """bars: indexed by bar start (UTC) with high/low columns. Scans bars that
    start at or after the entry bar and before the exit time."""
    window = bars[(bars.index >= entry_bar_t) & (bars.index < exit_time)]
    for _, bar in window.iterrows():
        hi, lo = float(bar["high"]), float(bar["low"])
        hit_stop = stop is not None and (lo <= stop if direction > 0 else hi >= stop)
        hit_target = target is not None and (hi >= target if direction > 0 else lo <= target)
        if hit_stop and hit_target:
            return AMBIGUOUS
        if hit_stop:
            return STOP_FIRST
        if hit_target:
            return TARGET_FIRST
    return NEITHER
