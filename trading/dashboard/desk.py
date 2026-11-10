"""Research desk: the six departments of the city, mapped onto what is actually implemented.

Read-only. Every task state is derived from a stored record; when there is no record the state says so.
Nothing here runs a task, starts a process, calls a provider or touches broker code. The Command Centre is a
deterministic function over these records: it names the next eligible task (always one the owner runs by hand
from the command line) and why other work is blocked. It is not an agent loop and it cannot approve anything.

States: NOT IMPLEMENTED, DISABLED, IDLE, RUNNING, SUCCEEDED, REUSED, FAILED, BLOCKED, CLOSED, UNKNOWN.
A result produced earlier and still valid is SUCCEEDED (with its time), never RUNNING; a reused result is REUSED.

    build_desk(inputs, now)  pure function (tests feed synthetic inputs)
    collect(now)             gathers inputs from existing stores, then build_desk
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATES = ("NOT IMPLEMENTED", "DISABLED", "IDLE", "RUNNING", "SUCCEEDED", "REUSED", "FAILED", "BLOCKED", "CLOSED", "UNKNOWN")

DEPARTMENTS = [
    ("data", "Data Centre", "Collection, freshness, structural validation, missing-data classification, revisions, IEX/SIP comparison"),
    ("research", "Research Lab", "Approved specifications, chronological replay, cost assumptions, baselines, evaluation, critical review"),
    ("risk", "Risk Office", "Sizing, exposure, loss limits and halts: which are tested in simulation and which reach an execution path"),
    ("operations", "Operations", "Server and worker health, start-up, incidents, recovery, session completion, reliability evidence"),
    ("archive", "Evidence Archive", "Specifications, locks, journals, reports, provenance, reproducibility"),
    ("command", "Command Centre", "Deterministic coordinator: dependencies, blockers, current activity, next eligible task"),
]

# Department edges. "declared" = the code path exists (file named); an edge is drawn as RECORDED only when a
# stored task transition exists for it (the evidence trace), and that transition's id is attached.
DEPT_EDGES = [
    ("data", "operations", "reliability_assessment", "trading/monitor/evidence_trace.py: Data Centre outputs -> reliability assessment"),
    ("operations", "archive", "report_finalization", "trading/monitor/evidence_trace.py: assessment -> stored report check"),
    ("research", "archive", None, "research/*/runs, STATUS.json, workflows/*/REPORT.md (written by research code)"),
    ("research", "risk", None, "trading/backtest + trading/risk.py: limits applied inside simulated replay only"),
    ("data", "command", None, "trading/dashboard/desk.py reads the stores"),
    ("operations", "command", None, "trading/dashboard/desk.py reads the stores"),
    ("archive", "command", None, "trading/dashboard/desk.py reads the stores"),
    ("research", "command", None, "trading/dashboard/desk.py reads the stores"),
    ("risk", "command", None, "trading/dashboard/desk.py reads the stores"),
]

TRACE_STATE = {"SUCCEEDED": "SUCCEEDED", "REUSED": "REUSED", "FAILED": "FAILED", "BLOCKED": "BLOCKED", "RUNNING": "RUNNING",
               "QUEUED": "IDLE", "CANCELLED": "FAILED"}
DEPMAP_STATE = {"OK": "SUCCEEDED", "IDLE": "IDLE", "STALE": "FAILED", "FAILED": "FAILED", "UNKNOWN": "UNKNOWN",
                "DISABLED": "DISABLED", "CLOSED": "CLOSED", "NOT IMPLEMENTED": "NOT IMPLEMENTED"}
READINESS_STATE = {"PASS": "SUCCEEDED", "WARNING": "SUCCEEDED", "FAIL": "FAILED", "UNKNOWN": "UNKNOWN"}

# Model assistance that could later help. Each stays DISABLED (owner revoked paid calls on 2026-11-04).
MODEL_ASSIST = [
    {"id": "ma_unresolved_explainer", "department": "data", "title": "Draft explanations for unresolved comparison items",
     "input": "the stored unresolved-anomaly rows of one finalized session (q_compare, no prices beyond those rows)",
     "output": "a draft note per item, cited to row ids; never a category change",
     "evaluation": "owner reads each draft against the rows; deterministic categories stay authoritative",
     "cost_boundary": "one call per finalized session, owner-approved provider, model and budget; currently none"},
    {"id": "ma_independent_review", "department": "research", "title": "Independent review of a research workflow report",
     "input": "the evidence snapshot and submitted documents of one coordinator workflow",
     "output": "accept / challenge / reject per claim with citations, validated by trading/coordinator.py",
     "evaluation": "the coordinator's deterministic validation; disagreement is shown, never averaged into a consensus",
     "cost_boundary": "one call per workflow via trading.reviewer verify --i-authorize-one-paid-call; currently revoked"},
]


def _parse(ts):
    try:
        return datetime.fromisoformat(ts) if ts else None
    except (TypeError, ValueError):
        return None


def _age_s(ts, now):
    t = _parse(ts)
    return round((now - t).total_seconds()) if t else None


def _task(tid, dept, title, purpose, kind, handler, inputs, data_mode, state, *, latest=None, outcome=None,
          output=None, blocker=None, upstream=(), downstream=(), freshness=None, evidence=(), note=None, record=None,
          simulation_only=None, execution_path=None):
    assert state in STATES, state
    return {"id": tid, "department": dept, "title": title, "purpose": purpose, "kind": kind, "handler": handler,
            "inputs": list(inputs), "data_mode": data_mode, "freshness": freshness, "state": state,
            "latest_run_utc": latest, "outcome": outcome, "output": output, "blocker": blocker,
            "upstream": list(upstream), "downstream": list(downstream), "evidence": list(evidence), "note": note,
            "record": record, "simulation_only": simulation_only, "execution_path": execution_path}


def _trace_task(trace, name):
    if not trace:
        return None
    return next((t for t in trace["tasks"] if t["task"] == name), None)


def _from_trace(trace, name, tid, dept, title, purpose, handler, inputs, upstream, downstream, summary):
    t = _trace_task(trace, name)
    if t is None:
        return _task(tid, dept, title, purpose, "deterministic software", handler, inputs, "REAL monitoring records (stored)",
                     "IDLE", blocker="no evidence-trace run recorded yet", upstream=upstream, downstream=downstream,
                     note="run: python -m trading.monitor.evidence_trace run --date <finalized session>")
    state = TRACE_STATE.get(t["status"], "UNKNOWN")
    out = t.get("output") or {}
    return _task(tid, dept, title, purpose, "deterministic software", handler, inputs,
                 f"REAL monitoring records · session {trace['session_date']}", state,
                 latest=t.get("finished_utc") or t.get("started_utc"), outcome=summary(out) if out and state in ("SUCCEEDED", "REUSED") else None,
                 output=f"/api/desk?run={trace['run_id']}",
                 blocker=t.get("error") if state in ("BLOCKED", "FAILED") else None, upstream=upstream, downstream=downstream,
                 record={"task_record": t["id"], "run_id": trace["run_id"], "attempt": t["attempt"],
                         "reused_from": t.get("reused_from"), "output_fingerprint": t.get("output_fingerprint")},
                 note=("result reused from " + t["reused_from"]) if state == "REUSED" else None)


def _fmt_counts(d):
    return ", ".join(f"{k} {v}" for k, v in (d or {}).items())


# ------------------------------------------------------------------ departments

def data_centre(inp, now):
    nodes, rd, trace = inp.get("depmap_nodes", {}), inp.get("readiness", {}), inp.get("trace")
    w = nodes.get("monitor_worker", {})
    hb = rd.get("heartbeat", {})
    fresh = rd.get("latest_data", {})
    q = nodes.get("quality", {})
    worker_state = DEPMAP_STATE.get(w.get("status"), "UNKNOWN")
    if worker_state == "SUCCEEDED" and hb.get("status") == "PASS":
        worker_state = "RUNNING"                    # a continuous process with a current heartbeat record
    tasks = [
        _task("dc_collection", "data", "Live IEX bar collection", "Store each regular-session 1-minute IEX bar as received",
              "deterministic software (continuous worker process)", "trading/monitor/worker.py",
              ["Alpaca IEX bars (read-only GET)"], "REAL · live IEX · operational evidence, not a research dataset",
              worker_state, latest=hb.get("checked_utc"), outcome=hb.get("summary"),
              output="/api/monitor", blocker=None if worker_state == "RUNNING" else "; ".join(w.get("evidence", [])) or "no heartbeat record",
              upstream=["Alpaca IEX"], downstream=["dc_freshness", "dc_structural", "dc_iex_sip"],
              freshness=f"heartbeat record {_age_s(hb.get('checked_utc'), now)} s old" if hb else None, evidence=w.get("evidence", []),
              note="Owned by the existing worker; the desk never starts a second collector."),
        _task("dc_freshness", "data", "Freshness check", "Is the newest stored bar per symbol recent enough?",
              "deterministic software", "trading/monitor/readiness.py (check latest_data)", ["bars", "worker status"],
              "REAL monitoring records", READINESS_STATE.get(fresh.get("status"), "UNKNOWN"),
              latest=fresh.get("checked_utc"), outcome=fresh.get("summary"), output="/api/monitor/readiness",
              blocker=fresh.get("summary") if fresh.get("status") in ("FAIL", "UNKNOWN") else ("no stored readiness record" if not fresh else None),
              upstream=["dc_collection"], downstream=["op_health"],
              freshness=f"evaluated {_age_s(fresh.get('checked_utc'), now)} s ago" if fresh else "never evaluated"),
        _from_trace(trace, "structural_validation", "dc_structural", "data", "Structural validation",
                    "OHLC invariants, minute alignment, session bounds for every stored live bar",
                    "trading/monitor/quality.py: bar_defects (via evidence_trace)", ["bars"], ["dc_inventory"], ["op_reliability"],
                    lambda o: f"{o.get('bars_checked')} bars checked; defects {_fmt_counts(o.get('defects_per_symbol'))}"),
        _from_trace(trace, "capture_inventory", "dc_inventory", "data", "Capture inventory and missing minutes",
                    "Count received, on-time and late bars per symbol against the scheduled minutes",
                    "trading/monitor/evidence_trace.py: h_capture", ["bars", "m_workers"], ["dc_collection"],
                    ["dc_structural", "dc_iex_sip"],
                    lambda o: "; ".join(f"{s} {v['received']}/{o.get('scheduled_minutes')} received ({v['late']} late)"
                                        for s, v in (o.get("per_symbol") or {}).items())),
        _from_trace(trace, "iex_sip_comparison", "dc_iex_sip", "data", "IEX / delayed-SIP comparison (missing-data classes)",
                    "Classify each minute (consistent, expected coverage difference, both absent, unresolved anomaly...)",
                    "trading/monitor/quality.py: QualityChecker (results read from q_runs / q_compare)",
                    ["q_runs", "q_compare", "q_state"], ["dc_inventory"], ["dc_revisions", "op_reliability"],
                    lambda o: f"{o.get('runs_ok')}/{o.get('runs')} runs ok; {_fmt_counts(o.get('categories'))}"),
        _from_trace(trace, "revision_tracking", "dc_revisions", "data", "Revision tracking",
                    "Keep and count every later revision of an observation (never overwrite the live record)",
                    "trading/monitor/evidence_trace.py: h_revisions (q_obs revisions)", ["q_obs"], ["dc_iex_sip"], ["op_reliability"],
                    lambda o: f"{o.get('observations')} observations; later revisions {_fmt_counts(o.get('revisions_by_feed')) or 'none'}"),
        _task("dc_comparison_live", "data", "Continuous delayed-SIP comparison (inside the worker)",
              "Compare minutes once their end is >= 20 min old", "deterministic software (inside the worker)",
              "trading/monitor/quality.py", ["Alpaca SIP (15-min delayed)", "Alpaca IEX re-fetch", "bars"],
              "REAL · delayed SIP", "RUNNING" if q.get("status") == "OK" and worker_state == "RUNNING" else DEPMAP_STATE.get(q.get("status"), "UNKNOWN"),
              latest=None, outcome="; ".join(q.get("evidence", [])) or None, output="/api/monitor/quality",
              upstream=["dc_collection"], downstream=["dc_iex_sip"], evidence=q.get("evidence", [])),
    ]
    return tasks


def research_lab(inp, now):
    exps, wf, nodes = inp.get("experiments", []), inp.get("workflow"), inp.get("depmap_nodes", {})
    rep = nodes.get("report", {})
    closed = [e for e in exps if str(e.get("status", "")).startswith(("FAILED", "CLOSED"))]
    tasks = [
        _task("rl_specs", "research", "Approved strategy specifications", "Owner-approved SPEC.md before any code",
              "human decision (owner approves)", "research/<id>/SPEC.md + trading/experiment.py", ["owner decision"],
              "documents", "CLOSED" if exps and len(closed) == len(exps) else ("UNKNOWN" if not exps else "IDLE"),
              outcome="; ".join(f"{e['id']}: {e.get('status')}" for e in exps) or "no experiment records found",
              blocker="No approved active strategy. A new specification needs an owner decision; the desk cannot create one.",
              upstream=[], downstream=["rl_replay"], evidence=[e["path"] for e in exps]),
        _task("rl_replay", "research", "Chronological replay (development period)", "Replay saved development data bar by bar",
              "deterministic software", "trading/backtest/ + trading/evaluate.py", ["data/history (development period)"],
              "REAL historical development data (2016-2021); validation and final periods locked", "CLOSED",
              outcome="Experiments 001 and 002 were replayed and evaluated; both failed development rules.",
              blocker="No approved specification to replay.", upstream=["rl_specs"], downstream=["rl_evaluation"]),
        _task("rl_costs", "research", "Execution-cost assumptions", "Base and stress round-trip costs used in evaluation",
              "deterministic software", "trading/costs.py", ["cost model constants", "spread pilot (provisional)"],
              "model constants; pilot measurements PROVISIONAL", "BLOCKED",
              outcome="Base 2.3 bp / stress 6.6 bp round trip. Spread pilot: 6 calm sessions, provisional.",
              blocker="Quote semantics undocumented (Alpaca questions A1-A5 unanswered; the draft is unsent, owner's decision).",
              upstream=[], downstream=["rl_evaluation"], evidence=["feasibility/spread_measurement/FINDINGS_pilot.md"]),
        _task("rl_baselines", "research", "Baselines (random-entry screen)", "Compare a strategy with random entries paying the same costs",
              "deterministic software", "trading/evaluate.py", ["replay results"], "REAL historical development data", "CLOSED",
              outcome="001 at about the 10th percentile, 002 at the 83rd (95th required).", upstream=["rl_replay"], downstream=["rl_evaluation"]),
        _task("rl_evaluation", "research", "Evaluation against pre-declared rules", "Reconcile saved runs and recheck pass rules",
              "deterministic software", "trading/jobs.py (reconcile_report pipeline)", ["research/<id>/runs, STATUS.json"],
              "saved research artifacts", DEPMAP_STATE.get(rep.get("status"), "UNKNOWN") if rep else "UNKNOWN",
              latest=None, outcome="; ".join(rep.get("evidence", [])) or None, output="/api/jobs",
              upstream=["rl_replay", "rl_baselines", "rl_costs"], downstream=["rl_review", "ea_reports"]),
    ]
    if wf:
        st = {"completed": "SUCCEEDED", "failed": "FAILED", "blocked": "BLOCKED", "running": "RUNNING", "queued": "IDLE"}.get(wf["status"], "UNKNOWN")
        tasks.append(_task("rl_review", "research", "Critical review (strategy failure review)",
                           "Coordinator workflow: evidence, analyses, skeptical review, report", "deterministic coordinator + submitted documents",
                           "trading/coordinator.py", ["research artifacts E1-E18 (hashed)"], "saved research artifacts", st,
                           latest=wf.get("finished_utc"), outcome=f"workflow {wf['workflow_id']}: {wf['status']}",
                           output="/api/workflows", upstream=["rl_evaluation"], downstream=["ea_reports"],
                           note="The specialist documents were written in an interactive session and the review is a self-review, "
                                "not independent (stated in the report)."))
    else:
        tasks.append(_task("rl_review", "research", "Critical review (strategy failure review)", "Coordinator workflow",
                           "deterministic coordinator + submitted documents", "trading/coordinator.py", [], "saved research artifacts",
                           "IDLE", blocker="no workflow record", upstream=["rl_evaluation"], downstream=["ea_reports"]))
    tasks.append(_task("rl_gap_down", "research", "Gap-down opening candidate", "Deferred research candidate",
                       "human decision", "research/candidates/gap_down_opening/STATUS.json", ["Alpaca written answers A1-A5"],
                       "none (downloads blocked in trading/execution_feasibility.py)", "BLOCKED",
                       outcome=inp.get("gap_down_status") or "UNKNOWN",
                       blocker="DEFERRED_DATA_SEMANTICS: needs written Alpaca answers and a new owner decision.", upstream=[], downstream=[]))
    return tasks


def risk_office(inp, now):
    ops = inp.get("operations") or {}
    gate = ops.get("order_gate") or {}
    ks = ops.get("kill_switch") or {}
    sim = "Tested in simulation (trading/backtest, tests/test_risk.py); connected to an execution path: NO (no order code exists)."
    common = dict(simulation_only=True, execution_path="none")
    return [
        _task("ro_sizing", "risk", "Position sizing (0.10% risk per trade incl. costs)", "Size simulated positions from the owner baseline",
              "deterministic software", "trading/risk.py (OWNER_BASELINE_2026_11_03)", ["simulated equity", "stop distance", "costs"],
              "simulation only", "IDLE", outcome=sim, upstream=["rl_specs"], downstream=[], **common),
        _task("ro_exposure", "risk", "Exposure limits (5% per position, 10% gross, 2 positions, no leverage)",
              "Reject simulated entries beyond the limits", "deterministic software", "trading/risk.py", ["simulated positions"],
              "simulation only", "IDLE", outcome=sim, upstream=["rl_specs"], downstream=[], **common),
        _task("ro_loss_halt", "risk", "Daily loss limit (0.50%) and drawdown halt (3%)", "Halt simulated trading after the limits",
              "deterministic software", "trading/risk.py + trading/backtest", ["simulated P&L"], "simulation only", "IDLE",
              outcome=sim, upstream=["rl_specs"], downstream=[], **common),
        _task("ro_order_gate", "risk", "Order-submission gate", "Block any order unless TRADING_MODE=paper and ORDER_SUBMISSION_ENABLED=true",
              "deterministic software", "trading/safety.py: require_order_submission_allowed", ["environment"],
              "configuration", "DISABLED" if gate.get("enabled") is False else ("UNKNOWN" if not gate else "FAILED"),
              outcome=f"order submission enabled: {gate.get('enabled')}" if gate else "no operations record",
              blocker="Order submission is not authorized (owner milestone required). No order code exists for it to protect.",
              upstream=[], downstream=[], simulation_only=False, execution_path="none (gate exists, nothing calls it)"),
        _task("ro_dry_run_gate", "risk", "Dry-run entry gate", "Record each decision minute; always deny entries in DRY_RUN",
              "deterministic software", "trading/operations/gate.py", ["approved strategies (empty)", "kill switch"],
              "DRY_RUN", "IDLE" if ops else "UNKNOWN", outcome=f"{ops.get('approved_strategy', 'UNKNOWN')}; kill switch "
              f"{'ON' if ks.get('on') else 'off' if ks else 'UNKNOWN'}", upstream=["op_dry_run"], downstream=[],
              simulation_only=False, execution_path="none (always denies)"),
        _task("ro_reconciliation", "risk", "Broker position reconciliation", "Compare intended and broker positions",
              "deterministic software (not written)", "NOT IMPLEMENTED", [], "none", "NOT IMPLEMENTED",
              blocker="Order submission disabled; nothing to reconcile.", upstream=[], downstream=[]),
    ]


def operations_dept(inp, now):
    rd, ops, trace, rel = inp.get("readiness", {}), inp.get("operations") or {}, inp.get("trace"), inp.get("reliability") or {}
    nodes = inp.get("depmap_nodes", {})
    sv = nodes.get("supervisor", {})
    inc = inp.get("incidents", [])
    open_inc = [i for i in inc if i.get("state") != "resolved"]
    runner_rd = rd.get("runner", {})
    run = ops.get("runner") or {}
    today = now.date().isoformat()
    store_today = run.get("session_date") == today or (run.get("started_utc") or "").startswith(today)
    status_file = inp.get("runner_status") or {}
    discrepancy = None
    if ops.get("records_visible") is False:            # confirmed cause: app-container private copy (paths.view_redirected)
        discrepancy = ops.get("note")
    elif status_file.get("session_date") == today and not store_today:
        discrepancy = (f"runner status file shows run {status_file.get('run_id')} for {today} with heartbeat "
                       f"{status_file.get('heartbeat_utc')}, but the operations store has no run record for {today} "
                       f"(latest {run.get('run_id')}). Acceptance can only count stored records; investigate after the close.")
    dry_state = ("FAILED" if discrepancy else "RUNNING" if run.get("alive") else "IDLE") if ops else "UNKNOWN"
    tasks = [
        _task("op_health", "operations", "Server and worker health checks", "Deterministic readiness checks over real records",
              "deterministic software", "trading/monitor/readiness.py", ["processes", "heartbeat", "store", "calendar", "disk"],
              "REAL records", "FAILED" if any(c.get("status") == "FAIL" for c in rd.values()) else ("SUCCEEDED" if rd else "UNKNOWN"),
              latest=max((c.get("checked_utc") or "" for c in rd.values()), default=None) or None,
              outcome="; ".join(f"{k} {v.get('status')}" for k, v in rd.items()) or "no stored readiness record",
              output="/api/monitor/readiness", upstream=["dc_collection", "dc_freshness"], downstream=["op_incidents"],
              note=("WARNING: " + rd["code_version"]["summary"]) if rd.get("code_version", {}).get("status") == "WARNING" else None),
        _task("op_supervision", "operations", "Worker supervision and recovery", "Relaunch a crashed worker (max 6 per hour)",
              "deterministic software (inside the city server)", "trading/monitor/control.py", ["worker heartbeat"],
              "REAL records", DEPMAP_STATE.get(sv.get("status"), "UNKNOWN"), outcome="; ".join(sv.get("evidence", [])) or None,
              upstream=["op_health"], downstream=["dc_collection"]),
        _task("op_incidents", "operations", "Incidents", "Open, observe and resolve incidents from failed checks",
              "deterministic software", "trading/monitor/readiness.py (incidents)", ["readiness checks"], "REAL records",
              "FAILED" if open_inc else "IDLE", outcome=f"{len(open_inc)} open, {len(inc) - len(open_inc)} resolved (recent)",
              blocker="; ".join(f"#{i['id']} {i['kind']}" for i in open_inc) or None, upstream=["op_health"], downstream=[],
              evidence=[f"#{i['id']} {i['kind']} {i['state']} opened {i.get('opened_utc')}" for i in inc[:5]]),
        _task("op_startup", "operations", "Daily start-up", "Reuse healthy processes; never kill or restart",
              "deterministic software, started by the owner", "trading/startup.py", ["process table", "records"], "REAL records",
              "SUCCEEDED" if inp.get("server_run") else "UNKNOWN", latest=(inp.get("server_run") or {}).get("started_utc"),
              outcome=f"city server pid {(inp.get('server_run') or {}).get('pid')} started {(inp.get('server_run') or {}).get('started_utc')}"
              if inp.get("server_run") else "no server run record", upstream=[], downstream=["op_health"]),
        _task("op_dry_run", "operations", "Automatic session dry run (Milestone 1)", "Record every decision minute; entries always denied",
              "deterministic software, started by the owner", "trading/operations/runner.py", ["calendar", "monitoring health", "approvals (empty)"],
              "DRY_RUN · no orders", dry_state, latest=run.get("started_utc"),
              outcome=(f"readiness check: {runner_rd.get('summary')}" if runner_rd else None),
              blocker=discrepancy, upstream=["op_health"], downstream=["ro_dry_run_gate", "op_acceptance"],
              record={"store_latest_run": run.get("run_id"), "status_file_run": status_file.get("run_id")}),
        _task("op_acceptance", "operations", "Dry-run acceptance (5 consecutive PASS sessions)", "Classify each session from stored records",
              "deterministic software", "trading/operations/report.py", ["operations store"], "REAL records",
              "UNKNOWN" if ops.get("records_visible") is False else "IDLE" if ops else "UNKNOWN",
              blocker=ops.get("note") if ops.get("records_visible") is False else None,
              outcome=f"streak {(ops.get('acceptance') or {}).get('current_streak')} of {(ops.get('acceptance') or {}).get('required_consecutive_passes')}; "
                      + "; ".join(f"{s['session_date']} {s['classification']}" for s in (ops.get("acceptance") or {}).get("sessions", [])),
              upstream=["op_dry_run"], downstream=[]),
        _task("op_report_completion", "operations", "Session report completion (existing criterion)",
              "5 consecutive sessions FINALIZED or INCOMPLETE with a reason (docs/MONITORING.md)", "deterministic software",
              "trading/monitor/readiness.py: reliability_summary", ["stored daily reports"], "REAL records",
              "SUCCEEDED" if rel.get("current_consecutive", 0) >= rel.get("target", 5) else ("IDLE" if rel else "UNKNOWN"),
              outcome=f"{rel.get('current_consecutive')} of {rel.get('target')} consecutive" if rel else None,
              blocker=rel.get("gap"), upstream=["ea_reports"], downstream=["op_gate"]),
        _from_trace(trace, "reliability_assessment", "op_reliability", "operations", "Reliability assessment (one session)",
                    "Existing daily evidence report recomputed from stored records, checked against the capture inventory",
                    "trading/monitor/reliability.py: daily_report (via evidence_trace)", ["all Data Centre outputs"],
                    ["dc_structural", "dc_iex_sip", "dc_revisions"], ["ea_reports"],
                    lambda o: (f"{o.get('report_state')}; on time {_fmt_counts(o.get('on_time_by_symbol'))}; late "
                               f"{_fmt_counts(o.get('late_by_symbol'))}; unplanned downtime {o.get('unplanned_downtime_minutes')} min")),
        _task("op_gate", "operations", "Reliability gate G1-G4", "Capture-quality thresholds before monitoring can count as reliable",
              "human decision (owner approval), then deterministic software", "NOT IMPLEMENTED (docs/RELIABILITY_GATE_PROPOSAL.md)",
              ["reliability assessments"], "none", "NOT IMPLEMENTED",
              blocker="PROPOSED, not active: awaiting the owner's approval. No threshold is applied anywhere.",
              upstream=["op_reliability", "op_report_completion"], downstream=[]),
    ]
    return tasks


def archive(inp, now):
    exps, trace, nodes = inp.get("experiments", []), inp.get("trace"), inp.get("depmap_nodes", {})
    hist = nodes.get("history", {})
    locks = inp.get("locks", [])
    tasks = [
        _task("ea_locks", "archive", "Specifications and experiment locks", "Fingerprinted specs, costs, periods, budget, limits",
              "deterministic software", "trading/experiment_lock.py", ["SPEC.md", "EXPERIMENT_LOCK.json"], "documents",
              "FAILED" if any(not l.get("ok") for l in locks) else ("SUCCEEDED" if locks else "UNKNOWN"),
              latest=now.isoformat(timespec="seconds") if locks else None,
              outcome="; ".join(f"{l['id']}: {l['result']}" for l in locks) or "no lock checked",
              upstream=["rl_specs"], downstream=[], note="Checked when this view was built; locks are never edited here."),
        _task("ea_journals", "archive", "Journals and attempt logs", "Append-only attempt and inspection logs",
              "deterministic software (append-only writers)", "trading/experiment.py, trading/research_run.py",
              ["experiment runs"], "documents", "SUCCEEDED" if inp.get("journals") else "UNKNOWN",
              outcome="; ".join(f"{j['path']}: {j['rows']} rows" for j in inp.get("journals", [])), upstream=[], downstream=[]),
        _from_trace(trace, "report_finalization", "ea_reports", "archive", "Daily evidence reports (finalized, amend-only)",
                    "Stored report versions: integrity of each stored hash, and whether today's code reproduces it",
                    "trading/monitor/evidence_trace.py: h_report over q_reports", ["q_reports", "q_report_corrections"],
                    ["op_reliability"], ["op_report_completion"],
                    lambda o: (f"v{o.get('latest_version')} {o.get('latest_status')}; {o.get('integrity')}; {o.get('reproduction')}"
                               + (f" ({', '.join(f'{k} {v}' for k, v in (o.get('difference_counts') or {}).items())})"
                                  if o.get("difference_counts") else "")
                               + (f"; pending amend-only correction: {len(o['pending_correction'])}" if o.get("pending_correction") else ""))),
        _task("ea_provenance", "archive", "Data provenance", "Manifests recording source, feed, adjustment and retrieval time",
              "deterministic software", "trading/history.py (manifest.json)", ["data/history"], "REAL historical (development)",
              DEPMAP_STATE.get(hist.get("status"), "UNKNOWN"), outcome="; ".join(hist.get("evidence", [])) or None,
              upstream=[], downstream=["rl_replay"]),
        _task("ea_workflow_reports", "archive", "Research workflow reports", "Hashed evidence snapshots and reports",
              "deterministic software", "trading/coordinator.py", ["research artifacts"], "documents",
              "SUCCEEDED" if inp.get("workflow") and inp["workflow"].get("status") == "completed" else "IDLE",
              outcome=(inp.get("workflow") or {}).get("workflow_id"), upstream=["rl_review"], downstream=[]),
    ]
    return tasks


# ------------------------------------------------------------------ Command Centre

def command_centre(depts: dict, inp: dict, now: datetime) -> dict:
    """Deterministic next eligible task. Candidates are only existing, authorized, manual commands."""
    all_tasks = [t for d in depts.values() for t in d]
    failed = [t for t in all_tasks if t["state"] == "FAILED"]
    blocked = [t for t in all_tasks if t["state"] == "BLOCKED"]
    finalized = inp.get("finalized_sessions", [])
    traced = {r["session_date"]: r for r in inp.get("trace_runs", []) if r["status"] == "COMPLETED"}
    untraced = [d for d in finalized if d not in traced]
    activity = [{"task": t["id"], "title": t["title"], "since": t["latest_run_utc"]} for t in all_tasks if t["state"] == "RUNNING"]
    candidates = []
    for t in failed:
        candidates.append({"task": t["id"], "action": "investigate (owner)", "why": t["blocker"] or t["outcome"] or "failed record",
                           "command": None, "rank": 1})
    for d in untraced:
        candidates.append({"task": "evidence_trace", "action": f"trace finalized session {d}",
                           "why": "finalized report exists but no completed evidence-trace run",
                           "command": f"python -m trading.monitor.evidence_trace run --date {d}", "rank": 2})
    nxt = sorted(candidates, key=lambda c: c["rank"])[0] if candidates else None
    prohibited = [
        "create or approve a strategy", "relax risk limits", "reopen closed experiments", "access validation or final data",
        "enable broker order submission", "purchase data or make paid model calls", "install external integrations",
    ]
    return {"next_eligible": nxt, "candidates": candidates, "current_activity": activity,
            "blocked": [{"task": t["id"], "title": t["title"], "why": t["blocker"]} for t in blocked],
            "failed": [{"task": t["id"], "title": t["title"], "why": t["blocker"] or t["outcome"]} for t in failed],
            "not_implemented": [{"task": t["id"], "title": t["title"]} for t in all_tasks if t["state"] == "NOT IMPLEMENTED"],
            "untraced_finalized_sessions": untraced, "prohibited": prohibited,
            "boundary": "Deterministic function over stored records. It runs nothing; every action is a manual command the owner runs."}


def build_desk(inp: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    depts = {"data": data_centre(inp, now), "research": research_lab(inp, now), "risk": risk_office(inp, now),
             "operations": operations_dept(inp, now), "archive": archive(inp, now)}
    cc = command_centre(depts, inp, now)
    cmd_tasks = [_task("cc_coordinator", "command", "Next eligible task", "Explain dependencies, blockers and the next manual step",
                       "deterministic software", "trading/dashboard/desk.py: command_centre", ["all department records"],
                       "REAL records", "SUCCEEDED", latest=now.isoformat(timespec="seconds"),
                       outcome=(cc["next_eligible"]["action"] if cc["next_eligible"] else "nothing eligible"), output="/api/desk")]
    cmd_tasks += [_task(m["id"], m["department"], m["title"], m["output"], "optional model-assisted task",
                        "NOT CONNECTED", [m["input"]], "none", "DISABLED",
                        blocker="Paid model calls revoked by the owner on 2026-11-04; needs a new explicit authorization.",
                        note=f"Evaluation: {m['evaluation']}. Cost boundary: {m['cost_boundary']}.") for m in MODEL_ASSIST]
    for t in cmd_tasks[1:]:
        depts[t["department"]].append(t)
    depts["command"] = cmd_tasks[:1]
    out_depts = []
    for did, name, scope in DEPARTMENTS:
        ts = depts[did]
        counts = {s: sum(1 for t in ts if t["state"] == s) for s in STATES if any(t["state"] == s for t in ts)}
        worst = next((s for s in ("FAILED", "BLOCKED", "UNKNOWN") if counts.get(s)), None)
        out_depts.append({"id": did, "name": name, "scope": scope, "counts": counts,
                          "headline": worst or ("RUNNING" if counts.get("RUNNING") else
                                                "SUCCEEDED" if counts.get("SUCCEEDED") or counts.get("REUSED") else "IDLE"),
                          "tasks": ts})
    trace = inp.get("trace")
    edges = []
    for a, b, task, decl in DEPT_EDGES:
        t = _trace_task(trace, task) if task else None
        edges.append({"from": a, "to": b, "declared": decl, "recorded": bool(t and t["status"] in ("SUCCEEDED", "REUSED", "FAILED")),
                      "event_id": f"{t['id']}:{t['status']}" if t else None, "event_status": t["status"] if t else None})
    return {"label": "RESEARCH DESK · real records · read-only · no orders exist · paid model calls disabled",
            "generated_utc": now.isoformat(timespec="seconds"), "departments": out_depts, "edges": edges, "command_centre": cc,
            "trace": trace, "trace_runs": [{k: r[k] for k in ("run_id", "session_date", "status", "created_utc", "finished_utc")}
                                           for r in inp.get("trace_runs", [])],
            "model_assist": MODEL_ASSIST, "states": STATES, "input_errors": inp.get("errors", [])}


# ------------------------------------------------------------------ collection (read-only)

def _rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]


def collect(now: datetime | None = None, desk_db: Path | None = None, trace_run: str | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    inp: dict = {"errors": []}

    def guard(name, fn):
        try:
            fn()
        except Exception as exc:                       # a missing source becomes UNKNOWN, visibly
            inp["errors"].append(f"{name}: {type(exc).__name__}: {exc}"[:300])

    def depmap_part():
        from trading.dashboard import depmap
        inp["depmap_nodes"] = {n["id"]: n for n in depmap.collect(now=now)["nodes"]}

    def monitor_part():
        from trading.monitor import evidence_trace as et, readiness
        db = et.open_monitor_readonly()
        try:
            inp["readiness"] = {r["check_id"]: r for r in _rows(db, "SELECT check_id, status, summary, checked_utc, changed_utc FROM readiness")}
            inp["incidents"] = _rows(db, "SELECT id, kind, state, opened_utc, resolved_utc FROM incidents ORDER BY id DESC LIMIT 20")
            sr = _rows(db, "SELECT pid, port, started_utc, last_alive_utc, stopped_utc FROM server_runs ORDER BY id DESC LIMIT 1")
            inp["server_run"] = sr[0] if sr else None
            inp["finalized_sessions"] = [r["session_date"] for r in _rows(db, "SELECT session_date FROM q_state WHERE status='finalized' ORDER BY session_date")]
            from trading.monitor import store as mst
            store = mst.MonitorStore.__new__(mst.MonitorStore)
            store.db = db
            rel = readiness.reliability_summary(store, now)
            inp["reliability"] = {k: rel.get(k) for k in ("target", "current_consecutive", "best_consecutive", "gap", "reliability_gate")}
        finally:
            db.close()

    def trace_part():
        from trading.monitor import evidence_trace as et
        runs = et.recent_runs(desk_db)
        inp["trace_runs"] = runs
        chosen = next((r for r in runs if r["run_id"] == trace_run), None) if trace_run else None
        inp["trace"] = chosen or next((r for r in runs if r["status"] == "COMPLETED"), runs[0] if runs else None)

    def ops_part():
        from trading.operations import paths, progress, snapshot
        inp["operations"] = snapshot.collect()
        inp["runner_status"] = progress.read(paths.runtime_dir() / progress.STATUS_NAME)

    def research_part():
        exps = []
        for d in sorted((PROJECT_ROOT / "research").glob("0*_*/STATUS.json")):
            s = json.loads(d.read_text(encoding="utf-8"))
            exps.append({"id": d.parent.name, "status": s.get("status") or s.get("state"), "path": str(d.relative_to(PROJECT_ROOT)).replace("\\", "/")})
        inp["experiments"] = exps
        g = PROJECT_ROOT / "research" / "candidates" / "gap_down_opening" / "STATUS.json"
        if g.is_file():
            inp["gap_down_status"] = json.loads(g.read_text(encoding="utf-8")).get("status")
        journals = []
        for p in sorted((PROJECT_ROOT / "research").glob("0*_*/*.csv")):
            with p.open(encoding="utf-8") as f:
                journals.append({"path": str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"), "rows": max(0, sum(1 for _ in f) - 1)})
        inp["journals"] = journals
        from trading import coordinator
        wfs = coordinator.overview().get("workflows", [])
        inp["workflow"] = {k: wfs[0].get(k) for k in ("workflow_id", "status", "finished_utc")} if wfs else None

    def locks_part():
        from trading import experiment_lock
        locks = []
        try:
            lk = experiment_lock.check_lock()
            locks.append({"id": "001_intraday_momentum", "ok": True, "result": f"matches lock {lk.get('experiment_id', '')[:16]}"})
        except experiment_lock.LockMismatch as exc:
            locks.append({"id": "001_intraday_momentum", "ok": False, "result": str(exc)[:200]})
        p2 = PROJECT_ROOT / "research" / "002_opening_range_breakout" / "EXPERIMENT_LOCK.json"
        locks.append({"id": "002_opening_range_breakout", "ok": p2.is_file(),
                      "result": "lock file present (content not re-verified here)" if p2.is_file() else "lock file missing"})
        inp["locks"] = locks

    for name, fn in (("depmap", depmap_part), ("monitor", monitor_part), ("trace", trace_part), ("operations", ops_part),
                     ("research", research_part), ("locks", locks_part)):
        guard(name, fn)
    return build_desk(inp, now)
