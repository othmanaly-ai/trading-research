"""Multi-session recovery, idempotent finalization and the daily evidence report. ALL MARKET DATA IN
THIS FILE IS SYNTHETIC (labelled fixtures, invented prices); no network, no real records."""

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from trading.alpaca_client import AlpacaAccessError
from trading.monitor import quality as q
from trading.monitor import reliability
from trading.monitor import store as mst
from tests.test_quality import SYMS, Clock, FakeFeeds, bar, run_until_idle

UTC = timezone.utc


def session(day: str):
    from datetime import date
    return mst.sessions_between(date.fromisoformat(day), date.fromisoformat(day))[0]


@pytest.fixture
def env():
    store = mst.MonitorStore()
    yield store
    store.close()


def monitored_day(store, day, feeds, minutes=None, live=True, received_lag_s=30):
    """SYNTHETIC: a session the live worker monitored. Fills both feeds and (optionally) live IEX bars."""
    s = session(day)
    n = minutes if minutes is not None else s.regular_minutes
    feeds.fill("sip", s.open_utc, n)
    feeds.fill("iex", s.open_utc, n)
    if live:
        for m in range(n):
            t = s.open_utc + timedelta(minutes=m)
            for sym in SYMS:
                store.insert_bars(sym, "iex", [bar(t)], t + timedelta(minutes=1, seconds=received_lag_s))
    q.QualityChecker(store, SYMS).mark_monitored(s, s.open_utc)
    return s


def state(store, day):
    return dict(store.db.execute("SELECT * FROM q_state WHERE session_date=?", (day,)).fetchone())


# ---- recovery after being offline -------------------------------------------------------------

def test_shutdown_before_post_close_check_then_restart_next_trading_day(env):
    feeds = FakeFeeds()
    wed = monitored_day(env, "2026-11-04", feeds)
    clock = Clock(datetime(2026, 11, 4, 20, 20, tzinfo=UTC))             # 15:20 ET: then the worker stops
    qc = q.QualityChecker(env, SYMS, clock)
    run_until_idle(qc, feeds, clock)
    assert state(env, "2026-11-04")["compared_through_utc"] == "2026-11-04T20:00:00+00:00"
    # Next trading day, 10:00 ET: a new worker process starts.
    clock.t = datetime(2026, 11, 5, 15, 0, tzinfo=UTC)
    qc2 = q.QualityChecker(env, SYMS, clock)
    run_until_idle(qc2, feeds, clock)
    st_ = state(env, "2026-11-04")
    assert st_["status"] == "finalized" and st_["compared_through_utc"] == mst.iso(wed.close_utc)
    kinds = [r[0] for r in env.db.execute("SELECT kind FROM q_runs WHERE session_date='2026-11-04' ORDER BY id")]
    assert "recovery" in kinds and kinds[-1] == "eod_recheck"
    rep = reliability.stored_or_current(env, "2026-11-04", clock())
    assert rep["status"]["state"] == "finalized" and rep["stored_version"] == 1
    assert rep["evidence"]["sip_comparison"]["SPY"]["minutes_compared"] == 390


@pytest.mark.parametrize("restart", [
    datetime(2026, 11, 5, 4, 30, tzinfo=UTC),       # 23:30 ET same day (after midnight UTC)
    datetime(2026, 11, 5, 5, 30, tzinfo=UTC),       # 00:30 ET next day (after midnight ET)
])
def test_midnight_boundaries_do_not_abandon_the_session(env, restart):
    feeds = FakeFeeds()
    monitored_day(env, "2026-11-04", feeds)
    clock = Clock(datetime(2026, 11, 4, 21, 5, tzinfo=UTC))              # stopped soon after the close
    run_until_idle(q.QualityChecker(env, SYMS, clock), feeds, clock)
    assert state(env, "2026-11-04")["status"] == "provisional"
    clock.t = restart
    run_until_idle(q.QualityChecker(env, SYMS, clock), feeds, clock)
    assert state(env, "2026-11-04")["status"] == "finalized"


