"""Research desk (trading/dashboard/desk.py) and /api/desk. Inputs are SYNTHETIC fixtures; the trace records come
from a fixture session (tests/test_evidence_trace.py). No real store, broker or provider is touched."""

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from trading.dashboard import desk
from trading.jobs import JobStore
from trading.monitor import evidence_trace as et
from tests.test_evidence_trace import DATE, make_session

UTC = timezone.utc
NOW = datetime(2026, 11, 10, 17, 0, tzinfo=UTC)


def base_inputs(**over):
    inp = {
        "depmap_nodes": {"monitor_worker": {"status": "OK", "evidence": ["running"]}, "quality": {"status": "OK", "evidence": []},
                         "supervisor": {"status": "OK", "evidence": []}, "history": {"status": "CLOSED", "evidence": []},
                         "report": {"status": "OK", "evidence": []}},
        "readiness": {"heartbeat": {"status": "PASS", "summary": "1 s", "checked_utc": NOW.isoformat()},
                      "latest_data": {"status": "PASS", "summary": "fresh", "checked_utc": NOW.isoformat()}},
        "incidents": [], "server_run": {"pid": 1, "started_utc": NOW.isoformat()}, "finalized_sessions": [],
        "reliability": {"target": 5, "current_consecutive": 4, "gap": "no capture threshold"},
        "trace": None, "trace_runs": [],
        "operations": {"order_gate": {"enabled": False}, "kill_switch": {"on": False}, "approved_strategy": "approved: NONE",
                       "runner": {"run_id": "r-today", "session_date": "2026-11-10", "started_utc": NOW.isoformat(), "alive": True},
                       "acceptance": {"current_streak": 0, "required_consecutive_passes": 5, "sessions": []}},
        "runner_status": {"run_id": "r-today", "session_date": "2026-11-10"},
        "experiments": [{"id": "001", "status": "CLOSED: failed", "path": "x"}, {"id": "002", "status": "FAILED_DEVELOPMENT", "path": "y"}],
        "locks": [{"id": "001", "ok": True, "result": "matches"}], "journals": [], "workflow": None, "errors": [],
    }
    inp.update(over)
    return inp


def tasks(d):
    return {t["id"]: t for dep in d["departments"] for t in dep["tasks"]}


def test_every_state_is_honest_and_from_the_allowed_set():
    d = desk.build_desk(base_inputs(), NOW)
    t = tasks(d)
    assert {x["state"] for x in t.values()} <= set(desk.STATES)
    assert [x["id"] for x in d["departments"]] == ["data", "research", "risk", "operations", "archive", "command"]
    assert t["op_gate"]["state"] == "NOT IMPLEMENTED" and "PROPOSED" in t["op_gate"]["blocker"]
    assert t["ro_reconciliation"]["state"] == "NOT IMPLEMENTED"
    assert t["ro_order_gate"]["state"] == "DISABLED"
    for rid in ("ro_sizing", "ro_exposure", "ro_loss_halt"):                    # simulation only; no execution path
        assert t[rid]["simulation_only"] is True and t[rid]["execution_path"] == "none" and "NO" in t[rid]["outcome"]
    assert all(m["state"] == "DISABLED" for m in t.values() if m["id"].startswith("ma_"))
    assert t["rl_specs"]["state"] == "CLOSED" and t["rl_replay"]["state"] == "CLOSED"     # closed experiments stay closed
    assert t["dc_collection"]["state"] == "RUNNING" and "never starts a second collector" in t["dc_collection"]["note"]
    assert t["dc_structural"]["state"] == "IDLE" and "no evidence-trace run" in t["dc_structural"]["blocker"]
    heads = {x["id"]: x["headline"] for x in d["departments"]}
    assert heads["risk"] == "IDLE"                     # nothing in the Risk Office has run; never shown as OK/SUCCEEDED


def test_missing_sources_are_unknown_never_ok():
    d = desk.build_desk({"errors": ["monitor: FileNotFoundError"]}, NOW)
    t = tasks(d)
    assert t["dc_collection"]["state"] == "UNKNOWN" and t["dc_freshness"]["state"] == "UNKNOWN"
    assert t["op_health"]["state"] == "UNKNOWN" and t["ro_order_gate"]["state"] == "UNKNOWN"
    assert d["input_errors"] == ["monitor: FileNotFoundError"]


def test_stale_data_and_failed_checks_show_as_failed():
    d = desk.build_desk(base_inputs(readiness={"latest_data": {"status": "FAIL", "summary": "IWM stale 300 s", "checked_utc": NOW.isoformat()},
                                               "heartbeat": {"status": "FAIL", "summary": "no heartbeat", "checked_utc": NOW.isoformat()}},
                                    depmap_nodes={"monitor_worker": {"status": "STALE", "evidence": ["stale"]}}), NOW)
    t = tasks(d)
    assert t["dc_freshness"]["state"] == "FAILED" and t["dc_collection"]["state"] == "FAILED" and t["op_health"]["state"] == "FAILED"
    assert d["command_centre"]["next_eligible"]["action"] == "investigate (owner)"


