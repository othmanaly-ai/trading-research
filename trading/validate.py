"""Data-quality checks for OHLCV bars. Each check returns plain findings."""

import math

import pandas as pd

from trading.sessions import MARKET_TZ, Session


def bars_to_frame(bars: list[dict]) -> pd.DataFrame:
    """Alpaca bar dicts (t, o, h, l, c, v, n, vw) to a DataFrame, order preserved."""
    df = pd.DataFrame(bars, columns=["t", "o", "h", "l", "c", "v", "n", "vw"])
    df = df.rename(columns={"t": "timestamp_utc", "o": "open", "h": "high", "l": "low",
                            "c": "close", "v": "volume", "n": "trade_count", "vw": "vwap"})
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df.insert(1, "timestamp_et", df["timestamp_utc"].dt.tz_convert(MARKET_TZ))
    return df


def check_bars(df: pd.DataFrame) -> dict:
    """Structural checks that apply to any bar interval."""
    ts = df["timestamp_utc"]
    prices = df[["open", "high", "low", "close"]]
    numeric = df[["open", "high", "low", "close", "volume"]].astype(float)
    nonfinite = ~numeric.map(math.isfinite)
    bad_high = df["high"] < prices[["open", "close", "low"]].max(axis=1)
    bad_low = df["low"] > prices[["open", "close", "high"]].min(axis=1)
    nonpositive = (prices <= 0).any(axis=1)
    return {
        "rows": len(df),
        "duplicate_timestamps": int(ts.duplicated().sum()),
        "out_of_order": int((ts.diff() <= pd.Timedelta(0)).sum()),
        "nonfinite_values": int(nonfinite.to_numpy().sum()),
        "invalid_ohlc_rows": int((bad_high | bad_low).sum()),
        "nonpositive_price_rows": int(nonpositive.sum()),
        "negative_volume_rows": int((df["volume"] < 0).sum()),
    }


def check_daily_coverage(df: pd.DataFrame, sessions: list[Session]) -> dict:
    """Daily bars are stamped at midnight New York time; map to session dates."""
    got = set(df["timestamp_et"].dt.date)
    expected = {s.date for s in sessions}
    return {
        "expected_sessions": sorted(str(d) for d in expected),
        "missing_sessions": sorted(str(d) for d in expected - got),
        "unexpected_dates": sorted(str(d) for d in got - expected),
    }


def check_minute_coverage(df: pd.DataFrame, session: Session) -> dict:
    """Compare 1-minute bars with every minute of the regular session.

    Alpaca only creates a bar for a minute in which a trade was reported, so a
    missing minute means "no trades on this feed", not necessarily lost data.
    """
    expected = pd.date_range(session.open_utc, session.close_utc, freq="1min",
                             inclusive="left", tz="UTC")
    got = pd.DatetimeIndex(df["timestamp_utc"])
    missing = expected.difference(got)
    outside = got.difference(expected)
    return {
        "expected_minutes": len(expected),
        "present_minutes": len(expected) - len(missing),
        "missing_minutes": len(missing),
        "missing_examples_et": [str(t.tz_convert(MARKET_TZ)) for t in missing[:10]],
        "bars_outside_regular_session": len(outside),
        "early_close": session.early_close,
    }


def has_problems(structural: dict) -> bool:
    return any(v for k, v in structural.items() if k != "rows")