def test_weekend_gap_recovers_friday_on_monday(env):
    feeds = FakeFeeds()
    monitored_day(env, "2026-11-06", feeds)                               # Friday, worker stopped at 11:00 ET
    clock = Clock(datetime(2026, 11, 6, 16, 20, tzinfo=UTC))
    run_until_idle(q.QualityChecker(env, SYMS, clock), feeds, clock)
    clock.t = datetime(2026, 11, 9, 14, 0, tzinfo=UTC)                   # Monday before the open
    run_until_idle(q.QualityChecker(env, SYMS, clock), feeds, clock)
    assert state(env, "2026-11-06")["status"] == "finalized"


def test_early_close_session_recovered_and_finalized(env):
    feeds = FakeFeeds()
    monitored_day(env, "2026-11-27", feeds)
    clock = Clock(datetime(2026, 11, 30, 15, 0, tzinfo=UTC))             # next session (Monday)
    run_until_idle(q.QualityChecker(env, SYMS, clock), feeds, clock)
    st_ = state(env, "2026-11-27")
    assert st_["status"] == "finalized" and st_["compared_through_utc"] == "2026-11-27T18:00:00+00:00"
    rep = reliability.stored_or_current(env, "2026-11-27", clock())
    assert rep["evidence"]["schedule"]["early_close"] is True and rep["evidence"]["schedule"]["scheduled_minutes"] == 210
    assert rep["evidence"]["sip_comparison"]["IWM"]["minutes_compared"] == 210


def test_repeated_finalization_is_idempotent_and_amendments_keep_history(env):
    feeds = FakeFeeds()
    monitored_day(env, "2026-11-04", feeds)
    clock = Clock(datetime(2026, 11, 5, 15, 0, tzinfo=UTC))
    qc = q.QualityChecker(env, SYMS, clock)
    run_until_idle(qc, feeds, clock)
    for _ in range(3):
        assert qc.finalize("2026-11-04")["stored"] is False
    qc2 = q.QualityChecker(env, SYMS, clock)                              # restart
    run_until_idle(qc2, feeds, clock)
    assert env.db.execute("SELECT COUNT(*) FROM q_reports").fetchone()[0] == 1
    # New evidence after finalization (e.g. a late SIP revision found later) becomes version 2.
    t = mst.iso(session("2026-11-04").open_utc + timedelta(minutes=5))
    env.db.execute("INSERT INTO q_obs (symbol, feed, t_utc, revision, session_date, o, h, l, c, v, retrieved_utc) "
                   "VALUES ('SPY','sip',?,2,'2026-11-04',100,100.5,99.5,100.3,1000,?)", (t, mst.iso(clock())))
    env.db.commit()
    res = qc2.finalize("2026-11-04")
    assert res == {"stored": True, "version": 2}
    rows = env.db.execute("SELECT version, amends_version FROM q_reports ORDER BY version").fetchall()
    assert [tuple(r) for r in rows] == [(1, None), (2, 1)]                 # version 1 kept


def test_unavailable_historical_access_reports_incomplete_not_success(env):
    feeds = FakeFeeds()
    monitored_day(env, "2026-11-04", feeds)
    refused = AlpacaAccessError(403, "SYNTHETIC: historical access refused", "url")
    feeds.script = [refused] * 10
    clock = Clock(datetime(2026, 11, 5, 15, 0, tzinfo=UTC))
    qc = q.QualityChecker(env, SYMS, clock)
    for _ in range(q.MAX_HISTORICAL_ACCESS_FAILURES):
        qc.next_cycle = None
        assert qc.step(feeds, clock())["status"] == "access_failure"
        clock.t += timedelta(seconds=q.ACCESS_REFUSED_WAIT)
    st_ = state(env, "2026-11-04")
    assert st_["status"] == "incomplete" and "access refused 3 times" in st_["detail"]
    rep = reliability.stored_or_current(env, "2026-11-04", clock())
    assert rep["status"]["state"] == "incomplete" and rep["stored_version"] == 1
    assert any("not yet compared" in u["what"] for u in rep["evidence"]["unresolved"])
    assert rep["evidence"]["operations"]["access_refusals"] >= 3
    assert env.db.execute("SELECT COUNT(*) FROM q_compare").fetchone()[0] == 0


