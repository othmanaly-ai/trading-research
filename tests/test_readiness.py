"""SYNTHETIC fixtures in isolated temporary databases: market readiness checks, incidents and
server start-up detection. Nothing here touches the real monitor or its database, and none of these
values are operational evidence."""

import json
import sqlite3
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from trading.monitor import readiness as rd
from trading.monitor import store as st

SAT = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)            # Saturday: market closed
OPEN = datetime(2026, 11, 13, 16, 0, tzinfo=timezone.utc)           # Friday 11:00 ET: market open
CFG = {"symbols": ["SPY"], "feed": "iex", "poll_seconds": 60, "code_version": "abc1234"}


@pytest.fixture(autouse=True)
def _isolated_runner(tmp_path, monkeypatch):
    """Every test: the dry-run runner check sees an isolated runtime folder and no real processes."""
    monkeypatch.setenv("TRADING_OPS_DIR", str(tmp_path / "ops_SYNTHETIC"))
    monkeypatch.setattr(rd, "runner_processes", lambda: [])


@pytest.fixture
def store(tmp_path):
    s = st.MonitorStore(tmp_path / "monitor_SYNTHETIC.sqlite")
    yield s
    s.close()


def healthy(s, now, pid=4242):
    s.set_desired("running", "test", now)
    s.update_worker(pid=pid, state="market_closed", detail="SYNTHETIC", heartbeat_utc=st.iso(now - timedelta(seconds=3)),
                    last_success_utc=st.iso(now - timedelta(hours=20)), consecutive_failures=0,
                    config_json=json.dumps(CFG))


def ev(s, now, procs=lambda: [[4242]], head=lambda: "abc1234", cross=lambda: {"ts_utc": "2026-11-13T12:00:00+00:00",
                                                                               "ok": True, "detail": {}}, **kw):
    return {c["id"]: c for c in rd.evaluate(s, now, procs=procs, head=head, cross_check=cross,
                                             server_info={"pid": 1, "started_utc": "x", "code_version": "abc1234"}, **kw)}


def test_missing_evidence_is_unknown_never_pass(store):
    c = ev(store, SAT, procs=lambda: None, head=lambda: None, cross=lambda: None)
    for k in ("worker_count", "heartbeat", "latest_data", "failures", "unfinished_sessions", "code_version"):
        assert c[k]["status"] == rd.UNKNOWN, (k, c[k])
    assert c["server"]["status"] == rd.PASS and c["database"]["status"] == rd.PASS
    snap = rd.snapshot(store, SAT, procs=lambda: None, head=lambda: None, cross_check=lambda: None, server_info={})
    assert snap["overall"] != rd.PASS and snap["counts"]["UNKNOWN"] >= 6
    assert all(x["checked_utc"] == st.iso(SAT) and x["recorded"] for x in snap["checks"])


