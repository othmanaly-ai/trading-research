"""Evidence trace (trading/monitor/evidence_trace.py). ALL MARKET DATA HERE IS SYNTHETIC: a labelled fixture
session built in a temporary folder by the existing QualityChecker. Nothing here is evidence about any feed,
and no test touches the real monitoring store (conftest redirects it)."""

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from trading.jobs import JobStore
from trading.monitor import evidence_trace as et
from trading.monitor import quality as q
from trading.monitor import store as mst
from tests.test_quality import OPEN, SYMS, Clock, FakeFeeds, checker, run_until_idle

UTC = timezone.utc
DATE = "2026-11-04"
AFTER = datetime(2026, 11, 4, 21, 50, tzinfo=UTC)          # close + 15 + 30 min: recheck done, finalizable


def _live(store, skip=()):
    """SYNTHETIC live IEX capture: one bar per minute per symbol, received 5 s after the bar end."""
    run = store.start_run(4242, "fixture", {"symbols": list(SYMS)}, OPEN - timedelta(minutes=5))
    for m in range(390):
        t = OPEN + timedelta(minutes=m)
        for s in SYMS:
            if (s, m) in skip:
                continue
            store.insert_bars(s, "iex", [{"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": 100.0, "h": 100.5, "l": 99.5,
                                          "c": 100.2, "v": 1000, "n": 10, "vw": 100.2}], t + timedelta(seconds=65))
        store.touch_run(run, t + timedelta(seconds=65))
    store.end_run(run, OPEN + timedelta(minutes=400), "fixture end")
    store.db.commit()


def make_session(finalize=True, skip=(("IWM", 10), ("IWM", 11))):
    store = mst.MonitorStore()
    q.ensure_schema(store)
    _live(store, skip)
    clock = Clock(AFTER if finalize else OPEN + timedelta(minutes=90))
    feeds = FakeFeeds()
    feeds.fill("sip", OPEN, 390)
    feeds.fill("iex", OPEN, 390)
    qc = checker(store, clock)
    run_until_idle(qc, feeds, clock)
    store.close()
    return clock


def dump_sha(path):
    db = sqlite3.connect(path)
    try:
        return hashlib.sha256("\n".join(db.iterdump()).encode()).hexdigest()
    finally:
        db.close()


@pytest.fixture
def desk(tmp_path):
    js = JobStore(tmp_path / "desk.sqlite")
    yield js
    js.close()


@pytest.fixture(autouse=True)
def _reset_hooks():
    yield
    et.HOOK = None
    et.HANDLER_OVERRIDES.clear()


def states(res):
    return {t["task"]: t["status"] for t in res["tasks"]}


def test_finalized_session_traces_end_to_end_without_touching_the_monitoring_store(desk):
    clock = make_session()
    before = dump_sha(mst.DB_PATH)
    res = et.run_trace(DATE, desk=desk, now=clock(), source="fixture")
    assert res["status"] == "COMPLETED" and set(states(res).values()) == {"SUCCEEDED"}
    assert dump_sha(mst.DB_PATH) == before                                   # read from a snapshot only
    out = {t["task"]: t["output"] for t in res["tasks"]}
    assert out["capture_inventory"]["per_symbol"]["IWM"] == {"received": 388, "on_time": 388, "late": 0}
    assert out["structural_validation"]["defects_per_symbol"] == {"SPY": 0, "QQQ": 0, "IWM": 0}
    assert out["iex_sip_comparison"]["runs_failed"] == 0 and out["iex_sip_comparison"]["categories"]
    rel = out["reliability_assessment"]
    assert rel["report_state"] == "finalized" and rel["missing_by_symbol"]["IWM"] == 2
    assert rel["reliability_gate"]["status"] == "PROPOSED, NOT ACTIVE"
    rep = out["report_finalization"]
    assert rep["latest_version"] == 1 and rep["integrity"].startswith("stored hash matches")
    t0 = res["tasks"][0]
    assert t0["inputs"]["source"] == "fixture" and t0["inputs"]["input_refs"]["bars"]["rows"] == 388 * 1 + 390 * 2
    assert t0["inputs"]["parent_run_id"] == res["run_id"] and t0["output_fingerprint"]
    assert "key" not in json.dumps(t0["inputs"]).lower().replace("input_key", "")    # no credentials in records


def test_missing_monitoring_store_fails_first_task_and_blocks_the_rest(desk, tmp_path):
    res = et.run_trace(DATE, desk=desk, monitor_db=tmp_path / "absent.sqlite", now=AFTER)
    s = states(res)
    assert s["capture_inventory"] == "FAILED" and "input missing" in res["tasks"][0]["error"]
    assert all(v == "BLOCKED" for k, v in s.items() if k != "capture_inventory")
    assert all("upstream failed" in t["error"] for t in res["tasks"][1:])
    assert res["status"] == "FAILED"


def test_session_not_monitored_is_a_failure_not_a_pass(desk):
    make_session()
    res = et.run_trace("2026-11-05", desk=desk, now=AFTER + timedelta(days=1))
    assert states(res)["capture_inventory"] == "FAILED" and "no live bar" in res["tasks"][0]["error"]


