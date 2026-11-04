"""Monitoring records (SQLite, data/monitoring/monitor.sqlite, git-ignored).

No broker imports: the dashboard server reads this module. Freshness is computed at read time
from source timestamps (Alpaca bar start times) and the exchange calendar, so the city and the
table always show the same derived values for the same records.
"""

import json
import sqlite3
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from trading.experiment import PERIODS
from trading.sessions import MARKET_TZ, sessions_between

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MONITOR_DIR = PROJECT_ROOT / "data" / "monitoring"
DB_PATH = MONITOR_DIR / "monitor.sqlite"
LOCK_PATH = MONITOR_DIR / "worker.lock"
LOG_PATH = MONITOR_DIR / "worker.log"

# Reserved research periods end here; monitoring never requests or keeps bars on or before it.
RESERVED_END: date = max(end for _start, end in PERIODS.values())
DEFAULT_SYMBOLS = ("SPY", "QQQ", "IWM")
FEEDS = {
    "iex": {"label": "IEX (single exchange, real-time on the free plan; partial volume, quiet minutes "
                     "have no bar)", "expected_lag_s": 0},
    "sip": {"label": "SIP (all US exchanges, consolidated) delayed 15 minutes on the free plan",
            "expected_lag_s": 15 * 60},
}
POLL_SECONDS = 60
HEARTBEAT_DEAD_S = 20           # no heartbeat for this long: the worker is not running
STALE_AFTER_S = 180             # beyond the feed's expected lag
DESIRED = ("running", "paused", "stopped")
LABEL = "MONITORING DATA · read-only · not a research dataset · not a trading signal"

_LOCK = threading.Lock()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds") if dt else None


def parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def market_state(now: datetime) -> dict:
    """Exchange-calendar state at `now`: open/closed, the relevant session, the next open."""
    today = now.astimezone(timezone.utc).date()
    sessions = sessions_between(today - timedelta(days=7), today + timedelta(days=10))
    current = next((s for s in sessions if s.open_utc <= now < s.close_utc), None)
    if current:
        return {"open": True, "session": current, "reason": "regular session",
                "next_open": None, "last_session": current}
    past = [s for s in sessions if s.close_utc <= now]
    upcoming = [s for s in sessions if s.open_utc > now]
    last, nxt = (past[-1] if past else None), (upcoming[0] if upcoming else None)
    et = now.astimezone(_tz())
    if last and last.date == et.date():
        reason = "after the close" + (" (early close)" if last.early_close else "")
    elif nxt and nxt.date == et.date():
        reason = "before the open"
    else:
        reason = "weekend or exchange holiday"
    return {"open": False, "session": None, "reason": reason, "next_open": nxt.open_utc if nxt else None,
            "last_session": last}


def _tz():
    from zoneinfo import ZoneInfo
    return ZoneInfo(MARKET_TZ)


def session_date_et(t: datetime) -> date:
    return t.astimezone(_tz()).date()


