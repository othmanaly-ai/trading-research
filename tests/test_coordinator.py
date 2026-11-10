"""Coordinator workflow. SYNTHETIC fixture files in a temporary root; never the real research records,
job store or monitoring database."""

import json
from pathlib import Path

import pytest

from trading import coordinator as c
from trading import jobs
from trading.jobs import JobStore


def _w(root: Path, rel: str, data) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


@pytest.fixture()
def root(tmp_path):
    return make_root(tmp_path)


def make_root(tmp_path):
    r = tmp_path / "proj"
    _w(r, "research/001_intraday_momentum/STATUS.json", {"state": "FAILED_DEVELOPMENT", "failed_rules": ["1", "2"], "development_run_id": "R1"})
    _w(r, "research/002_opening_range_breakout/STATUS.json", {"state": "FAILED_DEVELOPMENT", "failed_rules": ["D1"], "development_run_id": "R2"})
    _w(r, "research/001_intraday_momentum/runs/R1.json", {"results_by_cost": {"base": {"net_return": -0.0141}, "stress": {"net_return": -0.03}},
                                                          "random_direction": {"strategy_percentile": 10.0}})
    _w(r, "research/002_opening_range_breakout/runs/R2.json", {"primary": {"base": {"net_return": -0.0001, "gross_pnl": 1166.0, "trades": 1058},
                                                                           "stress": {"net_return": -0.022}},
                                                               "diagnostics": {"B1": {"1": {"strategy_percentile": 83.0}}}})
    for rel in ("research/001_intraday_momentum/SPEC.md", "research/001_intraday_momentum/RESULTS_development.md",
                "research/002_opening_range_breakout/SPEC.md", "research/002_opening_range_breakout/RESULTS_development.md",
                "feasibility/spread_measurement/FINDINGS_pilot.md", "feasibility/spread_measurement/PLAN.md",
                "research/FEASIBILITY_gap_down_opening.md", "research/NEXT_HYPOTHESES.md", "research/EXPLORATION_LOG.md"):
        _w(r, rel, "SYNTHETIC fixture text\n")
    _w(r, "trading/costs.py", "# SYNTHETIC copy marker; values come from trading.costs\n")
    _w(r, "feasibility/spread_measurement/findings_pilot.json",
       {"groups": {"E1": {"by_date": {"2016-01-04": {"half_spread_bp": 0.25}, "2021-01-04": {"half_spread_bp": 0.12}}}}})
    _w(r, "feasibility/execution_data/ALPACA_SUPPORT_REQUEST_DRAFT.md", "| # | Needed |\n|---|---|\n| A1 | clock |\n| A2 | code |\n")
    _w(r, "research/candidates/gap_down_opening/STATUS.json", {"state": "DEFERRED_DATA_SEMANTICS"})
    return r


@pytest.fixture()
def store(tmp_path):
    s = JobStore(tmp_path / "workflows.sqlite")
    yield s
    s.close()


def claim(cid, text, cites, figures=()):
    return {"id": cid, "text": text, "cites": list(cites), "figures": list(figures)}


def strategy_doc(snap, **over):
    d = {"task": "strategy_analysis", "evidence_snapshot": snap, "author": "Claude (interactive Claude Code session)",
         "mode": "claude_code_session", "requested_actions": ["owner_decision"],
         "sections": {
             "why_001_failed": {"claims": [claim("S1", "001 lost after base costs.", ["E4"], [{"fact": "001.base_net_return", "value": -0.0141}])]},
             "why_002_failed": {"claims": [claim("S2", "002 ranked below the 95th percentile.", ["E8"], [{"fact": "002.b1_percentile", "value": 83.0}])]},
             "decision": {"recommendation": "SYNTHETIC decision", "alternatives": ["a", "b"], "evidence_needed": ["x"],
                          "is_proposal_only": True, "claims": []}}}
    d.update(over)
    return d


def data_doc(snap, **over):
    d = {"task": "data_cost_analysis", "evidence_snapshot": snap, "author": "Claude (interactive Claude Code session)",
         "mode": "claude_code_session", "requested_actions": [],
         "sections": {
             "spread_establishes": {"claims": [claim("D1", "Half-spread 0.12-0.25 bp.", ["E11"], [{"fact": "pilot.half_spread_bp_max", "value": 0.25}])]},
             "spread_does_not_establish": {"claims": [claim("D2", "Quotes are not fills.", ["E10"])]},
             "alpaca_blocked": {"claims": [claim("D3", "A1 and A2 open.", ["E13"], [{"fact": "alpaca.open_questions", "value": ["A1", "A2"]}])]}}}
    d.update(over)
    return d