def test_closed_market_is_expected_and_healthy_state_passes(store):
    healthy(store, SAT)
    store.insert_bars("SPY", "iex", [{"t": "2026-11-13T20:59:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}],
                      datetime(2026, 11, 13, 21, 0, tzinfo=timezone.utc))
    c = ev(store, SAT)
    assert c["desired_vs_actual"]["status"] == rd.PASS and c["latest_data"]["status"] == rd.PASS
    assert "market closed (expected)" in c["latest_data"]["summary"]
    assert c["calendar"]["status"] == rd.PASS and "next open Mon 2026-11-16 09:30" in c["calendar"]["summary"]
    assert c["worker_count"]["status"] == rd.PASS and c["code_version"]["status"] == rd.PASS


def test_early_close_and_calendar_cross_check_states(store):
    healthy(store, SAT)
    after_early = datetime(2026, 11, 27, 18, 30, tzinfo=timezone.utc)             # 13:30 ET, early close 13:00
    c = ev(store, after_early)
    assert c["calendar"]["detail"]["reason"] == "after the close (early close)"
    assert ev(store, SAT, cross=lambda: None)["calendar"]["status"] == rd.WARNING
    assert ev(store, SAT, cross=lambda: {"ts_utc": "2026-11-13T12:00:00+00:00", "ok": False, "detail": {}})["calendar"]["status"] == rd.FAIL
    old = {"ts_utc": "2026-10-01T12:00:00+00:00", "ok": True, "detail": {}}
    assert ev(store, SAT, cross=lambda: old)["calendar"]["status"] == rd.WARNING


def test_stale_heartbeat_opens_one_deduplicated_incident_then_recovers(store):
    healthy(store, SAT)
    store.update_worker(heartbeat_utc=st.iso(SAT - timedelta(minutes=5)), state="running")
    c = ev(store, SAT)
    assert c["heartbeat"]["status"] == rd.FAIL
    rd.record(store, list(c.values()), SAT, alive_fn=lambda pid: True)               # process exists: frozen
    rd.record(store, list(ev(store, SAT + timedelta(minutes=1)).values()), SAT + timedelta(minutes=1), alive_fn=lambda pid: True)
    inc = rd.incidents(store)
    assert len(inc) == 1 and inc[0]["kind"] == "heartbeat_stale" and inc[0]["observations"] == 2 and inc[0]["state"] == "open"
    assert "Stop, then Start" in inc[0]["recovery"]
    assert "acknowledged" in rd.acknowledge(store, inc[0]["id"], "test", SAT)
    assert rd.incidents(store)[0]["state"] == "acknowledged"                       # seen, not resolved
    later = SAT + timedelta(minutes=3)
    store.update_worker(heartbeat_utc=st.iso(later), state="market_closed")
    rd.record(store, list(ev(store, later).values()), later, alive_fn=lambda pid: True)
    inc = rd.incidents(store)[0]
    assert inc["state"] == "resolved" and inc["resolution"].endswith("service recovered")
    assert "nothing changed" in rd.acknowledge(store, inc["id"], "test", later)
    assert any("service recovered" in e["message"] for e in store.events(10))


def test_worker_gone_without_stop_is_unexpected_stop(store):
    healthy(store, SAT)
    store.update_worker(heartbeat_utc=st.iso(SAT - timedelta(minutes=2)), state="running")
    c = ev(store, SAT, procs=lambda: [])
    assert c["worker_count"]["status"] == rd.FAIL and "desired state is running" in c["worker_count"]["summary"]
    rd.record(store, list(c.values()), SAT, alive_fn=lambda pid: False)
    assert [i["kind"] for i in rd.incidents(store)] == ["worker_stopped_unexpectedly"]


def test_duplicate_workers_fail_but_venv_launcher_child_is_one_worker(store):
    healthy(store, SAT, pid=11576)
    assert rd.group_worker_trees([(5368, 25800), (11576, 5368)]) == [[5368, 11576]]
    assert rd.group_worker_trees([(1, 9), (2, 9)]) == [[1], [2]]
    assert ev(store, SAT, procs=lambda: [[5368, 11576]])["worker_count"]["status"] == rd.PASS
    dup = ev(store, SAT, procs=lambda: [[5368, 11576], [7000, 7001]])["worker_count"]
    assert dup["status"] == rd.FAIL and "2 separate worker processes" in dup["summary"]


def test_provider_refusal_then_recovery(store):
    healthy(store, SAT)
    store.update_worker(state="error", detail="access refused (HTTP 403) for feed iex: SYNTHETIC", consecutive_failures=1,
                        backoff_until_utc=st.iso(SAT + timedelta(minutes=10)))
    c = ev(store, SAT)
    assert c["failures"]["status"] == rd.FAIL
    rd.record(store, list(c.values()), SAT, alive_fn=lambda pid: True)
    assert rd.incidents(store)[0]["kind"] == "access_refused"
    assert "never paste them in chat" in rd.incidents(store)[0]["recovery"]
    t2 = SAT + timedelta(minutes=11)
    healthy(store, t2)
    rd.record(store, list(ev(store, t2).values()), t2, alive_fn=lambda pid: True)
    assert rd.incidents(store)[0]["state"] == "resolved"


class BrokenDB:
    def execute(self, *a, **k):
        raise sqlite3.OperationalError("disk I/O error (SYNTHETIC)")

    def executescript(self, *a, **k):
        raise sqlite3.OperationalError("disk I/O error (SYNTHETIC)")

    def commit(self):
        raise sqlite3.OperationalError("disk I/O error (SYNTHETIC)")


def test_database_failure_is_fail_and_recorded_after_recovery(store):
    healthy(store, SAT)
    real = store.db
    store.db = BrokenDB()
    c = ev(store, SAT)
    assert c["database"]["status"] == rd.FAIL and c["heartbeat"]["status"] == rd.UNKNOWN
    rd.record(store, list(c.values()), SAT, alive_fn=lambda pid: True)
    assert rd._pending_incidents and rd._pending_incidents[0]["kind"] == "storage_failure"
    store.db = real
    t2 = SAT + timedelta(minutes=1)
    healthy(store, t2)
    rd.record(store, list(ev(store, t2).values()), t2, alive_fn=lambda pid: True)
    inc = rd.incidents(store)
    assert [i["kind"] for i in inc] == ["storage_failure"] and inc[0]["opened_utc"] == st.iso(SAT)
    assert inc[0]["state"] == "resolved" and not rd._pending_incidents


def test_restart_with_unfinished_session_is_pending_and_does_not_qualify(store):
    from trading.monitor import quality as q
    healthy(store, SAT)
    q.ensure_schema(store)
    store.db.execute("INSERT INTO q_state (session_date, compared_through_utc) VALUES ('2026-11-13', '2026-11-13T19:00:00+00:00')")
    store.db.commit()
    c = ev(store, SAT)
    assert c["unfinished_sessions"]["status"] == rd.WARNING and "2026-11-13" in c["unfinished_sessions"]["summary"]
    rel = rd.reliability_summary(store, SAT)
    row = [r for r in rel["sessions"] if r["session_date"] == "2026-11-13"][0]
    assert row["state"] == "provisional" and not row["qualifies"] and rel["current_consecutive"] == 0
    assert "No capture-quality threshold" in rel["gap"]


def test_unmonitored_scheduled_session_breaks_the_streak(store):
    from trading.monitor import quality as q
    q.ensure_schema(store)
    for d in ("2026-11-10", "2026-11-12"):
        store.db.execute("INSERT INTO q_state (session_date, compared_through_utc, eod_recheck_utc) VALUES (?, ?, ?)",
                         (d, f"{d}T21:00:00+00:00", f"{d}T22:00:00+00:00"))
    store.db.commit()
    rel = rd.reliability_summary(store, SAT)
    states = {r["session_date"]: (r["state"], r["qualifies"]) for r in rel["sessions"]}
    assert states["2026-11-11"] == ("not_monitored", False) and states["2026-11-13"] == ("not_monitored", False)
    assert rel["best_consecutive"] == 1 and rel["current_consecutive"] == 0


# ---------------------------------------------------------------- start-up detection and the API

def _serve(handler):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def test_existing_server_detection():
    from trading.dashboard import server as srv

    class Ours(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"mode": "DEMO_REPLAY", "banner": "SYNTHETIC"}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    class Other(Ours):
        def do_GET(self):
            self.send_response(404)
            self.end_headers()

    a, b = _serve(Ours), _serve(Other)
    try:
        assert srv.existing_server(a.server_address[1]) == {"mode": "DEMO_REPLAY", "banner": "SYNTHETIC"}
        assert srv.existing_server(b.server_address[1]) == {"unrecognised": True}
        assert srv.main(["--port", str(a.server_address[1])]) == 0           # does not start a second server
        assert srv.main(["--port", str(b.server_address[1])]) == 2
    finally:
        a.shutdown()
        b.shutdown()
    free = ThreadingHTTPServer(("127.0.0.1", 0), Ours)
    port = free.server_address[1]
    free.server_close()
    assert srv.existing_server(port, timeout=0.5) is None


def test_api_panel_and_records_agree(tmp_path, monkeypatch):
    from trading.dashboard import server as srv
    monkeypatch.setattr(st, "DB_PATH", tmp_path / "monitor_SYNTHETIC.sqlite")
    monkeypatch.setattr(rd, "worker_processes", lambda: [[4242]])
    monkeypatch.setattr(rd, "operations_cross_check", lambda: None)
    httpd, ctrl, stop = srv.create_server(None, 0, supervise_monitor=False, run_jobs=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        port = httpd.server_address[1]
        data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/monitor/readiness", timeout=30).read())
        s = st.MonitorStore()
        stored = {r["check_id"]: dict(r) for r in s.db.execute("SELECT * FROM readiness")}
        s.close()
        assert {c["id"]: c["status"] for c in data["checks"]} == {k: v["status"] for k, v in stored.items()}
        assert data["checks"][0]["id"] == "server" and data["checks"][0]["status"] == rd.PASS
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/monitor/incidents/ack", data=b'{"id": 999}', method="POST",
                                     headers={"Content-Type": "application/json", "X-Dashboard-Control": "1",
                                              "Origin": f"http://127.0.0.1:{port}"})
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=10)
        assert e.value.code in (403, 404)
    finally:
        stop.set()
        httpd.shutdown()
        httpd.server_close()


# ---------------------------------------------------------------- regression: unavailable counts (2026-11-09)

def test_agg_keeps_unknown_unknown():
    assert rd._agg(max, [1, 5]) == 5 and rd._agg(min, [3, 2]) == 2
    assert rd._agg(max, [1, None]) is None and rd._agg(min, []) is None and rd._agg(sum, [None]) is None


def test_in_progress_session_with_unavailable_counts_is_unknown_not_zero(store):
    """SYNTHETIC in-progress session built from records: the evidence report leaves 'missing' unavailable
    while the session is open. Before the fix, max() over None raised TypeError and dropped the request."""
    from trading.monitor import quality as q
    healthy(store, OPEN)
    store.update_worker(state="running")
    q.ensure_schema(store)
    store.db.execute("INSERT INTO q_state (session_date, compared_through_utc, first_monitored_utc) VALUES "
                     "('2026-11-13', '2026-11-13T15:30:00+00:00', '2026-11-13T14:30:00+00:00')")
    store.db.commit()
    store.insert_bars("SPY", "iex", [{"t": f"2026-11-13T15:{m:02d}:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}
                                      for m in range(50, 58)], OPEN)
    rel = rd.reliability_summary(store, OPEN)
    row = [r for r in rel["sessions"] if r["session_date"] == "2026-11-13"][0]
    assert row["state"] == "in_progress" and row["qualifies"] is False
    assert row["live_missing_max"] is None                     # unavailable stays unknown, never 0
    json.dumps(rd.snapshot(store, OPEN, procs=lambda: [[4242]], head=lambda: "abc1234", cross_check=lambda: None,
                           server_info={}, alive_fn=lambda pid: True))      # valid JSON, no exception


def test_all_unavailable_per_symbol_counts_become_unknown(store, monkeypatch):
    """SYNTHETIC overview row where on_time, late_catch_up and missing are all unavailable."""
    from trading.monitor import quality as q
    from trading.monitor import reliability as rl
    q.ensure_schema(store)
    row = {"session_date": "2026-11-13", "state": "in_progress", "detail": None, "scheduled_minutes": None,
           "early_close": False, "live_by_symbol": {"SPY": {"on_time": None, "late_catch_up": None, "missing": None},
                                                    "QQQ": {"on_time": 4, "late_catch_up": None, "missing": None}},
           "compared_min": None, "downtime_minutes": None, "unplanned_downtime_minutes": None, "request_failures": None,
           "access_refusals": None, "report_versions": 0}
    monkeypatch.setattr(rl, "sessions_overview", lambda s, now, limit=60: [row])
    monkeypatch.setattr(rl, "stored_or_current", lambda s, d, now: {"evidence": {}})
    out = [r for r in rd.reliability_summary(store, OPEN)["sessions"] if r["session_date"] == "2026-11-13"][0]
    for k in ("live_on_time_min", "live_late_recovery_min", "live_missing_max", "comparisons_outstanding_min",
              "anomalies", "revisions", "scheduled_minutes", "unplanned_downtime_minutes"):
        assert out[k] is None, k


def test_readiness_endpoint_answers_json_on_internal_error(tmp_path, monkeypatch):
    """SYNTHETIC: an evaluation bug must yield an honest JSON UNKNOWN (HTTP 500), not a dropped connection."""
    from trading.dashboard import server as srv
    monkeypatch.setattr(st, "DB_PATH", tmp_path / "monitor_SYNTHETIC.sqlite")
    monkeypatch.setattr(srv, "monitor_readiness", lambda: (_ for _ in ()).throw(TypeError("SYNTHETIC bug")))
    httpd, ctrl, stop = srv.create_server(None, 0, supervise_monitor=False, run_jobs=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_address[1]}/api/monitor/readiness", timeout=30)
        body = json.loads(e.value.read())
        assert e.value.code == 500 and body["overall"] == "UNKNOWN" and "SYNTHETIC bug" in body["error"]
    finally:
        stop.set()
        httpd.shutdown()
        httpd.server_close()
