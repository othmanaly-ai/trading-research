"""SYNTHETIC fixtures in isolated temporary folders and databases (2026-11-09 fixes). Nothing here
touches the real monitor, the real operations records or real processes; none of it is evidence."""

import json
import threading
from datetime import date, datetime, timedelta, timezone

import pytest

from trading.monitor import readiness as rd
from trading.monitor import reliability as rl
from trading.monitor import store as st

D = "2026-11-13"                                                   # Friday, regular session
OPEN = datetime(2026, 11, 13, 14, 30, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    s = st.MonitorStore(tmp_path / "monitor_SYNTHETIC.sqlite")
    yield s
    s.close()


# ---------------------------------------------------------------- 1. request failures from explicit outcomes

def test_incident_events_are_not_request_failures(store):
    from trading.monitor import quality as q
    q.ensure_schema(store)
    t = lambda m: st.iso(OPEN + timedelta(minutes=m))
    store.event("error", "disconnected", "connection failed: SYNTHETIC", OPEN + timedelta(minutes=10))     # live poll failure
    store.event("error", "error", "access refused (HTTP 403) SYNTHETIC", OPEN + timedelta(minutes=20))   # live refusal
    store.event("error", "incident", "incident opened: worker_stopped_unexpectedly: SYNTHETIC", OPEN + timedelta(minutes=30))
    store.event("error", "supervisor", "TypeError: SYNTHETIC", OPEN + timedelta(minutes=31))
    store.event("info", "state", "running: poll ok SYNTHETIC", OPEN + timedelta(minutes=32))             # success
    store.db.execute("INSERT INTO q_runs (kind, session_date, started_utc, status, error, requests) VALUES "
                     "('cycle', ?, ?, 'ok', NULL, 2), ('cycle', ?, ?, 'error', 'HTTP 500 SYNTHETIC', 1)", (D, t(40), D, t(50)))
    store.db.commit()
    ops = rl.daily_report(store, D, AFTER)["evidence"]["operations"]
    assert ops["request_failures"] == 3                         # 2 live poll failures + 1 failed comparison run
    assert ops["access_refusals"] == 1
    assert {e["kind"] for e in ops["failure_events"]} == {"disconnected", "error", "comparison-error"}
    assert ops["other_errors"] == 2 and ops["other_error_kinds"] == {"incident": 1, "supervisor": 1}


# ---------------------------------------------------------------- 2. finalized wording

def test_finalized_state_never_carries_pending_wording(store):
    from trading.monitor import quality as q
    q.ensure_schema(store)
    store.db.execute("INSERT INTO q_state (session_date, compared_through_utc, eod_recheck_utc, status, detail) VALUES "
                     "(?, '2026-11-13T21:00:00+00:00', '2026-11-13T22:00:00+00:00', 'provisional', "
                     "'session closed; comparison and post-close re-observation pending')", (D,))
    store.db.commit()
    s = rl.daily_report(store, D, AFTER)["status"]
    assert s["state"] == "finalized" and s["detail"] == rl.FINALIZED_DETAIL


def _stored(store, version, detail, request_failures, events):
    rep = {"session_date": D, "status": {"state": "finalized", "detail": detail},
           "evidence": {"operations": {"request_failures": request_failures, "failure_events": events}}}
    store.db.execute("INSERT INTO q_reports (session_date, version, status, created_utc, report_sha, report_json, "
                     "amends_version) VALUES (?,?,?,?,?,?,?)", (D, version, "finalized", st.iso(AFTER), "sha", json.dumps(rep),
                                                                  None if version == 1 else version - 1))
    store.db.commit()


def test_correction_is_a_new_version_with_reason_and_keeps_the_original(store):
    from trading.monitor import quality as q
    q.ensure_schema(store)
    events = [{"ts_utc": "x", "kind": "incident", "message": "incident opened: SYNTHETIC"},
              {"ts_utc": "y", "kind": "disconnected", "message": "connection failed: SYNTHETIC"}]
    _stored(store, 1, "session closed; comparison and post-close re-observation pending", 2, events)
    original = store.db.execute("SELECT report_json FROM q_reports WHERE session_date=? AND version=1", (D,)).fetchone()[0]
    preview = rl.correct_stored_report(store, D, "SYNTHETIC reason", AFTER, apply=False)
    assert not preview["stored"] and {c["field"] for c in preview["changes"]} == {"status.detail",
                                                                                "evidence.operations.request_failures"}
    assert store.db.execute("SELECT COUNT(*) FROM q_reports WHERE session_date=?", (D,)).fetchone()[0] == 1
    res = rl.correct_stored_report(store, D, "SYNTHETIC reason", AFTER, apply=True)
    assert res["stored"] and res["version"] == 2
    v1 = store.db.execute("SELECT report_json FROM q_reports WHERE session_date=? AND version=1", (D,)).fetchone()[0]
    assert v1 == original                                                       # original kept byte-for-byte
    v2 = json.loads(store.db.execute("SELECT report_json FROM q_reports WHERE session_date=? AND version=2", (D,)).fetchone()[0])
    assert v2["status"]["detail"] == rl.FINALIZED_DETAIL
    assert v2["evidence"]["operations"]["request_failures"] == 1
    assert v2["evidence"]["operations"]["failure_events_reclassified_as_other"][0]["kind"] == "incident"
    assert v2["correction"]["from_version"] == 1 and v2["correction"]["reason"] == "SYNTHETIC reason"
    reason = store.db.execute("SELECT reason, from_version FROM q_report_corrections WHERE session_date=?", (D,)).fetchone()
    assert tuple(reason) == ("SYNTHETIC reason", 1)
    assert rl.correct_stored_report(store, D, "again", AFTER, apply=True)["changes"] == []   # idempotent


def test_truncated_event_list_makes_the_corrected_count_unknown(store):
    from trading.monitor import quality as q
    q.ensure_schema(store)
    _stored(store, 1, rl.FINALIZED_DETAIL, 40, [{"ts_utc": "x", "kind": "incident", "message": "SYNTHETIC"}] * 30)
    ch = rl.plan_correction(json.loads(store.db.execute("SELECT report_json FROM q_reports").fetchone()[0]))
    assert ch == [{"field": "evidence.operations.request_failures", "old": 40, "new": None,
                   "why": "stored event list truncated; true count unknown"}]


# ---------------------------------------------------------------- 3. stalled or missing runner is visible

MON = date(2026, 11, 16)


def _plan(d=MON):
    from trading.operations import schedule
    return schedule.plan_for(d)


def _at(hhmm, d=MON):
    from trading.operations import schedule
    return datetime.fromisoformat(f"{d}T{hhmm}").replace(tzinfo=schedule.ET).astimezone(timezone.utc)


def _files(tmp_path, status=None, startup=None):
    from trading.operations import progress
    d = tmp_path / "ops"
    d.mkdir(exist_ok=True)
    if status:
        (d / progress.STATUS_NAME).write_text(json.dumps(status))
    if startup:
        (d / progress.STARTUP_NAME).write_text(json.dumps(startup))
    return d


def test_runner_check_states(tmp_path):
    rc = lambda now, procs, folder: rd.runner_check(now, procs=procs, runtime_dir=folder)
    empty = _files(tmp_path)
    assert rc(_at("08:00"), lambda: [], empty)["status"] == rd.WARNING                       # before pre-open
    assert rc(_at("10:00"), lambda: [], empty)["status"] == rd.FAIL                          # session, none running
    assert rc(_at("10:00", date(2026, 11, 14)), lambda: [], empty)["status"] == rd.PASS      # Saturday: not required
    now = _at("10:00")
    fresh = _files(tmp_path, status={"pid": 22352, "stage": "running", "phase": "DECISION_WINDOW", "run_id": "r1",
                                     "session_date": str(MON), "ts_utc": (now - timedelta(seconds=10)).isoformat()})
    _record(fresh, "r1", now - timedelta(seconds=10))
    assert rc(now, lambda: [[21432, 22352]], fresh)["status"] == rd.PASS
    assert rc(now, lambda: [[1], [2]], fresh)["status"] == rd.FAIL                          # two runners


def _record(folder, run_id, heartbeat, decisions=3):
    """SYNTHETIC dry-run records in a temporary folder."""
    from trading.operations.store import OpsStore
    st = OpsStore(folder / "operations.sqlite")
    st.db.execute("INSERT INTO runs (run_id, kind, session_date, started_utc, heartbeat_utc) VALUES (?,?,?,?,?)",
                  (run_id, "session", str(MON), heartbeat.isoformat(), heartbeat.isoformat()))
    for i in range(decisions):
        st.db.execute("INSERT INTO decisions (session_date, minute_utc, run_id) VALUES (?,?,?)",
                      (str(MON), (heartbeat - timedelta(minutes=i)).isoformat(), run_id))
    st.db.commit()
    st.close()


def test_alive_runner_without_recorded_progress_is_never_healthy(tmp_path):
    """Regression (2026-11-10): a fresh status file and a live process passed while the records the city reads had no
    run at all. Liveness is not progress: the run must be in the records with a current heartbeat."""
    now = _at("12:00")
    status = {"pid": 9496, "stage": "running", "phase": "DECISION_WINDOW", "run_id": "today", "session_date": str(MON),
              "decisions_this_run": 150, "ts_utc": (now - timedelta(seconds=5)).isoformat()}
    procs = lambda: [[25080, 9496]]
    no_db = _files(tmp_path, status=status)                                       # no records file at all
    c = rd.runner_check(now, procs=procs, runtime_dir=no_db)
    assert c["status"] == rd.FAIL and "NO RECORDED PROGRESS" in c["summary"]
    other = tmp_path / "other"
    other.mkdir()
    folder = _files(other, status=status)
    _record(folder, "yesterday", now - timedelta(days=2))                        # records exist, but not this run
    c = rd.runner_check(now, procs=procs, runtime_dir=folder)
    assert c["status"] == rd.FAIL and "not in the records" in c["summary"]
    third = tmp_path / "third"
    third.mkdir()
    folder = _files(third, status=status)
    _record(folder, "today", now - timedelta(hours=3))                           # run recorded once, then nothing
    c = rd.runner_check(now, procs=procs, runtime_dir=folder)
    assert c["status"] == rd.FAIL and "stored heartbeat" in c["summary"]
    # and it stays FAIL however long the status file keeps refreshing
    for minutes in (1, 30, 200):                                               # 12:01 to 15:20 ET
        later = now + timedelta(minutes=minutes)
        status["ts_utc"] = (later - timedelta(seconds=5)).isoformat()
        _files(third, status=status)
        assert rd.runner_check(later, procs=procs, runtime_dir=folder)["status"] == rd.FAIL


def test_app_private_copy_of_the_records_is_detected(tmp_path, monkeypatch):
    """Regression (2026-11-10): inside a packaged Windows app the records path resolves to the app's private copy.
    Simulated here with a hard link: the 'real' path and the private copy are the same file."""
    import os
    from trading.operations import paths
    local = tmp_path / "Local"
    copy_dir = local / "Packages" / "SomeApp_abc" / "LocalCache" / "Local" / "TradingProject" / "operations"
    copy_dir.mkdir(parents=True)
    (copy_dir / "operations.sqlite").write_bytes(b"stale copy")
    real_dir = local / "TradingProject" / "operations"
    real_dir.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("TRADING_OPS_DIR", raising=False)
    os.link(copy_dir / "operations.sqlite", real_dir / "operations.sqlite")      # this process "sees" the copy
    assert paths.view_redirected(real_dir / "operations.sqlite") == copy_dir / "operations.sqlite"
    assert "app-private copy" in paths.virtualization_problem(real_dir)
    from trading.operations import __main__ as cli
    assert cli.main(["status"]) == 3                                             # every command refuses
    assert cli.main(["kill-switch", "on", "--reason", "x"]) == 3
    assert not (copy_dir / "KILL_SWITCH.json").exists() and not (real_dir / "KILL_SWITCH.json").exists()
    from trading.operations import snapshot
    snap = snapshot.collect()
    assert snap["available"] is False and snap["records_visible"] is False
    (real_dir / "operations.sqlite").unlink()
    (real_dir / "operations.sqlite").write_bytes(b"real file")                   # outside the app: separate file
    assert paths.view_redirected(real_dir / "operations.sqlite") is None
    assert paths.virtualization_problem(real_dir) is None


def test_runner_alive_but_silent_is_stalled_with_its_last_step(tmp_path):
    now = _at("10:00")
    folder = _files(tmp_path, startup={"pid": 22352, "stage": "starting", "step": "1/4 loading code (pandas, exchange calendar)",
                                       "ts_utc": (now - timedelta(minutes=47)).isoformat()})
    c = rd.runner_check(now, procs=lambda: [[21432, 22352]], runtime_dir=folder)
    assert c["status"] == rd.FAIL and "STALLED" in c["summary"] and "1/4 loading code" in c["summary"]
    starting = _files(tmp_path, startup={"pid": 22352, "stage": "starting", "step": "2/4 taking the single-runner lock",
                                         "ts_utc": (now - timedelta(seconds=5)).isoformat()})
    assert rd.runner_check(now, procs=lambda: [[22352]], runtime_dir=starting)["status"] == rd.WARNING


def test_after_report_time_completed_or_not(tmp_path):
    late = _at("17:00")
    ok = _files(tmp_path, status={"pid": 1, "stage": "exited", "exit_reason": "completed", "session_date": str(MON),
                                  "ts_utc": late.isoformat()})
    c = rd.runner_check(late, procs=lambda: [], runtime_dir=ok)
    assert c["status"] == rd.WARNING and "says completed, but" in c["summary"]       # status file alone is not enough
    from trading.operations.store import OpsStore
    st = OpsStore(ok / "operations.sqlite")
    st.db.execute("INSERT INTO reports (session_date, version, created_utc, classification) VALUES (?,?,?,?)",
                  (str(MON), 1, late.isoformat(), "INCOMPLETE"))
    st.db.commit()
    st.close()
    assert rd.runner_check(late, procs=lambda: [], runtime_dir=ok)["status"] == rd.PASS
    (ok / "runner_status.json").unlink()
    assert rd.runner_check(late, procs=lambda: [], runtime_dir=ok)["status"] == rd.WARNING


# ---------------------------------------------------------------- 4. runner start-up progress and watchdog

class FakeRunner:
    calls = {}

    def __init__(self, store, reports_dir=None, echo=print, status_path=None, on_tick=None):
        FakeRunner.calls.update(status_path=status_path, echo=echo)
        self.on_tick = on_tick

    def run(self):
        self.on_tick()
        return 0


def test_run_records_each_startup_step_and_logs(tmp_path, monkeypatch, capsys):
    from trading.operations import __main__ as om
    from trading.operations import progress, runner
    monkeypatch.setenv("TRADING_OPS_DIR", str(tmp_path / "ops"))
    monkeypatch.setattr(runner, "Runner", FakeRunner)
    assert om.main(["run"]) == 0
    out = capsys.readouterr().out
    for s in ("[start-up 1/4]", "[start-up 2/4]", "[start-up 3/4]", "[start-up 4/4]", "OK: start-up complete"):
        assert s in out
    folder = tmp_path / "ops"
    assert progress.read(folder / progress.STARTUP_NAME)["stage"] == "handed over"
    assert "[start-up 4/4]" in (folder / progress.LOG_NAME).read_text(encoding="utf-8")
    assert FakeRunner.calls["status_path"] == folder / progress.STATUS_NAME


def test_second_runner_is_refused_and_says_so(tmp_path, monkeypatch, capsys):
    from trading.monitor.worker import SingleInstanceLock
    from trading.operations import __main__ as om
    from trading.operations import progress, runner
    monkeypatch.setenv("TRADING_OPS_DIR", str(tmp_path / "ops"))
    monkeypatch.setattr(runner, "Runner", FakeRunner)
    (tmp_path / "ops").mkdir()
    held = SingleInstanceLock(tmp_path / "ops" / "runner.lock")
    assert held.acquire()
    try:
        assert om.main(["run"]) == 4
    finally:
        held.release()
    assert "FAILED: another dry-run runner is already running" in capsys.readouterr().out
    assert progress.read(tmp_path / "ops" / progress.STARTUP_NAME)["stage"] == "refused"


def test_startup_hang_writes_stack_traces(tmp_path, monkeypatch):
    import time as _t
    from trading.operations import __main__ as om
    from trading.operations import progress, runner
    monkeypatch.setenv("TRADING_OPS_DIR", str(tmp_path / "ops"))
    monkeypatch.setattr(runner, "Runner", FakeRunner)
    monkeypatch.setattr(om, "STARTUP_WATCHDOG_S", 1)
    real = om._load_heavy
    monkeypatch.setattr(om, "_load_heavy", lambda: (_t.sleep(2.5), real()))        # SYNTHETIC slow start-up
    assert om.main(["run"]) == 0
    faults = (tmp_path / "ops" / progress.FAULTS_NAME).read_text(encoding="utf-8")
    assert "watchdog armed" in faults and "File " in faults                          # a traceback was dumped


def test_runner_status_file_tracks_the_run(tmp_path, monkeypatch):
    """SYNTHETIC holiday run of the real Runner: the status file ends as 'exited / no session'."""
    from trading.operations import progress
    from trading.operations.runner import Runner
    from trading.operations.store import OpsStore
    monkeypatch.setenv("TRADING_OPS_DIR", str(tmp_path / "ops"))
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "false")
    ticks = []
    s = OpsStore(tmp_path / "ops" / "operations.sqlite")
    holiday = datetime(2026, 11, 26, 13, 0, tzinfo=timezone.utc)
    r = Runner(s, now_fn=lambda: holiday, echo=lambda *a: None, status_path=tmp_path / "ops" / "st.json",
               on_tick=lambda: ticks.append(1))
    assert r.run() == 0
    st_ = progress.read(tmp_path / "ops" / "st.json")
    assert st_["stage"] == "exited" and st_["exit_reason"] == "no session" and st_["session_date"] == "2026-11-26"
    s.close()