class MonitorStore:
    def __init__(self, path: Path | None = None):
        path = path or DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        with _LOCK:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS worker (
                id INTEGER PRIMARY KEY CHECK (id = 1), pid INTEGER, state TEXT, detail TEXT,
                started_utc TEXT, heartbeat_utc TEXT, stopped_utc TEXT, exit_reason TEXT, config_json TEXT,
                last_poll_utc TEXT, last_success_utc TEXT, next_poll_utc TEXT, consecutive_failures INTEGER DEFAULT 0,
                backoff_until_utc TEXT, polls INTEGER DEFAULT 0, requests INTEGER DEFAULT 0,
                bars_inserted INTEGER DEFAULT 0, duplicates_ignored INTEGER DEFAULT 0,
                reserved_discarded INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS control (
                id INTEGER PRIMARY KEY CHECK (id = 1), desired TEXT, requested_utc TEXT, requested_by TEXT);
            CREATE TABLE IF NOT EXISTS bars (
                symbol TEXT, feed TEXT, t_utc TEXT, session_date TEXT, o REAL, h REAL, l REAL, c REAL,
                v INTEGER, n INTEGER, vw REAL, received_utc TEXT, PRIMARY KEY (symbol, feed, t_utc));
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts_utc TEXT, level TEXT, kind TEXT, message TEXT);
            CREATE TABLE IF NOT EXISTS spawns (ts_utc TEXT, requested_by TEXT, pid INTEGER, note TEXT);
            INSERT OR IGNORE INTO control (id, desired, requested_utc, requested_by) VALUES (1, 'stopped', NULL, 'default');
            INSERT OR IGNORE INTO worker (id, state, detail) VALUES (1, 'stopped', 'never started');
            """)
            self.db.commit()

    def close(self):
        self.db.close()

    # ---- control ---------------------------------------------------------------------
    def desired(self) -> str:
        return self.db.execute("SELECT desired FROM control WHERE id=1").fetchone()[0]

    def set_desired(self, desired: str, by: str, now: datetime | None = None) -> None:
        if desired not in DESIRED:
            raise ValueError(f"desired state must be one of {DESIRED}")
        self.db.execute("UPDATE control SET desired=?, requested_utc=?, requested_by=? WHERE id=1",
                        (desired, iso(now or now_utc()), by))
        self.db.commit()
        self.event("info", "control", f"desired state set to {desired} by {by}", now)

    # ---- worker status ------------------------------------------------------------------
    def update_worker(self, **fields) -> None:
        sets = ", ".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE worker SET {sets} WHERE id=1", list(fields.values()))
        self.db.commit()

    def bump(self, **increments) -> None:
        sets = ", ".join(f"{k}={k}+?" for k in increments)
        self.db.execute(f"UPDATE worker SET {sets} WHERE id=1", list(increments.values()))
        self.db.commit()

    def worker(self) -> dict:
        w = dict(self.db.execute("SELECT * FROM worker WHERE id=1").fetchone())
        w["config"] = json.loads(w.pop("config_json")) if w.get("config_json") else None
        return w

    def event(self, level: str, kind: str, message: str, now: datetime | None = None) -> None:
        self.db.execute("INSERT INTO events (ts_utc, level, kind, message) VALUES (?,?,?,?)",
                        (iso(now or now_utc()), level, kind, message[:500]))
        self.db.execute("DELETE FROM events WHERE id <= (SELECT MAX(id) FROM events) - 500")
        self.db.commit()

    def events(self, limit: int = 30) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))]

    def record_spawn(self, by: str, pid: int | None, note: str, now: datetime | None = None) -> None:
        self.db.execute("INSERT INTO spawns VALUES (?,?,?,?)", (iso(now or now_utc()), by, pid, note))
        self.db.commit()

    def spawns_since(self, since: datetime) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM spawns WHERE ts_utc >= ? ORDER BY ts_utc",
                                                 (iso(since),))]

    # ---- bars -------------------------------------------------------------------------
    def insert_bars(self, symbol: str, feed: str, bars: list[dict], received: datetime) -> dict:
        """INSERT OR IGNORE on (symbol, feed, bar start): repeats never create duplicates.
        Bars dated on or before the reserved-period end are discarded, never stored."""
        new = dup = reserved = 0
        for b in bars:
            t = parse(b["t"])
            sd = session_date_et(t)
            if sd <= RESERVED_END:
                reserved += 1
                continue
            cur = self.db.execute(
                "INSERT OR IGNORE INTO bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (symbol, feed, iso(t), sd.isoformat(), b.get("o"), b.get("h"), b.get("l"), b.get("c"),
                 b.get("v"), b.get("n"), b.get("vw"), iso(received)))
            if cur.rowcount:
                new += 1
            else:
                dup += 1
        self.db.commit()
        return {"new": new, "duplicates": dup, "reserved_discarded": reserved}

    def last_bar(self, symbol: str, feed: str) -> dict | None:
        r = self.db.execute("SELECT * FROM bars WHERE symbol=? AND feed=? ORDER BY t_utc DESC LIMIT 1",
                            (symbol, feed)).fetchone()
        return dict(r) if r else None

    def bars(self, symbol: str, feed: str, limit: int = 30) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM bars WHERE symbol=? AND feed=? ORDER BY t_utc DESC LIMIT ?", (symbol, feed, limit))]

    def count_session(self, symbol: str, feed: str, session_date: str) -> int:
        return self.db.execute("SELECT COUNT(*) FROM bars WHERE symbol=? AND feed=? AND session_date=?",
                               (symbol, feed, session_date)).fetchone()[0]

    # ---- the one view both the city and the table render ------------------------------
    def status(self, now: datetime | None = None) -> dict:
        now = now or now_utc()
        w = self.worker()
        cfg = w["config"] or {"symbols": list(DEFAULT_SYMBOLS), "feed": "iex", "poll_seconds": POLL_SECONDS}
        feed = cfg["feed"]
        hb = parse(w.get("heartbeat_utc"))
        alive = hb is not None and (now - hb).total_seconds() <= HEARTBEAT_DEAD_S and w["state"] != "stopped"
        mk = market_state(now)
        rows = []
        for sym in cfg["symbols"]:
            last = self.last_bar(sym, feed)
            row = {"symbol": sym, "feed": feed, "feed_label": FEEDS[feed]["label"], "last_bar_start_utc": None,
                   "last_bar_end_utc": None, "received_utc": None, "close": None, "volume": None,
                   "source_age_s": None, "session_bars": 0}
            if last:
                start = parse(last["t_utc"])
                end = start + timedelta(minutes=1)
                row.update(last_bar_start_utc=last["t_utc"], last_bar_end_utc=iso(end), received_utc=last["received_utc"],
                           close=last["c"], volume=last["v"], session_date=last["session_date"],
                           source_age_s=int((now - end).total_seconds()))
            if mk["open"]:
                row["session_bars"] = self.count_session(sym, feed, mk["session"].date.isoformat())
            row["freshness"], row["freshness_detail"] = _freshness(row, mk, alive, w["state"], feed, now)
            rows.append(row)
        return {
            "label": LABEL, "now_utc": iso(now), "reserved_end": RESERVED_END.isoformat(),
            "market": {"open": mk["open"], "reason": mk["reason"], "next_open_utc": iso(mk["next_open"]),
                       "session_date": mk["session"].date.isoformat() if mk["open"] else None,
                       "session_close_utc": iso(mk["session"].close_utc) if mk["open"] else None},
            "worker": {**w, "alive": alive, "heartbeat_age_s": int((now - hb).total_seconds()) if hb else None,
                       "effective_state": w["state"] if alive else ("stopped" if w["state"] == "stopped"
                                                                    else "not running")},
            "desired": self.desired(), "config": cfg, "symbols": rows, "events": self.events(20),
        }


def _freshness(row: dict, mk: dict, alive: bool, state: str, feed: str, now: datetime) -> tuple[str, str]:
    if state == "stopped":
        return "STOPPED", "worker stopped (by request or never started); values are the last stored ones"
    if not alive:
        return "DISCONNECTED", "the monitoring worker is not responding; values are the last stored ones"
    if state == "paused":
        return "PAUSED", "worker paused by request; no new data is being fetched"
    if state in ("disconnected", "error", "refused"):
        return "DISCONNECTED", f"worker state {state}; see events"
    if not mk["open"]:
        return "MARKET CLOSED", f"{mk['reason']}; next open {iso(mk['next_open']) or 'unknown'}"
    if row["last_bar_start_utc"] is None or row.get("session_date") != mk["session"].date.isoformat():
        return "NO DATA YET", "no bar stored for the current session yet"
    lag = row["source_age_s"] - FEEDS[feed]["expected_lag_s"]
    if lag <= STALE_AFTER_S:
        return "FRESH", f"last bar ended {row['source_age_s']} s ago"
    note = " (IEX has no bar in minutes without IEX trades; not necessarily an outage)" if feed == "iex" else ""
    return "STALE", f"no new bar for {row['source_age_s'] // 60} min{note}"