def test_bounded_backlog_lookback_and_request_budget(env, monkeypatch):
    feeds = FakeFeeds()
    days = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16", "2026-11-17"]
    for d in days:
        monitored_day(env, d, feeds, live=False)
    monkeypatch.setattr(q, "REQUEST_BUDGET_PER_HOUR", 12)
    # Saturday 21 Nov: the last 5 opened sessions are 16-20 Nov; only 16 and 17 were monitored.
    clock = Clock(datetime(2026, 11, 21, 14, 0, tzinfo=UTC))
    qc = q.QualityChecker(env, SYMS, clock)
    run_until_idle(qc, feeds, clock, limit=100)
    lookback = ["2026-11-16", "2026-11-17"]
    beyond = [d for d in days if d not in lookback]
    assert {d: state(env, d)["status"] for d in beyond} == {d: "incomplete" for d in beyond}
    assert "beyond the recovery lookback" in state(env, "2026-11-09")["detail"]
    assert all(r[0] == "incomplete" for r in env.db.execute(
        "SELECT status FROM q_reports WHERE session_date IN (%s)" % ",".join("?" * len(beyond)), beyond))
    hour = env.db.execute("SELECT COALESCE(SUM(requests),0) FROM q_runs WHERE started_utc >= ?",
                          (mst.iso(clock() - timedelta(hours=1)),)).fetchone()[0]
    assert hour <= 12 and qc.health()["state"] == "throttled"
    assert all(state(env, d)["status"] in ("provisional", "finalized") for d in lookback)   # no stale "in_progress"
    # Each later hour the budget allows more; the weekend keeps the lookback fixed. Nothing is requested twice.
    for _ in range(3):
        clock.t += timedelta(hours=1)
        run_until_idle(qc, feeds, clock, limit=100)
    assert {d: state(env, d)["status"] for d in lookback} == {d: "finalized" for d in lookback}
    assert env.db.execute("SELECT COUNT(*) FROM q_runs WHERE session_date IN (%s)" % ",".join("?" * len(beyond)),
                          beyond).fetchone()[0] == 0                         # no requests for expired sessions
    n = env.db.execute("SELECT COUNT(*), COUNT(DISTINCT symbol||t_utc||sip_rev||iex_rev) FROM q_compare").fetchone()
    assert n[0] == n[1]


def test_reserved_session_is_never_compared(env):
    env.db.execute("INSERT INTO q_state (session_date, status) VALUES ('2026-10-30', 'in_progress')") \
        if q.ensure_schema(env) is None else None
    env.db.commit()
    feeds = FakeFeeds()
    clock = Clock(datetime(2026, 11, 2, 14, 0, tzinfo=UTC))
    run_until_idle(q.QualityChecker(env, SYMS, clock), feeds, clock)
    assert feeds.calls == [] and state(env, "2026-10-30")["status"] == "incomplete"


# ---- the daily evidence report ---------------------------------------------------------------

def test_report_separates_live_capture_revisions_and_sip(env):
    feeds = FakeFeeds()
    s = session("2026-11-04")
    feeds.fill("sip", s.open_utc, 30)
    feeds.fill("iex", s.open_utc, 30)
    q.QualityChecker(env, SYMS).mark_monitored(s, s.open_utc)
    for m in range(30):
        t = s.open_utc + timedelta(minutes=m)
        if m == 7:
            continue                                                   # the live monitor never received 09:37
        lag = 30 if m < 20 else 900                                    # minutes 20+ arrived by catch-up
        c = 100.9 if m == 3 else 100.2                                 # live value later revised by IEX
        env.insert_bars("SPY", "iex", [bar(t, c=c, h=max(100.5, c))], t + timedelta(minutes=1, seconds=lag))
    clock = Clock(s.open_utc + timedelta(minutes=50))
    run_until_idle(q.QualityChecker(env, SYMS, clock), feeds, clock)
    ev = reliability.daily_report(env, "2026-11-04", clock())["evidence"]
    live = ev["live"]["SPY"]
    assert live["received_minutes"] == 29 and live["received_normal"] == 19 and live["received_by_catch_up"] == 10
    assert live["not_received_while_sip_had_a_bar"] >= 1
    rev = ev["iex_revisions"]["SPY"]
    assert rev["live_differs_from_refetch"] == 1 and rev["refetch_only_minutes"] == 1   # 09:33 revised, 09:37 missed
    assert rev["examples"][0]["live"]["c"] == 100.9 and rev["examples"][0]["refetch"]["c"] == 100.2
    sip = ev["sip_comparison"]["SPY"]
    assert sip["close_diff_vs_live_iex_bps"]["minutes"] == 29                 # live comparison kept separately
    assert sip["close_diff_vs_live_iex_bps"]["max_abs"] == pytest.approx((100.9 - 100.2) / 100.2 * 1e4)
    assert any("not identical" in k for k in sip["categories"])


