"""SYNTHETIC FIXTURES ONLY. These made-up bars test the checking code. They are
not market data and say nothing about any real price or strategy."""

import math
from datetime import date, datetime, timedelta, timezone

from trading.sessions import Session
from trading.validate import (
    bars_to_frame, check_bars, check_daily_coverage, check_minute_coverage, has_problems,
)

OPEN = datetime(2026, 11, 24, 14, 30, tzinfo=timezone.utc)
SESSION = Session(date(2026, 11, 24), OPEN, OPEN + timedelta(minutes=390), False)


def synthetic_bar(ts, o=100.0, h=101.0, l=99.0, c=100.5, v=1000):
    return {"t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": o, "h": h, "l": l, "c": c,
            "v": v, "n": 10, "vw": 100.2}


def full_session():
    return [synthetic_bar(OPEN + timedelta(minutes=i)) for i in range(390)]


def test_clean_synthetic_session_passes():
    df = bars_to_frame(full_session())
    structure = check_bars(df)
    assert not has_problems(structure)
    coverage = check_minute_coverage(df, SESSION)
    assert coverage["missing_minutes"] == 0
    assert coverage["bars_outside_regular_session"] == 0


def test_detects_each_structural_problem():
    bars = full_session()[:6]
    bars.append(dict(bars[2]))                  # duplicate timestamp
    bars[1], bars[3] = bars[3], bars[1]         # out of order
    bars[4] = synthetic_bar(OPEN + timedelta(minutes=4), h=98.0)   # high below low
    bars[5] = synthetic_bar(OPEN + timedelta(minutes=5), v=-5)     # negative volume
    bars[0] = synthetic_bar(OPEN, c=math.nan)   # nonfinite
    s = check_bars(bars_to_frame(bars))
    assert s["duplicate_timestamps"] == 1
    assert s["out_of_order"] >= 1
    assert s["invalid_ohlc_rows"] == 1
    assert s["negative_volume_rows"] == 1
    assert s["nonfinite_values"] == 1
    assert has_problems(s)


def test_minute_gaps_and_outside_bars_reported():
    bars = full_session()
    del bars[100:103]
    bars.append(synthetic_bar(OPEN + timedelta(minutes=390)))   # 16:00 ET, after close
    c = check_minute_coverage(bars_to_frame(bars), SESSION)
    assert c["missing_minutes"] == 3
    assert c["missing_examples_et"][0] == "2026-11-24 11:10:00-05:00"
    assert c["bars_outside_regular_session"] == 1


def test_daily_coverage_maps_midnight_et_stamps_to_dates():
    # Alpaca stamps daily bars at 00:00 New York time (05:00 UTC in winter).
    days = [date(2026, 11, 23), date(2026, 11, 24)]
    bars = [synthetic_bar(datetime(2026, 11, 23, 5, tzinfo=timezone.utc))]
    sessions = [Session(d, OPEN, OPEN, False) for d in days]
    c = check_daily_coverage(bars_to_frame(bars), sessions)
    assert c["missing_sessions"] == ["2026-11-24"]
    assert c["unexpected_dates"] == []