# ---------------------------------------------------------------- 5. city-server lifecycle evidence (harness)

def test_server_lifecycle_is_recorded(tmp_path, monkeypatch):
    from trading.dashboard import server as srv
    from trading.monitor import control
    monkeypatch.setattr(st, "DB_PATH", tmp_path / "monitor_SYNTHETIC.sqlite")
    launched = []
    monkeypatch.setattr(control, "SPAWN", lambda *a, **k: launched.append(a) or 4242)
    monkeypatch.setattr(rd, "SERVER_INFO", {})
    httpd, ctrl, stop = srv.create_server(None, 0, supervise_monitor=True, run_jobs=False)
    try:
        s = st.MonitorStore()
        runs = rd.server_runs(s)
        assert len(runs) == 1 and runs[0]["pid"] and runs[0]["stopped_utc"] is None
        control.Supervisor(threading.Event()).server_alive()
        rd.server_stopped(s, rd.SERVER_INFO["run_id"], "clean stop (SYNTHETIC)")
        row = rd.server_runs(s)[0]
        assert row["exit_reason"] == "clean stop (SYNTHETIC)" and row["stopped_utc"]
        assert any("city server started" in e["message"] for e in s.events(10))
        s.close()
    finally:
        stop.set()
        httpd.server_close()


# ---------------------------------------------------------------- 6. one inspectable start-up