def test_stale_comparison_blocks_downstream_until_the_session_is_finalized(desk):
    clock = make_session(finalize=False)
    res = et.run_trace(DATE, desk=desk, now=clock())
    s = states(res)
    assert s["capture_inventory"] == "SUCCEEDED" and s["structural_validation"] == "SUCCEEDED"
    assert s["iex_sip_comparison"] == "BLOCKED" and "20 minutes old" in res["tasks"][2]["error"]
    assert s["revision_tracking"] == s["reliability_assessment"] == s["report_finalization"] == "BLOCKED"
    assert res["status"] == "BLOCKED"


def test_duplicate_request_while_running_returns_the_active_run(desk):
    clock = make_session()
    seen = {}

    def hook(task):
        if task == "structural_validation" and "dup" not in seen:
            seen["dup"] = et.run_trace(DATE, desk=desk, now=clock())
    et.HOOK = hook
    res = et.run_trace(DATE, desk=desk, now=clock())
    assert seen["dup"]["duplicate_request"] is True and seen["dup"]["run_id"] == res["run_id"]
    assert desk.db.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0] == 1
    assert res["status"] == "COMPLETED"


def test_unchanged_inputs_are_reused_and_changed_inputs_recomputed(desk):
    clock = make_session()
    first = et.run_trace(DATE, desk=desk, now=clock())
    second = et.run_trace(DATE, desk=desk, now=clock() + timedelta(minutes=1))
    assert set(states(second).values()) == {"REUSED"}
    ids = {t["task"]: t["id"] for t in first["tasks"]}
    for t in second["tasks"]:
        assert t["reused_from"] == ids[t["task"]] and t["output"] == next(x["output"] for x in first["tasks"] if x["task"] == t["task"])
    # a late live bar arrives for a missing minute: inputs change, so the dependent results are recomputed
    store = mst.MonitorStore()
    t = OPEN + timedelta(minutes=10)
    store.insert_bars("IWM", "iex", [{"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": 100.0, "h": 100.5, "l": 99.5, "c": 100.2,
                                      "v": 1000, "n": 10, "vw": 100.2}], t + timedelta(hours=2))
    store.db.commit()
    store.close()
    third = et.run_trace(DATE, desk=desk, now=clock() + timedelta(minutes=2))
    s = states(third)
    assert s["capture_inventory"] == "SUCCEEDED" and s["iex_sip_comparison"] == "REUSED"
    assert next(x for x in third["tasks"] if x["task"] == "capture_inventory")["output"]["per_symbol"]["IWM"]["late"] == 1


def test_invalid_output_is_rejected_and_blocks_downstream(desk):
    clock = make_session()
    et.HANDLER_OVERRIDES["capture_inventory"] = lambda ctx: {"scheduled_minutes": 390,
                                                             "per_symbol": {"SPY": {"received": 5, "on_time": 1, "late": 1}}}
    res = et.run_trace(DATE, desk=desk, now=clock())
    cap = res["tasks"][0]
    assert cap["status"] == "FAILED" and cap["error"].startswith("invalid output rejected")
    assert desk.db.execute("SELECT COUNT(*) FROM jobs WHERE status='completed' AND worker='capture_inventory'").fetchone()[0] == 0
    assert states(res)["reliability_assessment"] == "BLOCKED"


def test_a_result_may_not_claim_the_proposed_gate_is_active():
    assert et.validate_output("reliability_assessment", {"report_state": "finalized", "evidence_fingerprint": "a" * 64,
                                                         "reliability_gate": {"status": "ACTIVE"}})
    assert et.validate_output("capture_inventory", {"scheduled_minutes": 10, "per_symbol": {"SPY": {"received": 11, "on_time": 11, "late": 0}}})


def test_upstream_failure_blocks_only_its_dependants(desk):
    clock = make_session()

    def boom(ctx):
        raise RuntimeError("synthetic handler failure")
    et.HANDLER_OVERRIDES["structural_validation"] = boom
    res = et.run_trace(DATE, desk=desk, now=clock())
    s = states(res)
    assert s["structural_validation"] == "FAILED" and "synthetic handler failure" in res["tasks"][1]["error"]
    assert s["iex_sip_comparison"] == "SUCCEEDED" and s["revision_tracking"] == "SUCCEEDED"    # independent branch
    assert s["reliability_assessment"] == "BLOCKED" and "upstream failed" in res["tasks"][4]["error"]
    assert res["status"] == "FAILED"


def test_interrupted_run_is_recovered_as_failed_and_a_restart_completes(desk):
    clock = make_session()

    def stop(task):
        if task == "reliability_assessment":
            raise KeyboardInterrupt                                    # process killed mid-task
    et.HOOK = stop
    with pytest.raises(KeyboardInterrupt):
        et.run_trace(DATE, desk=desk, now=clock())
    assert desk.db.execute("SELECT status FROM jobs WHERE worker='reliability_assessment'").fetchone()[0] == "running"
    et.HOOK = None
    res = et.run_trace(DATE, desk=desk, now=clock() + timedelta(minutes=1))
    old = desk.db.execute("SELECT status, error FROM jobs WHERE worker='reliability_assessment' AND attempt=1").fetchone()
    assert old["status"] == "failed" and old["error"].startswith("interrupted")
    first_pipe = desk.db.execute("SELECT status FROM pipelines ORDER BY rowid LIMIT 1").fetchone()[0]
    assert first_pipe == "failed"
    s = states(res)
    assert s["capture_inventory"] == "REUSED" and s["reliability_assessment"] == "SUCCEEDED"
    assert next(t for t in res["tasks"] if t["task"] == "reliability_assessment")["attempt"] == 2
    assert res["status"] == "COMPLETED"


