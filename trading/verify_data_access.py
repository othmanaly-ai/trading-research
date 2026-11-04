"""Milestone 2 check: read the paper account and fetch AAPL bars, read-only.

Run:  .venv\\Scripts\\python -m trading.verify_data_access [--feed sip|iex] [--symbol SPY] [--as-of 2016-02-01]

Samples inside the validation or final held-out periods are refused (exit 3)
unless --allow-held-out is given.

Writes to data/alpaca/<retrieval time>/ (git-ignored). Never prints keys.
The requested feed is used as-is; if it is refused, the script stops and says
so rather than switching to another feed.
"""

import argparse
import json
import platform
import sys
from datetime import date, datetime, time, timedelta, timezone

from trading.alpaca_client import (
    DATA_URL, PAPER_TRADING_URL, PROJECT_ROOT, AlpacaAccessError,
    MissingCredentials, ReadOnlyAlpacaClient, load_credentials,
)
from trading.history import period_of
from trading.sessions import CALENDAR_NAME, MARKET_TZ, completed_sessions
from trading.validate import (
    bars_to_frame, check_bars, check_daily_coverage, check_minute_coverage, has_problems,
)

SYMBOL = "AAPL"
HELD_OUT = {"validation", "final"}
ADJUSTMENT = "raw"
FEED_NOTES = {
    "sip": "SIP = consolidated tape from all US exchanges (CTA + UTP).",
    "iex": "IEX = one exchange only; a small share of total volume, so volume is "
           "lower and quiet minutes may have no bar.",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--feed", choices=["sip", "iex"], default="sip")
    parser.add_argument("--symbol", default=SYMBOL)
    parser.add_argument("--as-of", type=date.fromisoformat, default=None,
                        help="use the 5 sessions completed by this date (default: today)")
    parser.add_argument("--allow-held-out", action="store_true",
                        help="permit sessions inside the validation/final periods")
    args = parser.parse_args(argv)
    symbol = args.symbol.upper()

    try:
        client = ReadOnlyAlpacaClient(*load_credentials())
    except MissingCredentials as exc:
        print(f"BLOCKED: {exc}")
        return 2

    started = _now()
    as_of = (datetime.combine(args.as_of, time(23, 59), timezone.utc) if args.as_of else started)
    sessions = completed_sessions(as_of, 5)
    held_out = sorted({p for s in sessions if (p := period_of(s.date)) in HELD_OUT})
    if held_out and not args.allow_held_out:
        print(f"REFUSED: sessions {sessions[0].date}..{sessions[-1].date} fall in held-out period(s) "
              f"{held_out}. Use --as-of with a development-period date (e.g. 2016-02-01).")
        return 3
    out_dir = PROJECT_ROOT / "data" / "alpaca" / started.strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    last = sessions[-1]
    provenance = {
        "symbol": symbol,
        "calendar": CALENDAR_NAME,
        "market_timezone": MARKET_TZ,
        "stored_timestamps": "timestamp_utc (as returned) and timestamp_et (converted)",
        "requested_feed": args.feed,
        "feed_note": FEED_NOTES[args.feed],
        "actual_feed": None,
        "adjustment": ADJUSTMENT,
        "python": platform.python_version(),
        "requests": [],
        "sample_as_of": str(args.as_of) if args.as_of else "today",
        "sample_periods": sorted({str(period_of(s.date)) for s in sessions}),
    }
    results = {}
    try:
        account_at = _now()
        account = client.get_account()
        _write_json(out_dir / "account.json", account)
        provenance["requests"].append({"what": "paper account", "host": PAPER_TRADING_URL,
                                       "retrieved_utc": _iso(account_at)})

        daily_start, daily_end = str(sessions[0].date), str(last.date)
        daily_at = _now()
        daily = client.get_bars(symbol, "1Day", daily_start, daily_end, args.feed, ADJUSTMENT)
        provenance["requests"].append({
            "what": "daily bars", "host": DATA_URL, "timeframe": "1Day",
            "start": daily_start, "end": daily_end, "pages": daily["pages"],
            "rows": len(daily["bars"]), "retrieved_utc": _iso(daily_at)})

        minute_start = _iso(last.open_utc)
        minute_end = _iso(last.close_utc - timedelta(minutes=1))
        minute_at = _now()
        minute = client.get_bars(symbol, "1Min", minute_start, minute_end, args.feed, ADJUSTMENT)
        provenance["requests"].append({
            "what": "1-minute bars, regular session", "host": DATA_URL, "timeframe": "1Min",
            "session_date": str(last.date), "early_close": last.early_close,
            "start": minute_start, "end": minute_end, "pages": minute["pages"],
            "rows": len(minute["bars"]), "retrieved_utc": _iso(minute_at)})
    except AlpacaAccessError as exc:
        provenance["error"] = str(exc)
        _write_json(out_dir / "provenance.json", provenance)
        hint = {401: "keys missing or wrong", 403: f"your plan may not allow feed={args.feed}",
                429: "rate limit; wait a minute"}.get(exc.status_code, "")
        print(f"FAILED: {exc}" + (f" ({hint})" if hint else ""))
        print(f"No feed substitution was made. Provenance: {out_dir}")
        return 1

    # The bars endpoint does not echo the feed back; a 200 response to an
    # explicit feed= request is the only evidence of which feed was served.
    provenance["actual_feed"] = f"{args.feed} (request accepted; API does not echo feed)"

    daily_df = bars_to_frame(daily["bars"])
    minute_df = bars_to_frame(minute["bars"])
    daily_df.to_csv(out_dir / f"{symbol}_1Day_{args.feed}.csv", index=False)
    minute_df.to_csv(out_dir / f"{symbol}_1Min_{last.date}_{args.feed}.csv", index=False)

    results["daily"] = {"structure": check_bars(daily_df),
                        "coverage": check_daily_coverage(daily_df, sessions)}
    results["minute"] = {"structure": check_bars(minute_df),
                         "coverage": check_minute_coverage(minute_df, last)}
    _write_json(out_dir / "validation.json", results)
    _write_json(out_dir / "provenance.json", provenance)

    print(f"Account status: {account['status']}  equity: {account['equity']} {account['currency']}")
    print(f"Feed requested: {args.feed}")
    for name, res in results.items():
        flag = "PROBLEMS" if has_problems(res["structure"]) else "ok"
        print(f"{name}: rows={res['structure']['rows']} structure={flag} coverage={res['coverage']}")
    print(f"Saved to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