def _startup(capsys, **kw):
    from trading import startup
    defaults = dict(probe_server=lambda port: {"mode": "DEMO_REPLAY", "banner": "x"},
                    readiness_fn=lambda port: {"checks": [
                        {"id": "worker_count", "label": "worker", "status": "PASS", "summary": "one worker"},
                        {"id": "heartbeat", "label": "heartbeat", "status": "PASS", "summary": "fresh"}]},
                    runner_check_fn=lambda t: {"status": "PASS", "summary": "running (pid 1)", "detail": {}},
                    launch=lambda args: pytest.fail(f"must not launch {args}"), sleep=lambda s: None, venv_ok=True,
                    now_fn=lambda: _at("09:00"))                       # fixed pre-open time (not the real clock)
    defaults.update(kw)
    code = startup.run(**defaults)
    return code, capsys.readouterr().out


def test_startup_reuses_healthy_processes(monkeypatch, capsys):
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "false")
    code, out = _startup(capsys)
    assert code == 0 and "already running" in out and "READY:" in out


def test_startup_starts_missing_parts_and_waits(monkeypatch, capsys):
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "false")
    launched, probes, checks = [], iter([None, None, {"mode": "DEMO_REPLAY", "banner": "x"}]), iter([
        {"status": "FAIL", "summary": "no dry-run runner is running during today's session window", "detail": {}},
        {"status": "WARNING", "summary": "starting", "detail": {"runner_startup": {"step": "1/4 loading code"}}},
        {"status": "PASS", "summary": "running (pid 9)", "detail": {}}])
    code, out = _startup(capsys, probe_server=lambda port: next(probes, {"mode": "DEMO_REPLAY", "banner": "x"}),
                         launch=lambda args: launched.append(args) or 99, runner_check_fn=lambda t: next(checks))
    assert code == 0 and [a[1] for a in launched] == ["trading.dashboard.server", "trading.operations"]
    assert "start-up step: 1/4 loading code" in out and "READY:" in out


