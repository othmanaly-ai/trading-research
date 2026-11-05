"""Read-only data-quality comparison: delayed SIP (consolidated tape) vs IEX (one exchange).

Runs inside the monitoring worker process (which holds the read-only client). Stores ORIGINAL
observations with retrieval timestamps and revision history; comparisons are derived records that
name the exact revisions they used. Nothing here alters the live IEX bars, the freshness labels,
or any research dataset, and nothing feeds a trading decision.

Delay boundary: Alpaca's free plan withholds the latest 15 minutes of SIP data. A minute is only
requested once its END is at least SIP_DELAY + SAFETY_MARGIN (15 + 5 = 20 minutes) in the past.
Each SIP observation records `provider_available_utc` (bar end + 15 min: the earliest moment this
plan allows it to be known) and `retrieved_utc` (when we actually received it).

Classification (deterministic rules; no price or volume tolerances are invented):
  consistent_subset          both bars present and IEX lies inside SIP (IEX high <= SIP high,
                             IEX low >= SIP low, IEX volume <= SIP volume). Differences are
                             expected: IEX is a subset of consolidated trading.
  expected_coverage_difference  SIP has a bar, IEX has none (no IEX trades that minute).
  both_absent                no bar in either feed (no trades reported in that minute).
  unresolved_anomaly         SIP missing while IEX present, or IEX outside the SIP range or
                             above SIP volume. Plausible causes include trade-condition
                             filtering differences between the feeds; not proven defects.
  structural_defect          a bar violates its own invariants (high < max(open, close),
                             low > min(open, close), negative volume, missing/non-numeric
                             fields) or has an unexpected timestamp (not minute-aligned,
                             outside the regular session, conflicting duplicates in one response).
Access failures are recorded per request window; their minutes stay pending, never compared.
"""

import json
import math
from datetime import datetime, timedelta, timezone

from trading.monitor import store as st

SIP_DELAY = timedelta(minutes=15)
SAFETY_MARGIN = timedelta(minutes=5)
CYCLE_EVERY = timedelta(minutes=5)
MAX_CHUNK = timedelta(minutes=120)          # bounded request window; a backlog is worked off in chunks
EOD_RECHECK_AFTER = timedelta(minutes=30)   # after the close + delay: one full-day re-observation
BACKOFF = (60, 120, 300, 600)
ACCESS_REFUSED_WAIT = 1800
RECOVERY_LOOKBACK_SESSIONS = 5          # unfinished monitored sessions older than this are reported incomplete
MAX_HISTORICAL_ACCESS_FAILURES = 3      # then a past session is reported incomplete (never "successful")
REQUEST_BUDGET_PER_HOUR = 120           # quality requests; recovery never floods the provider
BACKLOG_GAP = timedelta(seconds=5)      # pause between backlog chunks
SESSION_STATES = ("in_progress", "provisional", "finalized", "incomplete")
FIELDS = ("o", "h", "l", "c", "v")
CATEGORIES = ("consistent_subset", "expected_coverage_difference", "both_absent", "unresolved_anomaly",
              "structural_defect")

