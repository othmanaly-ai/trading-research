"""Build a HISTORICAL REPLAY event log from stored, validated Alpaca bars.

Uses the same engine and event builder as DEMO, with its own mode, source,
feed and banner. Refuses to build (never falls back to synthetic data) when
stored data is missing, unusable, or outside the allowed periods.
"""

import json
from datetime import date, timedelta
from pathlib import Path

from trading.dashboard.demo_replay import Context, DemoReplay, build_replay
from trading.events import MODE_HISTORICAL_REPLAY
from trading.history import HISTORY_DIR, HistoryError, load_days, period_of, read_manifest
from trading.sessions import sessions_between

SOURCE = "alpaca_history"
DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "dashboard" / "historical_config.json"
NEVER_ALLOWED = {"final"}


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_historical(config: dict, root: Path = HISTORY_DIR) -> DemoReplay:
    symbol, feed, adj = config["symbol"], config["feed"], config["adjustment"]
    manifest = read_manifest(symbol, feed, adj, root)
    if manifest is None:
        raise HistoryError(
            f"No stored {symbol} {feed} history. With Alpaca paper keys in .env, run: "
            f".venv\\Scripts\\python -m trading.history --symbol {symbol} --feed {feed} "
            f"--start 2016-01-04 --end 2016-06-30")

    first = date.fromisoformat(config["first_session"])
    pool = sessions_between(first - timedelta(days=90), first + timedelta(days=45))
    idx = next(k for k, s in enumerate(pool) if s.date >= first)
    n, warm = config["sessions"], config["warmup_sessions"]
    replay = pool[idx: idx + n]
    engine_sessions = pool[idx - warm: idx + n + 1]

    allowed = set(config.get("allowed_periods", ["development"])) - NEVER_ALLOWED
    bad = sorted({period_of(s.date) or "outside defined periods" for s in replay} - allowed)
    if bad:
        raise HistoryError(f"replay sessions fall in {bad}; allowed periods are {sorted(allowed)}")

    days = load_days(symbol, feed, adj, engine_sessions, root)
    usable = [s for s in replay if s.date in days]
    if not usable:
        raise HistoryError("none of the requested replay sessions has usable stored data")

    ctx = Context(
        SOURCE, MODE_HISTORICAL_REPLAY, feed,
        f"HISTORICAL REPLAY: Alpaca {feed.upper()} 1-minute bars for {symbol} ({adj} adjustment), "
        f"retrieved {manifest['retrieved_utc']}. Fills and P&L are simulated on historical prices; "
        f"not broker results.")
    instruments = [{"id": symbol, "label": f"{symbol} ({feed.upper()}, Alpaca)"}]
    return build_replay(ctx, instruments, {symbol: days}, config["instances"], engine_sessions, replay,
                        extra_meta={"provenance": {
                            "source": manifest["source"], "requested_feed": manifest["requested_feed"],
                            "actual_feed": manifest["actual_feed"], "adjustment": manifest["adjustment"],
                            "retrieved_utc": manifest["retrieved_utc"],
                            "replay_sessions_expected": len(replay),
                            "replay_sessions_with_usable_data": len(usable),
                            "warmup_sessions_with_usable_data": sum(
                                1 for s in engine_sessions[:warm] if s.date in days),
                            "periods": sorted({period_of(s.date) for s in replay}),
                        }})