def review_doc(snap, decision="accept", **over):
    d = {"task": "skeptical_review", "evidence_snapshot": snap, "author": "Claude (interactive Claude Code session)",
         "mode": "claude_code_session", "requested_actions": [], "summary": "SYNTHETIC review",
         "verdicts": [{"id": i, "verdict": "accept", "reason": "checked", "cites": ["E4"]} for i in ("S1", "S2", "D1", "D2", "D3")]
                     + [{"id": "DECISION", "verdict": decision, "reason": "SYNTHETIC reason", "cites": ["E13"]}]}
    d.update(over)
    return d


def tasks(st):
    return {t["task"]: t for t in st["tasks"]}


def test_full_workflow_transitions_and_report(root, store):
    r = c.start(store, root)
    wid = r["workflow_id"]
    st = c.status(store, wid)
    t = tasks(st)
    assert r["created"] and t["evidence"]["status"] == "completed" and len(t["evidence"]["evidence_refs"]) >= 16
    assert t["strategy_analysis"]["status"] == "blocked" and "UNAVAILABLE" in t["strategy_analysis"]["error"]
    assert t["skeptical_review"]["status"] == "blocked" and t["skeptical_review"]["error"].startswith("waiting")
    snap = store.get(t["evidence"]["id"])["outputs"]["snapshot"]
    c.submit(store, wid, "strategy_analysis", strategy_doc(snap), root)
    c.submit(store, wid, "data_cost_analysis", data_doc(snap), root)
    assert tasks(c.status(store, wid))["skeptical_review"]["error"].startswith("awaiting")
    st = c.submit(store, wid, "skeptical_review", review_doc(snap), root)
    t = tasks(st)
    assert st["status"] == "completed" and all(x["status"] == "completed" for x in t.values())
    assert t["strategy_analysis"]["mode"] == "claude_code_session" and t["strategy_analysis"]["evidence_refs"] == ["E4", "E8"]
    report = (root / t["coordinator_report"]["report_path"]).read_text(encoding="utf-8")
    for s in ("## 1.", "## 2.", "## 3.", "## 4.", "PROPOSAL ONLY", "UNAVAILABLE", "SYNTHETIC decision", "[E4]"):
        assert s in report
    assert "authorizes no strategy implementation" in report


def test_invalid_document_fails_then_new_attempt_recovers(root, store):
    wid = c.start(store, root)["workflow_id"]
    snap = store.get(tasks(c.status(store, wid))["evidence"]["id"])["outputs"]["snapshot"]
    bad = strategy_doc("stale-snapshot")
    bad["sections"]["why_001_failed"]["claims"][0]["figures"][0]["value"] = 0.05       # wrong figure
    bad["sections"]["why_002_failed"]["claims"][0]["cites"] = ["E99"]                  # unknown evidence
    bad["requested_actions"] = ["run_experiment"]                                       # prohibited
    st = c.submit(store, wid, "strategy_analysis", bad, root)
    t = tasks(st)["strategy_analysis"]
    assert t["status"] == "failed" and st["status"] == "blocked"
    for msg in ("not bound to this evidence snapshot", "does not match the evidence", "E99", "prohibited"):
        assert msg in t["error"]
    c.submit(store, wid, "data_cost_analysis", data_doc(snap), root)
    assert tasks(c.status(store, wid))["skeptical_review"]["error"].startswith("upstream failed")
    st = c.submit(store, wid, "strategy_analysis", strategy_doc(snap), root)            # corrected document
    t = tasks(st)["strategy_analysis"]
    assert t["status"] == "completed" and t["attempt"] == 2
    failed = store.db.execute("SELECT COUNT(*) FROM jobs WHERE worker='strategy_analysis' AND status='failed'").fetchone()[0]
    assert failed == 1                                                                   # the rejected attempt is kept


def test_duplicates_are_prevented(root, store):
    a = c.start(store, root)
    b = c.start(store, root)
    assert a["workflow_id"] == b["workflow_id"] and not b["created"]
    wid = a["workflow_id"]
    snap = store.get(tasks(c.status(store, wid))["evidence"]["id"])["outputs"]["snapshot"]
    bad = strategy_doc(snap, author="")
    c.submit(store, wid, "strategy_analysis", bad, root)
    rows = store.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    for _ in range(3):
        c.advance(store, wid, root)                         # same rejected document: no re-validation, no new rows
    assert store.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == rows
    c.submit(store, wid, "strategy_analysis", strategy_doc(snap), root)
    c.submit(store, wid, "data_cost_analysis", data_doc(snap), root)
    c.submit(store, wid, "skeptical_review", review_doc(snap), root)
    again = c.start(store, root)
    assert again["workflow_id"] == wid and not again["created"] and "exactly this evidence" in again["reason"]
    assert store.db.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0] == 1