SCHEMA = """
CREATE TABLE IF NOT EXISTS q_obs (
    symbol TEXT, feed TEXT, t_utc TEXT, revision INTEGER, session_date TEXT,
    o REAL, h REAL, l REAL, c REAL, v REAL, n REAL, vw REAL, raw_json TEXT, defects TEXT,
    retrieved_utc TEXT, provider_available_utc TEXT, run_id INTEGER,
    PRIMARY KEY (symbol, feed, t_utc, revision));
CREATE TABLE IF NOT EXISTS q_compare (
    symbol TEXT, t_utc TEXT, session_date TEXT, sip_rev INTEGER, iex_rev INTEGER, category TEXT, detail TEXT,
    sip_present INTEGER, iex_present INTEGER, live_iex_present INTEGER,
    d_o_usd REAL, d_h_usd REAL, d_l_usd REAL, d_c_usd REAL, d_o_bps REAL, d_h_bps REAL, d_l_bps REAL, d_c_bps REAL,
    iex_volume REAL, sip_volume REAL, iex_volume_share REAL, sip_provider_available_utc TEXT,
    sip_retrieved_utc TEXT, iex_retrieved_utc TEXT, live_iex_received_utc TEXT, compared_utc TEXT, run_id INTEGER,
    PRIMARY KEY (symbol, t_utc, sip_rev, iex_rev));
CREATE TABLE IF NOT EXISTS q_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, session_date TEXT, started_utc TEXT, finished_utc TEXT,
    window_start_utc TEXT, window_end_utc TEXT, status TEXT, http_status INTEGER, requests INTEGER DEFAULT 0,
    sip_bars INTEGER DEFAULT 0, iex_bars INTEGER DEFAULT 0, new_obs INTEGER DEFAULT 0,
    duplicate_obs INTEGER DEFAULT 0, corrections INTEGER DEFAULT 0, defects INTEGER DEFAULT 0,
    compared INTEGER DEFAULT 0, error TEXT);
CREATE TABLE IF NOT EXISTS q_state (
    session_date TEXT PRIMARY KEY, compared_through_utc TEXT, eod_recheck_utc TEXT);
CREATE TABLE IF NOT EXISTS q_health (
    id INTEGER PRIMARY KEY CHECK (id = 1), state TEXT, detail TEXT, failures INTEGER DEFAULT 0,
    backoff_until_utc TEXT, last_success_utc TEXT, updated_utc TEXT);
INSERT OR IGNORE INTO q_health (id, state, detail) VALUES (1, 'idle', 'no comparison has run yet');
CREATE TABLE IF NOT EXISTS q_reports (
    session_date TEXT, version INTEGER, status TEXT, created_utc TEXT, report_sha TEXT, report_json TEXT,
    amends_version INTEGER, PRIMARY KEY (session_date, version));
"""
MIGRATIONS = {
    "q_state": [("status", "TEXT"), ("detail", "TEXT"), ("access_failures", "INTEGER DEFAULT 0"),
                ("finalized_utc", "TEXT"), ("first_monitored_utc", "TEXT"), ("updated_utc", "TEXT")],
    "q_compare": [("live_o", "REAL"), ("live_h", "REAL"), ("live_l", "REAL"), ("live_c", "REAL"), ("live_v", "REAL"),
                  ("d_c_usd_live", "REAL"), ("d_c_bps_live", "REAL")],
}


def ensure_schema(store: st.MonitorStore) -> None:
    store.db.executescript(SCHEMA)
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in store.db.execute(f"PRAGMA table_info({table})")}
        for name, decl in cols:
            if name not in have:
                store.db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    # Derived fields only: comparisons recorded before the live columns existed get the live IEX values
    # from the live-capture table (which is the original evidence and is not modified).
    store.db.execute("""
        UPDATE q_compare SET
          live_o = (SELECT o FROM bars b WHERE b.symbol=q_compare.symbol AND b.feed='iex' AND b.t_utc=q_compare.t_utc),
          live_h = (SELECT h FROM bars b WHERE b.symbol=q_compare.symbol AND b.feed='iex' AND b.t_utc=q_compare.t_utc),
          live_l = (SELECT l FROM bars b WHERE b.symbol=q_compare.symbol AND b.feed='iex' AND b.t_utc=q_compare.t_utc),
          live_c = (SELECT c FROM bars b WHERE b.symbol=q_compare.symbol AND b.feed='iex' AND b.t_utc=q_compare.t_utc),
          live_v = (SELECT v FROM bars b WHERE b.symbol=q_compare.symbol AND b.feed='iex' AND b.t_utc=q_compare.t_utc)
        WHERE live_iex_present = 1 AND live_c IS NULL""")
    store.db.execute("""
        UPDATE q_compare SET
          d_c_usd_live = live_c - (SELECT c FROM q_obs o WHERE o.symbol=q_compare.symbol AND o.feed='sip'
                                   AND o.t_utc=q_compare.t_utc AND o.revision=q_compare.sip_rev),
          d_c_bps_live = (live_c - (SELECT c FROM q_obs o WHERE o.symbol=q_compare.symbol AND o.feed='sip'
                                    AND o.t_utc=q_compare.t_utc AND o.revision=q_compare.sip_rev)) * 10000.0 /
                         (SELECT c FROM q_obs o WHERE o.symbol=q_compare.symbol AND o.feed='sip'
                          AND o.t_utc=q_compare.t_utc AND o.revision=q_compare.sip_rev)
        WHERE live_c IS NOT NULL AND d_c_bps_live IS NULL AND sip_present = 1""")
    store.db.commit()