def test_startup_reports_stalled_runner_and_never_starts_another(monkeypatch, capsys):
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "false")
    code, out = _startup(capsys, runner_check_fn=lambda t: {"status": "FAIL", "detail": {},
                                                            "summary": "STALLED: runner process [1, 2] is alive but silent"})
    assert code == 1 and "NOT READY" in out and "Do not start a second one" in out


def test_startup_unsafe_flags_or_foreign_port_are_not_ready(monkeypatch, capsys):
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "true")
    code, out = _startup(capsys)
    assert code == 1 and "order submission must be blocked" in out
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "false")
    code, out = _startup(capsys, probe_server=lambda port: {"unrecognised": True})
    assert code == 1 and "used by another program" in out


def test_startup_runner_that_never_reports_running_is_not_ready(monkeypatch, capsys):
    from trading import startup
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "false")
    monkeypatch.setattr(startup, "RUNNER_WAIT_S", 0.01)
    code, out = _startup(capsys, launch=lambda args: 7, runner_check_fn=lambda t: {
        "status": "FAIL", "summary": "no dry-run runner is running during today's session window", "detail": {}})
    assert code == 1 and "did not reach 'running'" in out


def test_check_only_never_launches(monkeypatch, capsys):
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "false")
    code, out = _startup(capsys, check_only=True, probe_server=lambda port: None,
                         runner_check_fn=lambda t: {"status": "FAIL", "detail": {},
                                                    "summary": "no dry-run runner is running during today's session window"})
    assert code == 1 and "CHECK ONLY" in out and out.count("nothing was started") == 2   # launch would pytest.fail


