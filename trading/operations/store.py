"""Append-only SQLite records for the dry run, kept outside OneDrive (paths.db_path()).

No credentials and no account identifiers are ever stored. Decisions are unique per
(session_date, minute_utc), so a restart can never record a second decision for a minute.
Reports are amend-only: a changed report becomes a new version; old versions are kept.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, kind TEXT, session_date TEXT, environment TEXT, pid INTEGER, started_utc TEXT,
  start_class TEXT, heartbeat_utc TEXT, ended_utc TEXT, exit_reason TEXT, code_fingerprint TEXT,
  code_version TEXT, config_json TEXT);
CREATE TABLE IF NOT EXISTS heartbeats (run_id TEXT, ts_utc TEXT);
CREATE TABLE IF NOT EXISTS checks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, session_date TEXT, ts_utc TEXT, stage TEXT, name TEXT,
  ok INTEGER, dependency INTEGER, detail_json TEXT);
CREATE TABLE IF NOT EXISTS decisions (
  session_date TEXT, minute_utc TEXT, run_id TEXT, decided_utc TEXT, phase TEXT, allowed INTEGER,
  reasons_json TEXT, inputs_json TEXT, PRIMARY KEY (session_date, minute_utc));
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, session_date TEXT, ts_utc TEXT, level TEXT, kind TEXT,
  message TEXT);
CREATE TABLE IF NOT EXISTS reports (
  session_date TEXT, version INTEGER, created_utc TEXT, classification TEXT, report_sha TEXT, report_json TEXT,
  amends_version INTEGER, PRIMARY KEY (session_date, version));
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OpsStore:
    def __init__(self, path: Path, read_only: bool = False):
        self.path = Path(path)
        if read_only:
            self.db = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True, timeout=5)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.path, timeout=10)
            self.db.executescript(SCHEMA)
            self.db.commit()
        self.db.row_factory = sqlite3.Row

    def close(self):
        self.db.close()

    def _x(self, sql, args=()):
        cur = self.db.execute(sql, args)
        self.db.commit()
        return cur

    # ---------------------------------------------------------------- writes
    def begin_run(self, run_id, kind, session_date, environment, pid, started_utc, start_class, fingerprint,
                  code_version, config: dict):
        self._x("INSERT INTO runs (run_id, kind, session_date, environment, pid, started_utc, start_class, heartbeat_utc,"
                " code_fingerprint, code_version, config_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, kind, session_date, environment, pid, started_utc, start_class, started_utc, fingerprint,
                 code_version, json.dumps(config, default=str)))

    def heartbeat(self, run_id, ts):
        self._x("UPDATE runs SET heartbeat_utc=? WHERE run_id=?", (ts, run_id))
        self._x("INSERT INTO heartbeats (run_id, ts_utc) VALUES (?,?)", (run_id, ts))

    def end_run(self, run_id, ts, reason):
        self._x("UPDATE runs SET ended_utc=?, exit_reason=?, heartbeat_utc=? WHERE run_id=?", (ts, reason, ts, run_id))

    def add_check(self, run_id, session_date, ts, stage, name, ok, dependency, detail):
        self._x("INSERT INTO checks (run_id, session_date, ts_utc, stage, name, ok, dependency, detail_json)"
                " VALUES (?,?,?,?,?,?,?,?)", (run_id, session_date, ts, stage, name, int(bool(ok)), int(bool(dependency)),
                                              json.dumps(detail, default=str)))

    def add_decision(self, session_date, minute_utc, run_id, decided_utc, phase, allowed, reasons, inputs) -> bool:
        cur = self._x("INSERT OR IGNORE INTO decisions VALUES (?,?,?,?,?,?,?,?)",
                      (session_date, minute_utc, run_id, decided_utc, phase, int(bool(allowed)),
                       json.dumps(list(reasons)), json.dumps(inputs, default=str)))
        return cur.rowcount == 1

    def event(self, run_id, session_date, ts, level, kind, message):
        self._x("INSERT INTO events (run_id, session_date, ts_utc, level, kind, message) VALUES (?,?,?,?,?,?)",
                (run_id, session_date, ts, level, kind, message[:2000]))

    def save_report(self, session_date, classification, report: dict) -> int:
        body = json.dumps(report, sort_keys=True, default=str)
        sha = hashlib.sha256(body.encode()).hexdigest()
        last = self.db.execute("SELECT version, report_sha FROM reports WHERE session_date=? ORDER BY version DESC LIMIT 1",
                               (session_date,)).fetchone()
        if last and last["report_sha"] == sha:
            return last["version"]
        v = (last["version"] + 1) if last else 1
        self._x("INSERT INTO reports VALUES (?,?,?,?,?,?,?)",
                (session_date, v, now_iso(), classification, sha, body, last["version"] if last else None))
        return v

    # ---------------------------------------------------------------- reads
    def rows(self, sql, args=()):
        return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def runs_for(self, d):
        return self.rows("SELECT * FROM runs WHERE session_date=? AND kind='session' ORDER BY started_utc", (d,))

    def decisions_for(self, d):
        return self.rows("SELECT * FROM decisions WHERE session_date=? ORDER BY minute_utc", (d,))

    def checks_for(self, d):
        return self.rows("SELECT c.* FROM checks c JOIN runs r ON r.run_id=c.run_id WHERE c.session_date=? AND r.kind='session'"
                         " ORDER BY c.id", (d,))

    def events_for(self, d):
        return self.rows("SELECT e.* FROM events e JOIN runs r ON r.run_id=e.run_id WHERE e.session_date=? AND r.kind='session'"
                         " ORDER BY e.id", (d,))

    def heartbeats_for(self, d):
        return self.rows("SELECT h.ts_utc, h.run_id FROM heartbeats h JOIN runs r ON r.run_id=h.run_id"
                         " WHERE r.session_date=? AND r.kind='session' ORDER BY h.ts_utc", (d,))

    def session_dates(self):
        return [r["session_date"] for r in self.rows("SELECT DISTINCT session_date FROM runs WHERE kind='session'"
                                                     " ORDER BY session_date")]

    def latest_run(self):
        r = self.rows("SELECT * FROM runs ORDER BY started_utc DESC LIMIT 1")
        return r[0] if r else None

    def latest_report(self, d):
        r = self.rows("SELECT * FROM reports WHERE session_date=? ORDER BY version DESC LIMIT 1", (d,))
        return r[0] if r else None