def test_report_operations_downtime_restarts_and_failures(env):
    s = session("2026-11-04")
    q.QualityChecker(env, SYMS).mark_monitored(s, s.open_utc)
    r1 = env.start_run(101, "abc1234", {}, s.open_utc - timedelta(minutes=5))
    env.touch_run(r1, s.open_utc + timedelta(minutes=90))                    # killed: never stopped cleanly
    r2 = env.start_run(102, "abc1234", {}, s.open_utc + timedelta(minutes=120))
    env.end_run(r2, s.open_utc + timedelta(minutes=300), "stop requested")   # planned stop
    env.event("error", "disconnected", "connection failed: SYNTHETIC", s.open_utc + timedelta(minutes=60))
    env.event("error", "error", "access refused (HTTP 403) for feed iex: SYNTHETIC", s.open_utc + timedelta(minutes=61))
    ops = reliability.daily_report(env, "2026-11-04", s.close_utc + timedelta(hours=4))["evidence"]["operations"]
    kinds = [d["kind"].split(" ")[0] for d in ops["downtime_intervals"]]
    assert kinds == ["unplanned", "planned"]
    assert ops["unplanned_downtime_minutes"] == 29 and ops["restarts_during_session"] == 1
    assert ops["request_failures"] == 2 and ops["access_refusals"] == 1
    assert {r["code_version"] for r in ops["worker_runs"]} == {"abc1234"}


def test_worker_marks_sessions_it_monitors(env):
    from trading.monitor.worker import Worker
    from tests.test_monitor import FakeClient
    clock = Clock(datetime(2026, 11, 4, 15, 0, tzinfo=UTC))
    env.set_desired("running", "test")
    w = Worker(env, clock=clock, client_factory=lambda sleep: FakeClient(clock), pid=9, version="test")
    w.start()
    w.step()
    w.step()
    assert state(env, "2026-11-04")["status"] in ("in_progress",)
    assert env.db.execute("SELECT code_version FROM m_workers").fetchone()[0] == "test"
    w.shutdown("stop requested")
    assert env.db.execute("SELECT exit_reason FROM m_workers").fetchone()[0] == "stop requested"


def test_session_endpoints(env):
    from trading.dashboard import server
    feeds = FakeFeeds()
    monitored_day(env, "2026-11-04", feeds)
    clock = Clock(datetime(2026, 11, 5, 15, 0, tzinfo=UTC))
    run_until_idle(q.QualityChecker(env, SYMS, clock), feeds, clock)
    httpd, _c, stop = server.create_server(None, 0, speed=3600, run_jobs=False, supervise_monitor=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def get(path):
        try:
            with urllib.request.urlopen(base + path, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    try:
        code, body = get("/api/monitor/sessions")
        assert code == 200 and body["sessions"][0]["state"] == "finalized" and "computer" in body["operating_note"]
        code, rep = get("/api/monitor/report?date=2026-11-04")
        assert code == 200 and rep["stored_version"] == 1 and rep["status"]["state"] == "finalized"
        assert get("/api/monitor/report?date=../x")[0] == 400
    finally:
        stop.set()
        httpd.shutdown()
        httpd.server_close()



def test_interval_without_run_records_is_unrecorded_not_downtime(env):
    s = session("2026-11-04")
    q.QualityChecker(env, SYMS).mark_monitored(s, s.open_utc)
    # SYNTHETIC: live bars received at 10:00 ET, but run recording only starts at 11:00 ET.
    env.insert_bars("SPY", "iex", [bar(s.open_utc)], s.open_utc + timedelta(minutes=30))
    rid = env.start_run(5, "v", {}, s.open_utc + timedelta(minutes=90))
    env.touch_run(rid, s.open_utc + timedelta(minutes=120))               # still alive at report time
    ops = reliability.daily_report(env, "2026-11-04", s.open_utc + timedelta(minutes=120))["evidence"]["operations"]
    assert ops["downtime_minutes"] == 0 and ops["unrecorded_minutes"] == 90
    assert ops["unrecorded_intervals"][0]["kind"].startswith("unrecorded")