def test_tampered_stored_report_fails_the_integrity_check(desk):
    clock = make_session()
    db = sqlite3.connect(mst.DB_PATH)
    rep = json.loads(db.execute("SELECT report_json FROM q_reports").fetchone()[0])
    rep["evidence"]["schedule"]["scheduled_minutes"] = 1
    db.execute("UPDATE q_reports SET report_json=?", (json.dumps(rep),))      # fixture store only
    db.commit()
    db.close()
    res = et.run_trace(DATE, desk=desk, now=clock())
    assert states(res)["report_finalization"] == "FAILED" and "integrity" in res["tasks"][-1]["error"]


# ---------------------------------------------------------------- report reproducibility (2026-11-10)

def test_new_reports_record_their_cutoff_and_reproduce_exactly(desk):
    clock = make_session()
    db = sqlite3.connect(mst.DB_PATH)
    rep = json.loads(db.execute("SELECT report_json FROM q_reports").fetchone()[0])
    db.close()
    meta = rep["reproducibility"]
    assert meta["evidence_cutoff_utc"] and meta["calc_version"] == 2 and meta["config_fingerprint"]
    res = et.run_trace(DATE, desk=desk, now=clock() + timedelta(days=1))
    out = res["tasks"][-1]["output"]
    assert out["evidence_cutoff_source"] == "recorded in the report"
    assert out["reproduction"].endswith("identical to the stored report") and out["difference_counts"] == {}


def test_evidence_after_the_cutoff_is_later_evidence_not_a_difference(desk):
    clock = make_session()
    store = mst.MonitorStore()
    run = store.start_run(777, "fixture-later", {"symbols": list(SYMS)}, AFTER + timedelta(minutes=30))   # after finalization
    store.touch_run(run, AFTER + timedelta(minutes=40))
    store.event("error", "supervisor", "synthetic later error", AFTER + timedelta(minutes=35))
    store.db.commit()
    store.close()
    res = et.run_trace(DATE, desk=desk, now=clock() + timedelta(hours=1))
    out = res["tasks"][-1]["output"]
    assert "operations.worker_runs" in out["later_evidence_fields"]
    assert out["reproduction"].endswith("identical to the stored report")          # identical at the cutoff
    assert out["difference_counts"].get("later_evidence")


def test_correction_that_drops_reclassified_events_is_flagged_and_now_counted():
    from trading.monitor import reliability
    stored = {"status": {"state": "finalized", "detail": reliability.FINALIZED_DETAIL},
              "evidence": {"operations": {"request_failures": 0, "failure_events": [], "other_errors": 5,
                                          "failure_events_reclassified_as_other": [{"kind": "incident", "ts_utc": "t", "message": "m"}] * 2}}}
    plan = reliability.plan_correction(stored)
    assert plan == [{"field": "evidence.operations.other_errors", "old": 5, "new": 7,
                     "why": "2 event(s) reclassified by an earlier correction were not added to other_errors"}]
    stored["evidence"]["operations"]["reclassified_counted_in_other_errors"] = True
    assert reliability.plan_correction(stored) == []
    # a new correction counts the moved events where they belong
    make_session()
    store = mst.MonitorStore()
    row = store.db.execute("SELECT report_json FROM q_reports").fetchone()
    rep = json.loads(row[0])
    ops = rep["evidence"]["operations"]
    ops["failure_events"] = [{"kind": "incident", "ts_utc": "2026-11-04T15:00:00+00:00", "message": "synthetic"}]
    ops["request_failures"] = 1
    before = ops["other_errors"]
    store.db.execute("UPDATE q_reports SET report_json=?", (json.dumps(rep),))      # fixture store only
    store.db.commit()
    res = reliability.correct_stored_report(store, DATE, "fixture correction", AFTER, apply=True)
    new = json.loads(store.db.execute("SELECT report_json FROM q_reports WHERE version=2").fetchone()[0])["evidence"]["operations"]
    store.close()
    assert res["stored"] and new["request_failures"] == 0 and new["other_errors"] == before + 1
    assert new["reclassified_counted_in_other_errors"] is True


def test_changed_handler_source_is_recomputed_not_reused(desk, monkeypatch):
    clock = make_session()
    et.run_trace(DATE, desk=desk, now=clock())
    monkeypatch.setattr(et, "code_version", lambda: "same-git-label|src:changed")       # source edited, label unchanged
    res = et.run_trace(DATE, desk=desk, now=clock() + timedelta(minutes=1))
    assert set(states(res).values()) == {"SUCCEEDED"}