def test_review_must_cover_every_claim_and_can_reject_the_decision(root, store):
    wid = c.start(store, root)["workflow_id"]
    snap = store.get(tasks(c.status(store, wid))["evidence"]["id"])["outputs"]["snapshot"]
    c.submit(store, wid, "strategy_analysis", strategy_doc(snap), root)
    c.submit(store, wid, "data_cost_analysis", data_doc(snap), root)
    partial = review_doc(snap)
    partial["verdicts"] = partial["verdicts"][:2]
    t = tasks(c.submit(store, wid, "skeptical_review", partial, root))["skeptical_review"]
    assert t["status"] == "failed" and "no verdict for" in t["error"]
    st = c.submit(store, wid, "skeptical_review", review_doc(snap, decision="reject"), root)
    report = (root / tasks(st)["coordinator_report"]["report_path"]).read_text(encoding="utf-8")
    assert "**REJECTED** by the skeptical review" in report and "**Recommended:**" not in report


def test_missing_evidence_fails_and_blocks_downstream(root, store):
    (root / "feasibility/spread_measurement/findings_pilot.json").unlink()
    st = c.status(store, c.start(store, root)["workflow_id"])
    t = tasks(st)
    assert t["evidence"]["status"] == "failed" and "findings_pilot.json" in t["evidence"]["error"]
    assert st["status"] == "failed"
    assert all(t[k]["status"] == "blocked" and "upstream failed" in t[k]["error"] for k in ("strategy_analysis", "data_cost_analysis"))


@pytest.mark.parametrize("action", sorted(c.PROHIBITED))
def test_prohibited_actions_are_refused(action):
    with pytest.raises(c.Refused):
        c.request_action(action)


def test_other_refusals(root, store):
    for path in ("data/monitoring/monitor.sqlite", "data/history/SPY/x.csv", "results/jobs/r.md",
                 "trading/alpaca_client.py", "research/../.env", "feasibility/validation_sessions.csv"):
        with pytest.raises(c.Refused):
            c.guard_path(path)
    wid = c.start(store, root)["workflow_id"]
    with pytest.raises(c.Refused):
        c.submit(store, wid, "coordinator_report", {}, root)            # deterministic tasks cannot be overridden
    snap = store.get(tasks(c.status(store, wid))["evidence"]["id"])["outputs"]["snapshot"]
    doc = strategy_doc(snap, mode="autonomous_agent")
    doc["sections"]["decision"]["is_proposal_only"] = False
    err = tasks(c.submit(store, wid, "strategy_analysis", doc, root))["strategy_analysis"]["error"]
    assert "unattended/autonomous model" in err and "is_proposal_only" in err


def test_workflow_store_is_separate_from_the_job_runner():
    assert c.DB_PATH != jobs.DB_PATH                     # the dashboard's JobRunner never sees workflow tasks
    assert c.UNATTENDED_MODEL["status"] == "UNAVAILABLE"
    src = Path(c.__file__).read_text(encoding="utf-8")
    assert "alpaca_client" not in src.split('"""', 2)[2] and "anthropic" not in src   # no broker or model client


def test_overview_is_read_only_when_no_workflow_exists(tmp_path):
    out = c.overview(tmp_path / "none.sqlite", tmp_path)
    assert out["workflows"] == [] and not (tmp_path / "none.sqlite").exists()


def test_workflows_endpoint_is_read_only(tmp_path, monkeypatch):
    import threading
    import urllib.request
    from trading.dashboard.server import DEFAULT_CONFIG, create_server
    monkeypatch.setattr(c, "DB_PATH", tmp_path / "none.sqlite")          # isolated: never the real workflow store
    httpd, _ctrl, stop = create_server(DEFAULT_CONFIG, 0, 3600, run_jobs=False, supervise_monitor=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_address[1]}/api/workflows", timeout=10) as r:
            body = json.loads(r.read())
        assert r.status == 200 and body["unattended_model"]["status"] == "UNAVAILABLE" and body["workflows"] == []
        assert not (tmp_path / "none.sqlite").exists()
    finally:
        stop.set(); httpd.shutdown(); httpd.server_close()