def boundary(now: datetime) -> datetime:
    """Start of the first minute that is NOT yet comparable: every minute t with t + 1 min <= this is."""
    return (now - SIP_DELAY - SAFETY_MARGIN).replace(second=0, microsecond=0)


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def bar_defects(bar: dict, session) -> list[str]:
    out = []
    for f in FIELDS + ("t",):
        if f not in bar:
            out.append(f"missing field {f}")
    if any(f"missing field {f}" in out for f in FIELDS):
        return out
    if not all(_num(bar[f]) for f in FIELDS):
        return out + ["non-numeric OHLCV"]
    o, h, l, c, v = (bar[f] for f in FIELDS)
    if h < max(o, c) or l > min(o, c) or h < l:
        out.append("OHLC invariant violated")
    if v < 0:
        out.append("negative volume")
    try:
        t = st.parse(bar["t"])
    except (TypeError, ValueError):
        return out + ["unparseable timestamp"]
    if t.second or t.microsecond:
        out.append("timestamp not minute-aligned")
    if not (session.open_utc <= t < session.close_utc):
        out.append("timestamp outside the regular session")
    return out


def _bps(a, b):
    return (a - b) / b * 1e4 if _num(a) and _num(b) and b else None


def classify(sip: dict | None, iex: dict | None) -> tuple[str, str]:
    if (sip and sip["defects"]) or (iex and iex["defects"]):
        which = [f"{n}: {', '.join(json.loads(x['defects']))}" for n, x in (("SIP", sip), ("IEX", iex)) if x and x["defects"]]
        return "structural_defect", "; ".join(which)
    if sip and iex:
        issues = []
        if iex["h"] > sip["h"]:
            issues.append("IEX high above SIP high")
        if iex["l"] < sip["l"]:
            issues.append("IEX low below SIP low")
        if iex["v"] > sip["v"]:
            issues.append("IEX volume above SIP volume")
        if issues:
            return "unresolved_anomaly", "; ".join(issues) + " (IEX should be a subset of consolidated trading; " \
                                                             "possibly trade-condition filtering differences)"
        return "consistent_subset", "IEX inside the SIP range; differences reflect different trade coverage"
    if sip and not iex:
        return "expected_coverage_difference", "SIP bar present, no IEX bar (no IEX trades this minute)"
    if iex and not sip:
        return "unresolved_anomaly", "IEX bar present but no consolidated (SIP) bar"
    return "both_absent", "no bar in either feed"


