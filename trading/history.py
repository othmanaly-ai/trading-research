"""Historical bar store: fetch from Alpaca (read-only), validate, save with provenance.

Fetch:  .venv\\Scripts\\python -m trading.history --symbol SPY --start 2016-01-04 --end 2016-03-31

Layout (git-ignored):
  data/history/<SYMBOL>/<feed>/<adjustment>/minute/<YYYY-MM-DD>.csv   regular-session 1-minute bars
  data/history/<SYMBOL>/<feed>/<adjustment>/daily.csv                 one row per session
  data/history/<SYMBOL>/<feed>/<adjustment>/manifest.json             provenance and validation

Dates inside the final held-out period are refused unless --include-final is
given, so the final test data is not downloaded (and looked at) by accident.
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from trading.backtest import DayData
from trading.experiment import PERIODS
from trading.sessions import MARKET_TZ, Session, sessions_between
from trading.validate import bars_to_frame, check_bars, check_minute_coverage, has_problems

# The Alpaca client is imported only where data is fetched, so readers of stored
# data (the dashboard server) never load broker code.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = PROJECT_ROOT / "data" / "history"
SOURCE = "alpaca_rest"


class HistoryError(RuntimeError):
    pass


def series_dir(root: Path, symbol: str, feed: str, adjustment: str) -> Path:
    return root / symbol.upper() / feed / adjustment


def period_of(d: date) -> str | None:
    for name, (a, b) in PERIODS.items():
        if a <= d <= b:
            return name
    return None


def _iso(dt) -> str:
    return pd.Timestamp(dt).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_and_store(client: "ReadOnlyAlpacaClient", symbol: str, start: date, end: date,  # noqa: F821
                    feed: str, adjustment: str, root: Path = HISTORY_DIR,
                    include_final: bool = False) -> dict:
    sessions = sessions_between(start, end)
    if not sessions:
        raise HistoryError(f"no NYSE sessions between {start} and {end}")
    if not include_final and any(period_of(s.date) == "final" for s in sessions):
        raise HistoryError("range overlaps the final held-out period; pass --include-final only "
                           "when running the final test")

    retrieved = datetime.now(timezone.utc)
    minute = client.get_bars(symbol, "1Min", _iso(sessions[0].open_utc), _iso(sessions[-1].close_utc),
                             feed, adjustment)
    daily = client.get_bars(symbol, "1Day", str(sessions[0].date), str(sessions[-1].date),
                            feed, adjustment)

    out = series_dir(root, symbol, feed, adjustment)
    (out / "minute").mkdir(parents=True, exist_ok=True)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    # Keep the API's bars exactly as received (all hours) before any filtering.
    pd.DataFrame(minute["bars"]).to_csv(out / "raw" / "minute_all_hours.csv", index=False)
    pd.DataFrame(daily["bars"]).to_csv(out / "raw" / "daily.csv", index=False)
    mframe = bars_to_frame(minute["bars"])
    dframe = bars_to_frame(daily["bars"])
    dframe["session_date"] = dframe["timestamp_et"].dt.date.astype(str)
    dframe.to_csv(out / "daily.csv", index=False)
    daily_structure = check_bars(dframe) if len(dframe) else {"rows": 0}

    per_session = {}
    for s in sessions:
        open_t, close_t = pd.Timestamp(s.open_utc), pd.Timestamp(s.close_utc)
        day = mframe[(mframe["timestamp_utc"] >= open_t) & (mframe["timestamp_utc"] < close_t)]
        day.to_csv(out / "minute" / f"{s.date}.csv", index=False)
        structure = check_bars(day) if len(day) else {"rows": 0}
        coverage = check_minute_coverage(day, s) if len(day) else {"present_minutes": 0}
        has_daily = str(s.date) in set(dframe["session_date"])
        usable = len(day) > 0 and not has_problems(structure) and has_daily
        per_session[str(s.date)] = {
            "period": period_of(s.date), "rows": len(day), "structure": structure,
            "present_minutes": coverage.get("present_minutes", 0),
            "expected_minutes": s.regular_minutes, "early_close": s.early_close,
            "missing_minutes": coverage.get("missing_minutes", s.regular_minutes),
            "missing_examples_et": coverage.get("missing_examples_et", []),
            "daily_bar": has_daily, "usable": usable,
        }

    manifest = {
        "source": SOURCE, "symbol": symbol.upper(), "requested_feed": feed,
        "actual_feed": f"{feed} (request accepted; API does not echo feed)",
        "adjustment": adjustment, "interval": "1Min (regular session only) + 1Day",
        "timezone_stored": "UTC plus America/New_York column", "calendar": "XNYS",
        "start": str(start), "end": str(end), "retrieved_utc": _iso(retrieved),
        "requests": {"minute_pages": minute["pages"], "minute_rows_all_hours": len(minute["bars"]),
                     "daily_pages": daily["pages"], "daily_rows": len(daily["bars"]),
                     "pagination_complete": True,   # get_bars follows next_page_token until it is null
                     "minute_requested": [_iso(sessions[0].open_utc), _iso(sessions[-1].close_utc)],
                     "minute_received": _received(mframe), "daily_received": _received(dframe)},
        "daily_structure": daily_structure,
        "transformations": [
            "raw/ holds the API bars unmodified (all hours).",
            "minute/<date>.csv keeps bars whose start is in [session open, session close) per the XNYS "
            "calendar, so pre-market and after-hours bars are excluded; prices are not altered.",
            "No gaps are filled and no bars are interpolated. Missing minutes are reported, not repaired.",
            "A session is unusable if it has no regular-session bars, fails structural checks, or has "
            "no daily bar; unusable sessions are kept on disk but never fed to the engine.",
        ],
        "limitations": [
            "Alpaca creates a minute bar only when a trade printed; a missing minute may mean no trades "
            "on this feed rather than lost data (much more common on IEX than SIP).",
            "The API does not echo which feed served the data.",
            "Daily bars are compared to minute bars only by session date, not by price.",
        ],
        "sessions": per_session,
        "summary": {
            "expected_sessions": len(sessions),
            "usable_sessions": sum(1 for v in per_session.values() if v["usable"]),
            "by_period": {p: sum(1 for v in per_session.values() if v["usable"] and v["period"] == p)
                          for p in PERIODS},
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return manifest


def _received(frame: pd.DataFrame) -> list[str] | None:
    if not len(frame):
        return None
    return [_iso(frame["timestamp_utc"].min()), _iso(frame["timestamp_utc"].max())]


def read_manifest(symbol: str, feed: str, adjustment: str, root: Path = HISTORY_DIR) -> dict | None:
    path = series_dir(root, symbol, feed, adjustment) / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def load_days(symbol: str, feed: str, adjustment: str, sessions: list[Session],
              root: Path = HISTORY_DIR) -> dict[date, DayData]:
    """Usable stored sessions as DayData. Unusable or missing sessions are left out,
    so the engine records them as 'data: session missing' instead of trading them."""
    manifest = read_manifest(symbol, feed, adjustment, root)
    if manifest is None:
        raise HistoryError(f"no stored history for {symbol} {feed} {adjustment}")
    out = series_dir(root, symbol, feed, adjustment)
    daily = pd.read_csv(out / "daily.csv")
    closes = dict(zip(daily["session_date"].astype(str), daily["close"]))
    days = {}
    for s in sessions:
        info = manifest["sessions"].get(str(s.date))
        if not info or not info["usable"]:
            continue
        frame = pd.read_csv(out / "minute" / f"{s.date}.csv")
        frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
        frame["timestamp_et"] = frame["timestamp_utc"].dt.tz_convert(MARKET_TZ)
        days[s.date] = DayData(s, frame, official_close=float(closes[str(s.date)]))
    return days


def main(argv=None) -> int:
    from trading.alpaca_client import (
        AlpacaAccessError, MissingCredentials, ReadOnlyAlpacaClient, load_credentials,
    )

    parser = argparse.ArgumentParser(description="Fetch and store Alpaca historical bars (read-only)")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--feed", choices=["sip", "iex"], default="sip")
    parser.add_argument("--adjustment", choices=["raw", "all"], default="all")
    parser.add_argument("--include-final", action="store_true")
    args = parser.parse_args(argv)
    if args.end < args.start or args.end - args.start > timedelta(days=800):
        print("Choose an end date after the start, within about two years per run.")
        return 2
    try:
        client = ReadOnlyAlpacaClient(*load_credentials())
        m = fetch_and_store(client, args.symbol, args.start, args.end, args.feed, args.adjustment,
                            include_final=args.include_final)
    except MissingCredentials as exc:
        print(f"BLOCKED: {exc}")
        return 2
    except (HistoryError, AlpacaAccessError) as exc:
        print(f"FAILED: {exc} (no feed substitution was made)")
        return 1
    s, r = m["summary"], m["requests"]
    gappy = {d: v["missing_minutes"] for d, v in m["sessions"].items() if v["missing_minutes"]}
    print(f"{m['symbol']} feed requested {m['requested_feed']} ({m['actual_feed']}), adjustment {m['adjustment']}")
    print(f"minute bars requested {r['minute_requested']} received {r['minute_received']} "
          f"({r['minute_pages']} pages, complete={r['pagination_complete']})")
    print(f"{s['usable_sessions']} of {s['expected_sessions']} sessions usable; by period {s['by_period']}")
    print(f"sessions with missing regular-session minutes: {len(gappy)} {dict(list(gappy.items())[:5])}")
    print(f"daily bar checks: {m['daily_structure']}")
    print(f"Saved to {series_dir(HISTORY_DIR, args.symbol, args.feed, args.adjustment)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