# ---------------------------------------------------------------- report reproducibility and correction counts (2026-11-10)

def test_reports_carry_reproducibility_metadata_outside_the_evidence_hash():
    from trading.monitor import reliability as rl
    cut = datetime(2026, 11, 16, 21, 45, tzinfo=timezone.utc)
    meta = rl.reproducibility(cut)
    assert meta["evidence_cutoff_utc"].startswith("2026-11-16T21:45") and meta["calc_version"] == rl.REPORT_CALC_VERSION
    assert len(meta["config_fingerprint"]) == 16 and "as_of" in meta["recompute"]


def test_correction_that_left_reclassified_events_uncounted_is_flagged_once():
    from trading.monitor import reliability as rl
    ev = {"kind": "incident", "ts_utc": "2026-11-16T15:00:00+00:00", "message": "synthetic"}
    stored = {"status": {"state": "finalized", "detail": rl.FINALIZED_DETAIL},
              "evidence": {"operations": {"request_failures": 0, "failure_events": [], "other_errors": 116,
                                          "failure_events_reclassified_as_other": [ev, ev]}}}
    assert rl.plan_correction(stored) == [{"field": "evidence.operations.other_errors", "old": 116, "new": 118,
                                           "why": "2 event(s) reclassified by an earlier correction were not added to other_errors"}]
    stored["evidence"]["operations"]["reclassified_counted_in_other_errors"] = True
    assert rl.plan_correction(stored) == []