class QualityChecker:
    def __init__(self, store: st.MonitorStore, symbols, clock=st.now_utc):
        self.store, self.symbols, self.clock = store, list(symbols), clock
        ensure_schema(store)
        self.next_cycle: datetime | None = None

    # ---- records -----------------------------------------------------------------------
    def _health(self, state: str, detail: str, **extra) -> None:
        sets = ", ".join(f"{k}=?" for k in ("state", "detail", "updated_utc", *extra))
        self.store.db.execute(f"UPDATE q_health SET {sets} WHERE id=1",
                              [state, detail, st.iso(self.clock()), *extra.values()])
        self.store.db.commit()

    def health(self) -> dict:
        return dict(self.store.db.execute("SELECT * FROM q_health WHERE id=1").fetchone())

    def _latest(self, symbol, feed, t_iso):
        return self.store.db.execute("SELECT * FROM q_obs WHERE symbol=? AND feed=? AND t_utc=? ORDER BY revision DESC "
                                     "LIMIT 1", (symbol, feed, t_iso)).fetchone()

    def _observe(self, symbol, feed, bar, session, retrieved, run_id, counts, window, extra_defects=()) -> None:
        defects = bar_defects(bar, session) + list(extra_defects)
        if _ts_ok(bar) and not (window[0] <= st.parse(bar["t"]) < window[1]):
            defects.append("timestamp outside the requested window")
        try:
            t = st.parse(bar["t"])
            t_iso = st.iso(t)
        except (TypeError, ValueError, KeyError):
            t, t_iso = None, f"unparseable:{json.dumps(bar.get('t'))}"
        vals = {f: bar.get(f) for f in ("o", "h", "l", "c", "v", "n", "vw")}
        prev = self._latest(symbol, feed, t_iso)
        same = prev is not None and all(prev[k] == (vals[k] if _num(vals[k]) else None)
                                        for k in ("o", "h", "l", "c", "v", "n", "vw"))
        if same and (prev["defects"] or None) == (json.dumps(defects) if defects else None):
            counts["duplicate_obs"] += 1                  # same values seen again: evidence unchanged
            return
        rev = 1 if prev is None else prev["revision"] + 1
        if prev is not None:
            counts["corrections"] += 1
            self.store.event("warning", "quality-correction",
                             f"{feed.upper()} {symbol} {t_iso} revised (revision {rev}); earlier revision kept", self.clock())
        if defects:
            counts["defects"] += 1
        avail = st.iso(t + timedelta(minutes=1) + SIP_DELAY) if (t and feed == "sip") else (
            st.iso(t + timedelta(minutes=1)) if t else None)
        self.store.db.execute(
            "INSERT INTO q_obs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (symbol, feed, t_iso, rev, session.date.isoformat(),
             *[(vals[k] if _num(vals[k]) else None) for k in ("o", "h", "l", "c", "v", "n", "vw")],
             json.dumps(bar, default=str), json.dumps(defects) if defects else None,
             st.iso(retrieved), avail, run_id))
        counts["new_obs"] += 1

    def _run(self, kind, session, start, end) -> int:
        cur = self.store.db.execute("INSERT INTO q_runs (kind, session_date, started_utc, window_start_utc, "
                                    "window_end_utc, status) VALUES (?,?,?,?,?, 'running')",
                                    (kind, session.date.isoformat(), st.iso(self.clock()), st.iso(start), st.iso(end)))
        self.store.db.commit()
        return cur.lastrowid

    def _finish(self, run_id, **fields) -> None:
        fields["finished_utc"] = st.iso(self.clock())
        sets = ", ".join(f"{k}=?" for k in fields)
        self.store.db.execute(f"UPDATE q_runs SET {sets} WHERE id=?", [*fields.values(), run_id])
        self.store.db.commit()

    # ---- one comparison window ----------------------------------------------------------
    def compare_window(self, client, session, start: datetime, end_exclusive: datetime, kind: str = "cycle") -> dict:
        """Fetch SIP and IEX for [start, end_exclusive), store observations, derive comparisons."""
        from trading.alpaca_client import AlpacaAccessError, MissingCredentials
        import requests
        run_id = self._run(kind, session, start, end_exclusive)
        counts = {"new_obs": 0, "duplicate_obs": 0, "corrections": 0, "defects": 0}
        got, n_requests = {}, 0
        try:
            for feed in ("sip", "iex"):
                resp = client.get_bars_multi(self.symbols, "1Min", st.iso(start),
                                             st.iso(end_exclusive - timedelta(seconds=1)), feed, "raw")
                n_requests += resp.get("pages", 1)
                got[feed] = (resp["bars"], self.clock())
        except (AlpacaAccessError, MissingCredentials, requests.RequestException, OSError) as exc:
            code = getattr(exc, "status_code", None)
            status = "access_failure" if code in (401, 403) or isinstance(exc, MissingCredentials) else "error"
            msg = f"{type(exc).__name__}: {exc}"
            self._finish(run_id, status=status, http_status=code, requests=n_requests, error=msg[:400])
            self.store.event("error", "quality-" + status, msg[:400], self.clock())
            return {"ok": False, "status": status, "http_status": code, "error": msg, "run_id": run_id}
        sizes = {}
        for feed, (bars, retrieved) in got.items():
            sizes[feed] = 0
            for sym in self.symbols:
                rows = bars.get(sym, [])
                sizes[feed] += len(rows)
                seen = {}
                for b in rows:
                    key = b.get("t")
                    extra = []
                    if key in seen and seen[key] != b:       # conflicting duplicates inside one response
                        extra.append("conflicting duplicate bars in one response")
                        self.store.event("error", "quality-defect", f"{feed} {sym} {key}: conflicting duplicate bars", self.clock())
                    seen[key] = b
                    if _ts_ok(b) and st.session_date_et(st.parse(b["t"])) <= st.RESERVED_END:
                        continue                              # reserved research period: never stored
                    self._observe(sym, feed, b, session, retrieved, run_id, counts, (start, end_exclusive), extra)
        compared = self._derive(session, start, end_exclusive, run_id)
        self._finish(run_id, status="ok", requests=n_requests, sip_bars=sizes["sip"], iex_bars=sizes["iex"],
                     compared=compared, **counts)
        return {"ok": True, "run_id": run_id, "compared": compared, **counts}

    def _derive(self, session, start, end_exclusive, run_id) -> int:
        now_iso, n = st.iso(self.clock()), 0
        t = start
        while t < end_exclusive:
            t_iso = st.iso(t)
            for sym in self.symbols:
                sip, iex = self._latest(sym, "sip", t_iso), self._latest(sym, "iex", t_iso)
                live = self.store.db.execute("SELECT o, h, l, c, v, received_utc FROM bars WHERE symbol=? AND "
                                             "feed='iex' AND t_utc=?", (sym, t_iso)).fetchone()
                cat, detail = classify(sip, iex)
                row = {"d": {}, "share": None}
                if sip and iex and cat != "structural_defect":
                    for f in ("o", "h", "l", "c"):
                        row["d"][f] = (iex[f] - sip[f], _bps(iex[f], sip[f]))
                    if sip["v"] and sip["v"] > 0:
                        row["share"] = iex["v"] / sip["v"]
                d = row["d"]
                live_d = (live["c"] - sip["c"], _bps(live["c"], sip["c"])) if (live and sip and _num(live["c"])
                                                                               and _num(sip["c"])) else (None, None)
                self.store.db.execute(
                    "INSERT OR IGNORE INTO q_compare (symbol, t_utc, session_date, sip_rev, iex_rev, category, detail, "
                    "sip_present, iex_present, live_iex_present, d_o_usd, d_h_usd, d_l_usd, d_c_usd, d_o_bps, d_h_bps, "
                    "d_l_bps, d_c_bps, iex_volume, sip_volume, iex_volume_share, sip_provider_available_utc, "
                    "sip_retrieved_utc, iex_retrieved_utc, live_iex_received_utc, compared_utc, run_id, live_o, live_h, "
                    "live_l, live_c, live_v, d_c_usd_live, d_c_bps_live) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (sym, t_iso, session.date.isoformat(), sip["revision"] if sip else 0, iex["revision"] if iex else 0,
                     cat, detail, int(bool(sip)), int(bool(iex)), int(bool(live)),
                     *(d.get(f, (None, None))[0] for f in ("o", "h", "l", "c")),
                     *(d.get(f, (None, None))[1] for f in ("o", "h", "l", "c")),
                     iex["v"] if iex else None, sip["v"] if sip else None, row["share"],
                     sip["provider_available_utc"] if sip else None, sip["retrieved_utc"] if sip else None,
                     iex["retrieved_utc"] if iex else None, live["received_utc"] if live else None, now_iso, run_id,
                     *((live[k] for k in ("o", "h", "l", "c", "v")) if live else (None,) * 5), *live_d))
                n += 1
            t += timedelta(minutes=1)
        self.store.db.commit()
        return n

    # ---- sessions: which ones are monitored, which remain unfinished --------------------------
    def mark_monitored(self, session, now: datetime) -> None:
        """Called by the worker while it live-polls an open session."""
        if session.date <= st.RESERVED_END:
            return
        self.store.db.execute(
            "INSERT INTO q_state (session_date, status, detail, first_monitored_utc, updated_utc) "
            "VALUES (?, 'in_progress', 'session open; monitored live', ?, ?) ON CONFLICT(session_date) DO NOTHING",
            (session.date.isoformat(), st.iso(now), st.iso(now)))
        self.store.db.commit()

    def _set_state(self, date_s: str, **fields) -> None:
        fields["updated_utc"] = st.iso(self.clock())
        sets = ", ".join(f"{k}=?" for k in fields)
        self.store.db.execute(f"UPDATE q_state SET {sets} WHERE session_date=?", [*fields.values(), date_s])
        self.store.db.commit()

    def _requests_last_hour(self, now: datetime) -> int:
        return self.store.db.execute("SELECT COALESCE(SUM(requests),0) FROM q_runs WHERE started_utc >= ?",
                                     (st.iso(now - timedelta(hours=1)),)).fetchone()[0]

    def _session(self, date_s: str):
        from datetime import date as _d
        found = st.sessions_between(_d.fromisoformat(date_s), _d.fromisoformat(date_s))
        return found[0] if found else None

    def _expire_old(self, now: datetime) -> None:
        """Unfinished sessions beyond the lookback are reported INCOMPLETE (never marked successful)."""
        recent = [s for s in st.sessions_between((now - timedelta(days=14)).date(), now.date()) if s.open_utc <= now]
        keep = {s.date.isoformat() for s in recent[-RECOVERY_LOOKBACK_SESSIONS:]}
        for row in self.store.db.execute("SELECT session_date FROM q_state WHERE status IN ('in_progress','provisional') "
                                         "OR status IS NULL").fetchall():
            if row[0] not in keep:
                self._set_state(row[0], status="incomplete",
                                detail=f"beyond the recovery lookback of {RECOVERY_LOOKBACK_SESSIONS} sessions; "
                                       "remaining minutes were not compared")
                self.finalize(row[0])
            else:                                            # keep every pending state accurate, not only the one worked on
                sess = self._session(row[0])
                if sess and now >= sess.close_utc:
                    self.store.db.execute("UPDATE q_state SET status='provisional', detail=?, updated_utc=? WHERE "
                                          "session_date=? AND status='in_progress'",
                                          ("session closed; comparison and post-close re-observation pending",
                                           st.iso(now), row[0]))
        self.store.db.commit()

    def pending_sessions(self) -> list:
        return [dict(r) for r in self.store.db.execute(
            "SELECT * FROM q_state WHERE status IN ('in_progress','provisional') OR status IS NULL ORDER BY session_date")]

    def _next_action(self, now: datetime):
        mk = st.market_state(now)
        current = (mk["session"] or mk["last_session"])
        rows = self.pending_sessions()
        rows.sort(key=lambda r: (0 if current and r["session_date"] == current.date.isoformat() else 1, r["session_date"]))
        for row in rows:
            session = self._session(row["session_date"])
            if session is None or session.date <= st.RESERVED_END:
                self._set_state(row["session_date"], status="incomplete", detail="not a comparable session")
                continue
            closed = now >= session.close_utc
            if row.get("status") != ("provisional" if closed else "in_progress"):
                self._set_state(row["session_date"], status="provisional" if closed else "in_progress",
                                detail="session closed; comparison and post-close re-observation pending" if closed
                                else "session open; monitored live")
            b = min(boundary(now), session.close_utc)
            through = st.parse(row["compared_through_utc"]) if row["compared_through_utc"] else session.open_utc
            if through < b:
                return session, "chunk", through, min(b, through + MAX_CHUNK)
            if through >= session.close_utc:
                if not row["eod_recheck_utc"]:
                    if now >= session.close_utc + SIP_DELAY + EOD_RECHECK_AFTER:
                        return session, "recheck", session.open_utc, session.close_utc
                    continue
                return session, "finalize", None, None
        return None

    # ---- scheduling (called from the worker loop) ----------------------------------------
    def step(self, client, now: datetime) -> dict | None:
        h = self.health()
        if h["backoff_until_utc"] and now < st.parse(h["backoff_until_utc"]):
            return None
        if self.next_cycle and now < self.next_cycle:
            return None
        self._expire_old(now)
        action = self._next_action(now)
        if action is None:
            self.next_cycle = now + CYCLE_EVERY
            self._health("ok" if h["last_success_utc"] else "idle",
                         "up to date: every monitored session is compared to the 20-minute boundary "
                         "or finalized")
            return None
        session, kind, start, end = action
        date_s = session.date.isoformat()
        if kind == "finalize":
            self.finalize(date_s)
            self.next_cycle = now
            return {"ok": True, "finalized": date_s}
        if self._requests_last_hour(now) + 2 > REQUEST_BUDGET_PER_HOUR:
            self.next_cycle = now + timedelta(minutes=1)
            self._health("throttled", f"hourly request budget ({REQUEST_BUDGET_PER_HOUR}) reached; backlog continues "
                                      "next minute")
            return None
        run_kind = "eod_recheck" if kind == "recheck" else (
            "recovery" if session.date != st.session_date_et(now) else "cycle")
        res = self.compare_window(client, session, start, end, kind=run_kind)
        if not res["ok"]:
            if res["status"] == "access_failure" and session.date != st.session_date_et(now):
                row = self.store.db.execute("SELECT access_failures FROM q_state WHERE session_date=?",
                                            (date_s,)).fetchone()
                n = (row[0] or 0) + 1
                self._set_state(date_s, access_failures=n)
                if n >= MAX_HISTORICAL_ACCESS_FAILURES:
                    self._set_state(date_s, status="incomplete",
                                    detail=f"historical access refused {n} times ({res['error'][:160]}); "
                                           "remaining minutes were not compared")
                    self.finalize(date_s)
            return self._fail(res, now)
        if kind == "recheck":
            self._set_state(date_s, eod_recheck_utc=st.iso(now))
            self.finalize(date_s)
            detail = f"{date_s}: post-close re-observation done ({res['corrections']} correction(s)); finalized"
        else:
            self._set_state(date_s, compared_through_utc=st.iso(end))
            detail = f"{date_s}: compared through {st.iso(end)}"
        more = self._next_action(now)
        self.next_cycle = now + BACKLOG_GAP if (more and more[1] != "finalize") else now + (
            timedelta(0) if more else CYCLE_EVERY)
        self._health("ok", detail + ("; more work queued" if more else ""), failures=0, backoff_until_utc=None,
                     last_success_utc=st.iso(now))
        return res

    # ---- idempotent daily finalization ---------------------------------------------------
    def finalize(self, date_s: str) -> dict:
        """Store the daily evidence report once. Re-running with unchanged evidence stores nothing;
        changed evidence after finalization becomes a new version that amends (never replaces) the old."""
        from trading.monitor import reliability
        rep_ = reliability.daily_report(self.store, date_s, self.clock())
        body = json.dumps(rep_["evidence"], sort_keys=True, default=str)
        sha = __import__("hashlib").sha256(body.encode()).hexdigest()
        last = self.store.db.execute("SELECT * FROM q_reports WHERE session_date=? ORDER BY version DESC LIMIT 1",
                                     (date_s,)).fetchone()
        status = rep_["status"]["state"]
        if status == "finalized":
            self._set_state(date_s, status="finalized", finalized_utc=st.iso(self.clock()),
                            detail="compared through the close; post-close re-observation done")
        if last and last["report_sha"] == sha and last["status"] == status:
            return {"stored": False, "version": last["version"]}
        version = (last["version"] + 1) if last else 1
        self.store.db.execute("INSERT INTO q_reports VALUES (?,?,?,?,?,?,?)",
                              (date_s, version, status, st.iso(self.clock()), sha,
                               json.dumps(rep_, default=str), last["version"] if last else None))
        self.store.event("info", "quality-report", f"{date_s}: report version {version} stored ({status})"
                         + (f"; amends version {last['version']}" if last else ""), self.clock())
        self.store.db.commit()
        return {"stored": True, "version": version}

    def _fail(self, res, now):
        failures = self.health()["failures"] + 1
        wait = ACCESS_REFUSED_WAIT if res["status"] == "access_failure" else BACKOFF[min(failures - 1, len(BACKOFF) - 1)]
        until = now + timedelta(seconds=wait)
        state = "access_failure" if res["status"] == "access_failure" else "error"
        self._health(state, f"{res['error'][:300]} (retry in {wait} s; the SIP feed is not replaced by another)",
                     failures=failures, backoff_until_utc=st.iso(until))
        return res