def test_dry_run_record_discrepancy_is_a_failure_not_a_pass():
    d = desk.build_desk(base_inputs(operations={**base_inputs()["operations"], "runner": {"run_id": "old", "session_date": "2026-11-08",
                                                                                           "started_utc": "2026-11-09T02:43:13+00:00", "alive": False}},
                                    runner_status={"run_id": "new", "session_date": "2026-11-10", "heartbeat_utc": NOW.isoformat()}), NOW)
    t = tasks(d)["op_dry_run"]
    assert t["state"] == "FAILED" and "no run record for 2026-11-10" in t["blocker"]


def test_command_centre_is_deterministic_and_only_names_manual_authorized_commands():
    inp = base_inputs(finalized_sessions=["2026-11-04", "2026-11-05"],
                      trace_runs=[{"run_id": "r1", "session_date": "2026-11-04", "status": "COMPLETED", "created_utc": "", "finished_utc": ""}])
    a, b = desk.build_desk(inp, NOW), desk.build_desk(inp, NOW)
    assert a["command_centre"] == b["command_centre"]
    nxt = a["command_centre"]["next_eligible"]
    assert nxt["command"] == "python -m trading.monitor.evidence_trace run --date 2026-11-05"
    assert a["command_centre"]["untraced_finalized_sessions"] == ["2026-11-05"]
    for c in a["command_centre"]["candidates"]:
        assert c["command"] is None or c["command"].startswith("python -m trading.monitor.evidence_trace run --date ")
    assert "enable broker order submission" in a["command_centre"]["prohibited"]


def test_desk_module_has_no_broker_or_order_code():
    src = Path(desk.__file__).read_text(encoding="utf-8") + Path(et.__file__).read_text(encoding="utf-8")
    for bad in ("alpaca_client", "submit_order", "requests.post", "urllib.request", "ANTHROPIC", "anthropic"):
        assert bad not in src


@pytest.fixture
def traced(tmp_path, monkeypatch):
    clock = make_session()
    dbp = tmp_path / "desk.sqlite"
    js = JobStore(dbp)
    run = et.run_trace(DATE, desk=js, now=clock(), source="fixture")
    js.close()
    monkeypatch.setattr(et, "DESK_DB", dbp)
    return dbp, run


def test_desk_tasks_agree_with_stored_trace_records(traced):
    dbp, run = traced
    trace = et.recent_runs(dbp)[0]
    d = desk.build_desk(base_inputs(trace=trace, trace_runs=et.recent_runs(dbp), finalized_sessions=[DATE]), NOW)
    t = tasks(d)
    js = JobStore(dbp)
    try:
        stored = {r["worker"]: r["status"] for r in js.db.execute("SELECT worker, status FROM jobs")}
    finally:
        js.close()
    mapping = {"capture_inventory": "dc_inventory", "structural_validation": "dc_structural", "iex_sip_comparison": "dc_iex_sip",
               "revision_tracking": "dc_revisions", "reliability_assessment": "op_reliability", "report_finalization": "ea_reports"}
    for worker, tid in mapping.items():
        assert stored[worker] == "completed" and t[tid]["state"] == "SUCCEEDED"
        assert t[tid]["record"]["task_record"].startswith(f"evidence_trace:{DATE}:{worker}:")
    assert d["command_centre"]["untraced_finalized_sessions"] == []
    rec = [e for e in d["edges"] if e["recorded"]]
    assert {(e["from"], e["to"]) for e in rec} == {("data", "operations"), ("operations", "archive")}
    assert all(e["event_id"].endswith(":SUCCEEDED") for e in rec)        # animation keyed to a stored transition


def test_api_desk_serves_the_same_records(traced, tmp_path, monkeypatch):
    dbp, run = traced
    monkeypatch.setenv("TRADING_OPS_DIR", str(tmp_path / "ops"))
    from trading.dashboard.server import DEFAULT_CONFIG, create_server
    httpd, ctrl, stop = create_server(DEFAULT_CONFIG, 0, 3600, run_jobs=False, supervise_monitor=False)
    import threading
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    try:
        port = httpd.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/desk", timeout=60) as r:
            api = json.loads(r.read())
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/desk?run={run['run_id']}", timeout=60) as r:
            api_run = json.loads(r.read())
    finally:
        stop.set(); httpd.shutdown(); httpd.server_close()
    assert api["trace"]["run_id"] == run["run_id"] == api_run["trace"]["run_id"]
    assert [t["status"] for t in api["trace"]["tasks"]] == [t["status"] for t in run["tasks"]]
    t = tasks(api)
    assert t["dc_inventory"]["state"] == "SUCCEEDED" and t["ea_reports"]["state"] == "SUCCEEDED"
    assert t["ro_order_gate"]["state"] in ("DISABLED", "UNKNOWN")
    assert all(x["state"] != "RUNNING" for x in t.values() if x["id"] in ("dc_inventory", "op_reliability", "ea_reports"))
