"""Data health from the monitoring store, read-only (no network, no broker code).

Freshness uses source time: a bar's end (bar start + 60 s) versus now. A healthy connection is not
suitability: in Milestone 1 every result also carries the reason that execution suitability is not
established (IEX is a single exchange, and no strategy defines data requirements).
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from trading.operations.gate import DataHealth

FRESH_S = 180            # matches the monitor's FRESH label (bar ended at most 3 minutes ago)
WORKER_ALIVE_S = 20      # matches the monitor's heartbeat rule
SUITABILITY_REASON = ("data suitability for execution not established (no strategy data requirements; "
                      "the live feed is labelled, not certified)")


def _parse(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def read(now: datetime, monitor_db: Path) -> DataHealth:
    try:
        db = sqlite3.connect(f"file:{Path(monitor_db).as_posix()}?mode=ro", uri=True, timeout=2)
    except sqlite3.Error as exc:
        return DataHealth(False, None, {}, (f"monitoring store unreadable ({type(exc).__name__})", SUITABILITY_REASON))
    try:
        w = db.execute("SELECT state, heartbeat_utc, config_json FROM worker WHERE id=1").fetchone()
        if not w:
            return DataHealth(False, None, {}, ("monitoring worker has no record", SUITABILITY_REASON))
        state, hb, cfg = w
        cfg = json.loads(cfg) if cfg else {}
        feed, symbols = cfg.get("feed"), cfg.get("symbols") or []
        hb_age = (now - _parse(hb)).total_seconds() if hb else None
        alive = hb_age is not None and hb_age <= WORKER_ALIVE_S and state not in ("stopped",)
        reasons = [] if alive else [f"monitoring worker not alive (state {state}, heartbeat age {hb_age if hb_age is None else round(hb_age)} s)"]
        out = {}
        for sym in symbols:
            row = db.execute("SELECT MAX(t_utc) FROM bars WHERE symbol=? AND feed=?", (sym, feed)).fetchone()
            start = _parse(row[0]) if row and row[0] else None
            age = None if start is None else (now - (start + timedelta(seconds=60))).total_seconds()
            fresh = age is not None and age <= FRESH_S
            out[sym] = {"age_s": None if age is None else round(age, 1), "fresh": fresh}
            if not fresh:
                reasons.append(f"{sym} {feed}: newest bar ended {'never' if age is None else f'{round(age)} s ago'} (stale)")
        if not symbols:
            reasons.append("monitoring worker has no symbols configured")
        reasons.append(SUITABILITY_REASON)
        return DataHealth(alive, feed, out, tuple(reasons))
    except (sqlite3.Error, ValueError, TypeError) as exc:
        return DataHealth(False, None, {}, (f"monitoring store unreadable ({type(exc).__name__})", SUITABILITY_REASON))
    finally:
        db.close()