def _ts_ok(b) -> bool:
    try:
        st.parse(b["t"])
        return True
    except (TypeError, ValueError, KeyError):
        return False


# ---- the daily report (read by the dashboard; no network) -------------------------------

def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def report(store: st.MonitorStore, session_date: str | None = None, now: datetime | None = None) -> dict:
    ensure_schema(store)
    now = now or st.now_utc()
    if session_date is None:
        mk = st.market_state(now)
        cur = mk["session"] or mk["last_session"]
        session_date = cur.date.isoformat() if cur else None
    from datetime import date as _date
    sessions = st.sessions_between(_date.fromisoformat(session_date), _date.fromisoformat(session_date)) if session_date else []
    session = sessions[0] if sessions else None
    health = dict(store.db.execute("SELECT * FROM q_health WHERE id=1").fetchone())
    state = store.db.execute("SELECT * FROM q_state WHERE session_date=?", (session_date,)).fetchone()
    through = st.parse(state["compared_through_utc"]) if state and state["compared_through_utc"] else None
    out = {"label": "DATA QUALITY · delayed SIP vs IEX · read-only · not a trading signal or suitability certificate",
           "session_date": session_date, "now_utc": st.iso(now), "health": health,
           "delay_rule": "a minute is compared once its end is >= 20 min old (15 min SIP delay + 5 min safety margin)",
           "boundary_utc": st.iso(boundary(now)), "compared_through_utc": st.iso(through) if through else None,
           "eod_recheck_utc": state["eod_recheck_utc"] if state else None, "symbols": [], "runs": [], "flagged": []}
    if session is None:
        out["note"] = "no regular session on this date"
        return out
    out["session"] = {"open_utc": st.iso(session.open_utc), "close_utc": st.iso(session.close_utc),
                      "early_close": session.early_close, "minutes": session.regular_minutes}
    end_now = min(boundary(now), session.close_utc)
    out["pending"] = {"from_utc": st.iso(through or session.open_utc),
                      "to_utc": st.iso(min(now, session.close_utc)),
                      "comparable_now_until_utc": st.iso(end_now)}
    symbols = sorted({r[0] for r in store.db.execute("SELECT DISTINCT symbol FROM q_compare WHERE session_date=?",
                                                    (session_date,))}) or list(st.DEFAULT_SYMBOLS)
    for sym in symbols:
        rows = [dict(r) for r in store.db.execute(
            "SELECT * FROM q_compare c WHERE symbol=? AND session_date=? AND NOT EXISTS (SELECT 1 FROM q_compare d "
            "WHERE d.symbol=c.symbol AND d.t_utc=c.t_utc AND (d.sip_rev > c.sip_rev OR (d.sip_rev = c.sip_rev AND "
            "d.iex_rev > c.iex_rev)))", (sym, session_date))]
        cats = {k: sum(r["category"] == k for r in rows) for k in CATEGORIES}
        both = [r for r in rows if r["sip_present"] and r["iex_present"] and r["category"] != "structural_defect"]
        pos = [r for r in both if r["sip_volume"] and r["sip_volume"] > 0]
        corr = {f: store.db.execute("SELECT COUNT(*) FROM q_obs WHERE symbol=? AND feed=? AND session_date=? AND "
                                    "revision > 1", (sym, f, session_date)).fetchone()[0] for f in ("sip", "iex")}
        delays = [(st.parse(r["sip_retrieved_utc"]) - st.parse(r["t_utc"]) - timedelta(minutes=1)).total_seconds()
                  for r in rows if r["sip_retrieved_utc"]]
        live_missing_refetched = sum(1 for r in rows if r["iex_present"] and not r["live_iex_present"])
        out["symbols"].append({
            "symbol": sym, "minutes_compared": len(rows),
            "minutes_expected_so_far": int((end_now - session.open_utc).total_seconds() // 60) if end_now > session.open_utc else 0,
            "sip_present": sum(r["sip_present"] for r in rows), "iex_present": sum(r["iex_present"] for r in rows),
            "live_iex_present": sum(r["live_iex_present"] for r in rows), "both_present": len(both),
            "iex_missing": sum(1 for r in rows if r["sip_present"] and not r["iex_present"]),
            "sip_missing": sum(1 for r in rows if r["iex_present"] and not r["sip_present"]),
            "categories": cats, "corrections": corr, "live_iex_gaps_filled_later": live_missing_refetched,
            "iex_volume_share_total": (sum(r["iex_volume"] for r in pos) / sum(r["sip_volume"] for r in pos)) if pos else None,
            "iex_volume_share_median": _median([r["iex_volume_share"] for r in pos]),
            "zero_volume_sip_minutes": sum(1 for r in rows if r["sip_present"] and not r["sip_volume"]),
            "close_diff_bps_median_abs": _median([abs(r["d_c_bps"]) for r in both if r["d_c_bps"] is not None]),
            "close_diff_bps_max_abs": max((abs(r["d_c_bps"]) for r in both if r["d_c_bps"] is not None), default=None),
            "close_diff_usd_max_abs": max((abs(r["d_c_usd"]) for r in both if r["d_c_usd"] is not None), default=None),
            "high_diff_bps_median": _median([r["d_h_bps"] for r in both]),
            "low_diff_bps_median": _median([r["d_l_bps"] for r in both]),
            "sip_retrieval_delay_s_median": _median(delays), "sip_retrieval_delay_s_min": min(delays) if delays else None,
        })
        out["flagged"] += [{k: r[k] for k in ("symbol", "t_utc", "category", "detail", "sip_rev", "iex_rev",
                                               "sip_provider_available_utc", "sip_retrieved_utc")}
                           for r in rows if r["category"] in ("unresolved_anomaly", "structural_defect")][:50]
    out["runs"] = [dict(r) for r in store.db.execute(
        "SELECT * FROM q_runs WHERE session_date=? ORDER BY id DESC LIMIT 15", (session_date,))]
    out["corrections_recent"] = [dict(r) for r in store.db.execute(
        "SELECT symbol, feed, t_utc, revision, retrieved_utc FROM q_obs WHERE session_date=? AND revision > 1 "
        "ORDER BY retrieved_utc DESC LIMIT 20", (session_date,))]
    return out


def minute_record(store: st.MonitorStore, symbol: str, t_utc: str) -> dict:
    """Supporting records for one minute: every observation revision and every comparison."""
    ensure_schema(store)
    obs = [dict(r) for r in store.db.execute("SELECT * FROM q_obs WHERE symbol=? AND t_utc=? ORDER BY feed, revision",
                                             (symbol, t_utc))]
    cmp_ = [dict(r) for r in store.db.execute("SELECT * FROM q_compare WHERE symbol=? AND t_utc=? ORDER BY compared_utc",
                                              (symbol, t_utc))]
    live = store.db.execute("SELECT * FROM bars WHERE symbol=? AND feed='iex' AND t_utc=?", (symbol, t_utc)).fetchone()
    return {"symbol": symbol, "t_utc": t_utc, "observations": obs, "comparisons": cmp_,
            "live_iex_bar": dict(live) if live else None}
