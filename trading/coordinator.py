"""Coordinator workflow for research questions (the first "JARVIS-managed" workflow).

One workflow is implemented: `strategy_failure_review`
    "Review our existing strategy failures and recommend the next research decision."

How it works (and what it is not):
* It reuses the research-job system's store (`trading.jobs.JobStore`: states, the one-completed-
  job-per-input index, the job/pipeline schema) in a separate database, `data/jobs/workflows.sqlite`,
  so the dashboard's job runner never picks these tasks up.
* Tasks:
    evidence            deterministic code: reads an allowlist of saved files, hashes them, extracts facts
    strategy_analysis   SPECIALIST ROLE filled by a submitted document
    data_cost_analysis  SPECIALIST ROLE filled by a submitted document
    skeptical_review    SPECIALIST ROLE filled by a submitted document, plus deterministic cross-checks
    coordinator_report  deterministic code: assembles the final report only from validated tasks
* A specialist role is NOT an independently running agent. There is no unattended model connection
  in this project (the paid reviewer is OPTIONAL / DISABLED by the owner), so every specialist
  document must be submitted explicitly and is recorded with its author and mode, for example an
  interactive Claude Code session. The coordinator validates; it never writes analysis itself.
* Read-only research: no experiment is run, no data is downloaded, no data/ or monitoring file is
  read, no lock, risk limit or acceptance rule is touched, and prohibited actions are refused.

CLI:
    python -m trading.coordinator start           # create (or reuse) the workflow; runs evidence collection
    python -m trading.coordinator submit <workflow_id> <task> <file.json>
    python -m trading.coordinator advance <workflow_id>
    python -m trading.coordinator status [<workflow_id>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from trading.jobs import JobStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "jobs" / "workflows.sqlite"
WORKFLOW = "strategy_failure_review"
QUESTION = "Review our existing strategy failures and recommend the next research decision."
SUBMISSIONS = "research/workflows"            # relative to the project root: <id>/<task>.json and REPORT.md

UNATTENDED_MODEL = {
    "status": "UNAVAILABLE",
    "reason": ("No authorized unattended model connection exists. The paid model reviewer is OPTIONAL / "
               "DISABLED (owner revoked paid calls on 2026-11-04) and no other model access is configured. "
               "Specialist roles are filled by explicitly submitted documents, recorded with their author "
               "and mode (for example an interactive Claude Code session)."),
}

# (task, kind, role, depends on, completion criteria)
TASKS = [
    ("evidence", "deterministic", "Evidence clerk (code)", [],
     "Every required evidence file exists inside the allowed roots, is hashed, and the core facts are "
     "extracted; no prohibited path is read."),
    ("strategy_analysis", "specialist", "Strategy analyst (role)", ["evidence"],
     "A submitted document bound to this evidence snapshot with sections why_001_failed, why_002_failed and "
     "decision; every claim cites existing evidence ids; every quoted figure matches an extracted fact; "
     "requested actions only from the allowed list."),
    ("data_cost_analysis", "specialist", "Data and cost analyst (role)", ["evidence"],
     "A submitted document bound to this evidence snapshot with sections spread_establishes, "
     "spread_does_not_establish and alpaca_blocked; every claim cites evidence; figures match facts; "
     "allowed actions only."),
    ("skeptical_review", "specialist", "Skeptical reviewer (role)", ["strategy_analysis", "data_cost_analysis"],
     "A submitted review bound to this evidence snapshot giving a verdict (accept, challenge or reject) "
     "with a reason for every claim of both analyses and for the decision; deterministic cross-checks pass."),
    ("coordinator_report", "deterministic", "Coordinator (code)", ["strategy_analysis", "data_cost_analysis", "skeptical_review"],
     "REPORT.md written from validated tasks only, with all four required sections; a decision rejected "
     "by the review is not presented as the recommendation."),
]
ORDER = [t[0] for t in TASKS]
SPEC = {t[0]: t for t in TASKS}

# Evidence allowlist (id, path relative to project root, role, required). Nothing under data/ or results/.
EVIDENCE = [
    ("E1", "research/001_intraday_momentum/SPEC.md", "001 specification", True),
    ("E2", "research/001_intraday_momentum/STATUS.json", "001 status (closed)", True),
    ("E3", "research/001_intraday_momentum/RESULTS_development.md", "001 development results and diagnosis", True),
    ("E4", "research/001_intraday_momentum/runs/{run001}.json", "001 recorded run (metrics, rules)", True),
    ("E5", "research/002_opening_range_breakout/SPEC.md", "002 specification", True),
    ("E6", "research/002_opening_range_breakout/STATUS.json", "002 status (closed)", True),
    ("E7", "research/002_opening_range_breakout/RESULTS_development.md", "002 development results", True),
    ("E8", "research/002_opening_range_breakout/runs/{run002}.json", "002 recorded run (metrics, rules)", True),
    ("E9", "trading/costs.py", "cost assumptions (base, stress, severe)", True),
    ("E10", "feasibility/spread_measurement/FINDINGS_pilot.md", "spread pilot findings (provisional)", True),
    ("E11", "feasibility/spread_measurement/findings_pilot.json", "spread pilot statistics", True),
    ("E12", "feasibility/spread_measurement/PLAN.md", "spread pilot pre-registration", True),
    ("E13", "feasibility/execution_data/ALPACA_SUPPORT_REQUEST_DRAFT.md", "open Alpaca data questions (A1-A5)", True),
    ("E14", "research/candidates/gap_down_opening/STATUS.json", "deferred candidate status", True),
    ("E15", "research/FEASIBILITY_gap_down_opening.md", "gap-down feasibility note", True),
    ("E16", "research/NEXT_HYPOTHESES.md", "earlier candidate list", True),
    ("E17", "research/EXPLORATION_LOG.md", "exploration / contamination ledger", True),
    ("E18", "research/FAILURE_COMPARISON_001_002.md", "plain-English failure comparison", False),
]
ALLOWED_ROOTS = ("research/", "feasibility/", "trading/costs.py")

# Actions a submitted document may request (all are owner decisions or no-ops) ...
ALLOWED_REQUESTS = {"owner_decision", "owner_sends_support_request", "pre_register_measurement_plan",
                    "no_action"}
# ... and actions the coordinator always refuses, whoever asks.
PROHIBITED = {"place_order", "submit_order", "paper_order", "live_order", "run_experiment", "evaluate_strategy",
              "implement_strategy", "reopen_experiment", "fetch_market_data", "download_data",
              "read_validation_data", "read_final_data", "use_monitoring_data", "change_risk_limits",
              "change_experiment_lock", "change_acceptance_rules", "paid_model_call", "purchase",
              "restart_monitoring", "interrupt_dry_run"}

REQUIRED_SECTIONS = {
    "strategy_analysis": ("why_001_failed", "why_002_failed", "decision"),
    "data_cost_analysis": ("spread_establishes", "spread_does_not_establish", "alpaca_blocked"),
}


class Refused(Exception):
    """A prohibited action or path was requested; nothing was done."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def guard_path(rel: str) -> str:
    """Allow only the evidence roots; refuse data/, results/, monitoring and held-out paths."""
    r = rel.replace("\\", "/")
    if ".." in r.split("/") or r.startswith("/") or ":" in r:
        raise Refused(f"path outside the project evidence roots: {rel}")
    parts = r.lower().split("/")
    if (parts[0] in ("data", "results") or any("monitor" in x for x in parts)
            or any(x.startswith(("validation", "final", ".env", "secret")) for x in parts)):
        raise Refused(f"prohibited evidence path (data, monitoring, held-out or secret): {rel}")
    if not any(r == a or r.startswith(a) for a in ALLOWED_ROOTS):
        raise Refused(f"path not in the evidence allowlist roots {ALLOWED_ROOTS}: {rel}")
    return r


def request_action(action: str) -> str:
    """The only entry point for side effects named by documents or users. Prohibited ones are refused."""
    if action in PROHIBITED:
        raise Refused(f"refused: '{action}' is prohibited for research workflows (no orders, runs, downloads, "
                      "held-out or monitoring data, lock/risk/rule changes, paid calls or purchases)")
    if action not in ALLOWED_REQUESTS:
        raise Refused(f"refused: '{action}' is not an allowed workflow request")
    return f"recorded for the owner: {action} (the coordinator performs nothing on its own)"


# ------------------------------------------------------------------ evidence (deterministic)

def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def collect_evidence(root: Path = PROJECT_ROOT) -> dict:
    """Hash the allowlisted files and extract facts. Raises with a list of what is missing."""
    s1 = _read_json(root / "research/001_intraday_momentum/STATUS.json")
    s2 = _read_json(root / "research/002_opening_range_breakout/STATUS.json")
    runs = {"run001": s1.get("development_run_id"), "run002": s2.get("development_run_id")}
    items, missing = [], []
    for eid, pattern, role, required in EVIDENCE:
        rel = guard_path(pattern.format(**runs))
        p = root / rel
        if not p.is_file():
            (missing if required else items).append(rel if required else
                                                    {"id": eid, "path": rel, "role": role, "present": False})
            continue
        data = p.read_bytes()
        items.append({"id": eid, "path": rel, "role": role, "present": True, "bytes": len(data), "sha256": _sha(data)})
    if missing:
        raise FileNotFoundError(f"required evidence missing: {missing}")
    by = {i["id"]: root / i["path"] for i in items if i.get("present")}
    r1, r2 = _read_json(by["E4"]), _read_json(by["E8"])
    facts: dict[str, dict] = {}

    def fact(key, value, eid):
        facts[key] = {"value": value, "evidence": eid}

    fact("001.state", s1.get("state"), "E2"); fact("001.failed_rules", s1.get("failed_rules"), "E2")
    fact("001.base_net_return", r1["results_by_cost"]["base"]["net_return"], "E4")
    fact("001.stress_net_return", r1["results_by_cost"]["stress"]["net_return"], "E4")
    fact("001.random_percentile", r1["random_direction"]["strategy_percentile"], "E4")
    fact("002.state", s2.get("state"), "E6"); fact("002.failed_rules", s2.get("failed_rules"), "E6")
    fact("002.base_net_return", r2["primary"]["base"]["net_return"], "E8")
    fact("002.stress_net_return", r2["primary"]["stress"]["net_return"], "E8")
    fact("002.base_gross_pnl", r2["primary"]["base"]["gross_pnl"], "E8")
    fact("002.base_trades", r2["primary"]["base"]["trades"], "E8")
    fact("002.b1_percentile", r2["diagnostics"]["B1"][sorted(r2["diagnostics"]["B1"])[0]]["strategy_percentile"], "E8")
    from trading import costs
    base = costs.BASE
    fact("cost.base_half_spread_bp", base.half_spread_bp, "E9")
    fact("cost.base_slippage_bp", base.slippage_bp, "E9")
    fact("cost.base_round_trip_bp", round(2 * base.per_side_bp + base.sell_fee_bp, 4), "E9")
    fact("cost.stress_round_trip_bp", round(2 * costs.STRESS.per_side_bp + costs.STRESS.sell_fee_bp, 4), "E9")
    pil = _read_json(by["E11"])
    hs = [d["half_spread_bp"] for g in pil["groups"].values() for d in g.get("by_date", {}).values()
          if d.get("half_spread_bp") is not None]
    fact("pilot.half_spread_bp_min", min(hs), "E11"); fact("pilot.half_spread_bp_max", max(hs), "E11")
    fact("pilot.dates", len({dt for g in pil["groups"].values() for dt in g.get("by_date", {})}), "E11")
    draft = by["E13"].read_text(encoding="utf-8")
    qs = [line.split("|")[1].strip() for line in draft.splitlines() if line.startswith("| A") and line.split("|")[1].strip()[:2] in {f"A{i}" for i in range(1, 10)}]
    fact("alpaca.open_questions", qs, "E13")
    fact("candidate.gap_down_state", _read_json(by["E14"]).get("state"), "E14")
    snapshot = _sha(json.dumps([[i["id"], i.get("sha256")] for i in items], sort_keys=True).encode())
    return {"snapshot": snapshot, "items": items, "facts": facts, "collected_utc": _now()}


# ------------------------------------------------------------------ specialist documents

def _close(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= max(1e-4, 0.005 * abs(b))
    return a == b


def validate_document(task: str, doc: dict, evidence: dict, analyses: dict | None = None) -> list[str]:
    """Errors (empty = valid). Mechanical checks only: binding, structure, citations, figures, actions."""
    errors: list[str] = []
    ids = {i["id"] for i in evidence["items"] if i.get("present")}
    if doc.get("task") != task:
        errors.append(f"document is for task {doc.get('task')!r}, not {task!r}")
    if doc.get("evidence_snapshot") != evidence["snapshot"]:
        errors.append("document is not bound to this evidence snapshot (stale or for another run)")
    for k in ("author", "mode"):
        if not doc.get(k):
            errors.append(f"missing {k} (who wrote it, and how: e.g. interactive Claude Code session)")
    if doc.get("mode") in ("autonomous_agent", "unattended_model"):
        errors.append("mode claims an unattended/autonomous model; none is available in this project")
    for act in doc.get("requested_actions", []):
        try:
            request_action(act)
        except Refused as exc:
            errors.append(str(exc))
    claims = []
    if task in REQUIRED_SECTIONS:
        secs = doc.get("sections") or {}
        for s in REQUIRED_SECTIONS[task]:
            if s not in secs or not secs[s]:
                errors.append(f"required section missing or empty: {s}")
        for s, body in secs.items():
            for c in (body.get("claims", []) if isinstance(body, dict) else []):
                claims.append((s, c))
    elif task == "skeptical_review":
        claims = [("review", c) for c in doc.get("verdicts", [])]
    seen = set()
    for s, c in claims:
        cid = c.get("id")
        if not cid or cid in seen:
            errors.append(f"{s}: claim without a unique id: {c.get('text', '')[:60]!r}")
        seen.add(cid)
        cites = c.get("cites") or []
        if not cites:
            errors.append(f"{cid}: no evidence cited")
        bad = [e for e in cites if e not in ids]
        if bad:
            errors.append(f"{cid}: cites unknown or absent evidence {bad}")
        for f in c.get("figures", []):
            fk, fv = f.get("fact"), f.get("value")
            if fk not in evidence["facts"]:
                errors.append(f"{cid}: figure refers to unknown fact {fk!r}")
            elif not _close(fv, evidence["facts"][fk]["value"]):
                errors.append(f"{cid}: figure {fk}={fv!r} does not match the evidence ({evidence['facts'][fk]['value']!r})")
    if task == "strategy_analysis":
        d = (doc.get("sections") or {}).get("decision") or {}
        for k in ("recommendation", "alternatives", "evidence_needed"):
            if not d.get(k):
                errors.append(f"decision.{k} missing")
        if d and not d.get("is_proposal_only", False):
            errors.append("decision must be marked is_proposal_only: it authorizes no implementation or evaluation")
    if task == "skeptical_review" and analyses is not None:
        want = {c["id"] for a in analyses.values() for body in (a.get("sections") or {}).values()
                if isinstance(body, dict) for c in body.get("claims", [])} | {"DECISION"}
        got = {v.get("id") for v in doc.get("verdicts", [])}
        if want - got:
            errors.append(f"review gives no verdict for: {sorted(want - got)}")
        for v in doc.get("verdicts", []):
            if v.get("verdict") not in ("accept", "challenge", "reject") or not v.get("reason"):
                errors.append(f"{v.get('id')}: verdict must be accept/challenge/reject with a reason")
    return errors


# ------------------------------------------------------------------ workflow engine

def _store(db: Path | None = None) -> JobStore:
    return JobStore(db or DB_PATH)


def _active(store: JobStore):
    row = store.db.execute("SELECT id FROM pipelines WHERE experiment=? AND status IN ('queued','running','blocked') "
                           "ORDER BY rowid DESC LIMIT 1", (WORKFLOW,)).fetchone()
    return row["id"] if row else None


def start(store: JobStore, root: Path = PROJECT_ROOT) -> dict:
    """Create the workflow, or reuse the active one / the completed one for the same evidence (no duplicates)."""
    active = _active(store)
    if active:
        return {"workflow_id": active, "created": False, "reason": "an unfinished workflow already exists"}
    try:
        ev = collect_evidence(root)
        snap = ev["snapshot"]
    except Exception as exc:                              # evidence failure is recorded, not hidden
        ev, snap = None, "missing-evidence"
        err = f"{type(exc).__name__}: {exc}"
    done = store.db.execute("SELECT pipeline_id FROM jobs WHERE worker='coordinator_report' AND experiment=? "
                            "AND input_key=? AND status='completed'", (WORKFLOW, snap)).fetchone()
    if done:
        return {"workflow_id": done["pipeline_id"], "created": False,
                "reason": "a completed workflow exists for exactly this evidence snapshot"}
    wid = f"{WORKFLOW}@{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    ids = []
    for task, kind, role, deps, criteria in TASKS:
        jid = store.create(wid, task, kind, WORKFLOW, snap,
                           {"question": QUESTION, "role": role, "depends_on": deps, "completion_criteria": criteria,
                            "evidence_snapshot": snap}, commit=False)
        ids.append(jid)
    store.db.execute("INSERT INTO pipelines (id, experiment, pipeline, created_utc, status, job_ids_json) "
                     "VALUES (?,?,?,?,?,?)", (wid, WORKFLOW, WORKFLOW, _now(), "running", json.dumps(ids)))
    store.db.commit()
    if ev is None:
        store.set(ids[0], "failed", error=err)
        _finish(store, wid)
    else:
        store.set(ids[0], "running")
        store.set(ids[0], "completed", outputs=ev, evidence={"items": ev["items"]})
    advance(store, wid, root)
    return {"workflow_id": wid, "created": True}


def _tasks(store: JobStore, wid: str) -> dict:
    p = store.pipeline(wid)
    return {store.get(j)["worker"]: store.get(j) for j in p["job_ids"]}


def _sub_path(root: Path, wid: str, task: str) -> Path:
    return root / SUBMISSIONS / wid.replace("@", "_").replace(":", "-") / f"{task}.json"


def submit(store: JobStore, wid: str, task: str, doc: dict, root: Path = PROJECT_ROOT) -> dict:
    """Record a specialist document for a task (it is validated on advance). Refuses non-specialist tasks."""
    if task not in SPEC or SPEC[task][1] != "specialist":
        raise Refused(f"'{task}' is not a specialist task; deterministic tasks cannot be overridden")
    if store.pipeline(wid) is None:
        raise ValueError(f"unknown workflow {wid}")
    path = _sub_path(root, wid, task)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return advance(store, wid, root)


def advance(store: JobStore, wid: str, root: Path = PROJECT_ROOT) -> dict:
    """Move every task as far as its inputs allow. Idempotent: running it again changes nothing."""
    p = store.pipeline(wid)
    if p["status"] in ("completed", "cancelled"):
        return status(store, wid)
    tasks = _tasks(store, wid)
    ev = tasks["evidence"]["outputs"] if tasks["evidence"]["status"] == "completed" else None
    docs: dict[str, dict] = {}
    for name in ORDER[1:]:
        tasks = _tasks(store, wid)                          # fresh: an earlier step in this pass may have completed
        p = store.pipeline(wid)
        t = tasks[name]
        deps = SPEC[name][3]
        if t["status"] == "completed":
            if SPEC[name][1] == "specialist":
                docs[name] = t["outputs"]["document"]
            continue
        dep_states = {d: tasks[d]["status"] for d in deps}
        if any(s in ("failed", "cancelled") for s in dep_states.values()):
            msg = f"upstream failed: {[d for d, s in dep_states.items() if s in ('failed', 'cancelled')]}"
            if t["status"] != "blocked" or t["error"] != msg:
                store.set(t["id"], "blocked", error=msg)
            continue
        if any(s != "completed" for s in dep_states.values()):
            msg = f"waiting for: {[d for d, s in dep_states.items() if s != 'completed']}"
            if t["status"] != "blocked" or t["error"] != msg:
                store.set(t["id"], "blocked", error=msg)
            continue
        if SPEC[name][1] == "specialist":
            path = _sub_path(root, wid, name)
            if not path.is_file():
                msg = (f"awaiting a submitted document for the {SPEC[name][2]}; unattended model UNAVAILABLE, so this "
                       f"role is filled by an explicit submission ({path.relative_to(root).as_posix()})")
                if t["error"] != msg:
                    store.set(t["id"], "blocked", error=msg)
                continue
            raw = path.read_bytes()
            sub_sha = _sha(raw)
            if t["status"] == "failed" and (t["outputs"] or {}).get("submission_sha256") == sub_sha:
                continue                                    # same rejected document: no duplicate re-validation
            if t["status"] == "failed":                     # a new document: a new attempt, the failed one is kept
                new = store.create(wid, name, "specialist", WORKFLOW, t["input_key"], t["inputs"])   # attempt n+1
                ids = [new if j == t["id"] else j for j in p["job_ids"]]
                store.db.execute("UPDATE pipelines SET job_ids_json=? WHERE id=?", (json.dumps(ids), wid))
                store.db.commit()
                p = store.pipeline(wid)
                t = store.get(new)
            store.set(t["id"], "running")
            try:
                doc = json.loads(raw)
                errs = validate_document(name, doc, ev, analyses={k: docs[k] for k in ("strategy_analysis", "data_cost_analysis") if k in docs}
                                         if name == "skeptical_review" else None)
            except ValueError as exc:
                doc, errs = None, [f"not valid JSON: {exc}"]
            out = {"submission": path.relative_to(root).as_posix(), "submission_sha256": sub_sha,
                   "author": (doc or {}).get("author"), "mode": (doc or {}).get("mode")}
            if errs:
                store.set(t["id"], "failed", outputs=out, error="; ".join(errs)[:3000])
                continue
            refs = sorted({e for body in (doc.get("sections") or {}).values() if isinstance(body, dict)
                           for c in body.get("claims", []) for e in c.get("cites", [])} |
                          {e for v in doc.get("verdicts", []) for e in v.get("cites", [])})
            store.set(t["id"], "completed", outputs=out | {"document": doc}, evidence={"cites": refs})
            docs[name] = doc
        else:                                               # coordinator_report
            store.set(t["id"], "running")
            try:
                out, refs = write_report(wid, ev, docs, root)
            except Exception as exc:
                store.set(t["id"], "failed", error=f"{type(exc).__name__}: {exc}")
                continue
            store.set(t["id"], "completed", outputs=out, evidence={"cites": refs})
    _finish(store, wid)
    return status(store, wid)


def _finish(store: JobStore, wid: str) -> None:
    """completed: the report exists. failed: evidence collection failed (nothing can proceed).
    blocked: anything else; each task's error says what it waits for (a rejected specialist document
    can be replaced by a new submission, which becomes a new attempt)."""
    tasks = _tasks(store, wid)
    if tasks["coordinator_report"]["status"] == "completed":
        overall = "completed"
    elif tasks["evidence"]["status"] == "failed":
        overall = "failed"
    else:
        overall = "blocked"
    fin = _now() if overall in ("completed", "failed") else None
    store.db.execute("UPDATE pipelines SET status=?, finished_utc=COALESCE(?, finished_utc) WHERE id=?", (overall, fin, wid))
    store.db.commit()


# ------------------------------------------------------------------ coordinator report (deterministic)

def _claims(doc: dict, section: str) -> list[dict]:
    body = (doc.get("sections") or {}).get(section) or {}
    return body.get("claims", []) if isinstance(body, dict) else []


def write_report(wid: str, ev: dict, docs: dict, root: Path) -> tuple[dict, list[str]]:
    sa, dc, rv = docs["strategy_analysis"], docs["data_cost_analysis"], docs["skeptical_review"]
    verdicts = {v["id"]: v for v in rv["verdicts"]}
    paths = {i["id"]: i["path"] for i in ev["items"] if i.get("present")}

    def line(c):
        v = verdicts.get(c["id"], {})
        mark = {"accept": "accepted", "challenge": "CHALLENGED", "reject": "REJECTED"}.get(v.get("verdict"), "no verdict")
        note = f" — review: {mark}" + (f" ({v.get('reason')})" if v.get("verdict") != "accept" else "")
        return f"- **{c['id']}** {c['text']} [{', '.join(c['cites'])}]{note}"

    def kept(cs):                                        # rejected claims are listed separately, never as findings
        return [c for c in cs if verdicts.get(c["id"], {}).get("verdict") != "reject"]

    rejected = [c for d in (sa, dc) for s in (d.get("sections") or {}) for c in _claims(d, s)
                if verdicts.get(c["id"], {}).get("verdict") == "reject"]
    dec = (sa.get("sections") or {}).get("decision") or {}
    dv = verdicts.get("DECISION", {})
    lines = [f"# Research workflow report: {QUESTION}", "",
             f"Workflow `{wid}` · evidence snapshot `{ev['snapshot'][:16]}` · generated {_now()}", "",
             "**What produced this.** Evidence collection and this report: deterministic code "
             "(`trading/coordinator.py`). Strategy analysis, data/cost analysis and skeptical review: specialist "
             "ROLES, each filled by a submitted document whose author and mode are listed below. "
             f"Unattended model connection: **{UNATTENDED_MODEL['status']}**. Nothing here is autonomous AI.", "",
             "| Role | Author | Mode |", "|---|---|---|"]
    for name, d in (("Strategy analyst", sa), ("Data and cost analyst", dc), ("Skeptical reviewer", rv)):
        lines.append(f"| {name} | {d['author']} | {d['mode']} |")
    lines += ["", "## 1. Why experiments 001 and 002 failed", "", "### 001 intraday momentum",
              *[line(c) for c in kept(_claims(sa, "why_001_failed"))], "", "### 002 opening-range breakout",
              *[line(c) for c in kept(_claims(sa, "why_002_failed"))], "",
              "## 2. What the provisional spread evidence establishes", *[line(c) for c in kept(_claims(dc, "spread_establishes"))],
              "", "### …and what it does not establish", *[line(c) for c in kept(_claims(dc, "spread_does_not_establish"))],
              "", "## 3. Questions blocked on Alpaca", *[line(c) for c in kept(_claims(dc, "alpaca_blocked"))], "",
              "## 4. Next research decision (PROPOSAL ONLY)", ""]
    if dv.get("verdict") == "reject":
        lines += [f"The proposed decision was **REJECTED** by the skeptical review: {dv.get('reason')}",
                  "No recommendation is made; the owner decides from the alternatives below."]
    else:
        lines += [f"**Recommended:** {dec['recommendation']}"]
        if dv.get("verdict") == "challenge":
            lines += ["", f"**Review challenge:** {dv.get('reason')}"]
    lines += ["", "**Alternatives:**", *[f"- {a}" for a in dec.get("alternatives", [])], "",
              "**Evidence needed:**", *[f"- {e}" for e in dec.get("evidence_needed", [])], "",
              "This is a proposal. It authorizes no strategy implementation, no evaluation, no data download, no "
              "experiment and no change to any lock, risk limit or acceptance rule. Only the owner can decide."]
    if rejected:
        lines += ["", "## Claims rejected by the review (not used above)", *[line(c) for c in rejected]]
    if rv.get("summary"):
        lines += ["", "## Skeptical review summary", rv["summary"]]
    refs = sorted({e for d in (sa, dc, rv) for e in json.dumps(d).split('"') if e in paths})
    lines += ["", "## Evidence", "| Id | File | SHA-256 (first 12) |", "|---|---|---|",
              *[f"| {i['id']} | `{i['path']}` | `{i.get('sha256', '')[:12]}` |" for i in ev["items"] if i.get("present")]]
    out_dir = _sub_path(root, wid, "x").parent
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for section in ("## 1.", "## 2.", "## 3.", "## 4."):
        if section not in path.read_text(encoding="utf-8"):
            raise ValueError(f"report missing {section}")
    return {"report_path": path.relative_to(root).as_posix(), "report_sha256": _sha(path.read_bytes()),
            "decision_verdict": dv.get("verdict")}, refs


# ------------------------------------------------------------------ read model (dashboard)

def status(store: JobStore, wid: str) -> dict:
    p = store.pipeline(wid)
    tasks, rows = [], _tasks(store, wid)
    for name in ORDER:
        t = rows[name]
        out = t["outputs"] or {}
        tasks.append({"task": name, "kind": SPEC[name][1], "role": SPEC[name][2], "depends_on": SPEC[name][3],
                      "completion_criteria": SPEC[name][4], "id": t["id"], "attempt": t["attempt"], "status": t["status"],
                      "created_utc": t["created_utc"], "started_utc": t["started_utc"], "finished_utc": t["finished_utc"],
                      "error": t["error"], "evidence_refs": (t["evidence"] or {}).get("cites") or
                      [i["id"] for i in (t["evidence"] or {}).get("items", [])],
                      "author": out.get("author"), "mode": out.get("mode"), "submission": out.get("submission"),
                      "report_path": out.get("report_path"),
                      "facts": out.get("facts") if name == "evidence" else None})
    return {"workflow_id": wid, "question": QUESTION, "status": p["status"], "created_utc": p["created_utc"],
            "finished_utc": p["finished_utc"], "tasks": tasks}


def overview(db: Path | None = None, root: Path = PROJECT_ROOT) -> dict:
    """Everything the dashboard shows (read-only; returns an empty list if no workflow exists)."""
    path = db or DB_PATH
    base = {"unattended_model": UNATTENDED_MODEL, "workflow": WORKFLOW, "question": QUESTION, "workflows": []}
    if not path.is_file():
        return base
    store = JobStore(path)
    try:
        ids = [r["id"] for r in store.db.execute("SELECT id FROM pipelines WHERE experiment=? ORDER BY rowid DESC LIMIT 10", (WORKFLOW,))]
        base["workflows"] = [status(store, w) for w in ids]
    finally:
        store.close()
    for w in base["workflows"]:
        ev_task = next((t for t in w["tasks"] if t["task"] == "evidence"), None)
        store = JobStore(path)
        try:
            row = store.get(ev_task["id"]) if ev_task else None
        finally:
            store.close()
        w["evidence_items"] = [{k: i.get(k) for k in ("id", "path", "role", "sha256", "present")}
                               for i in ((row or {}).get("outputs") or {}).get("items", [])]
        rp = next((t["report_path"] for t in w["tasks"] if t["task"] == "coordinator_report" and t["report_path"]), None)
        if rp and (root / rp).is_file():
            w["report_markdown"] = (root / rp).read_text(encoding="utf-8")
    return base


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Coordinator research workflow (read-only research)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("start")
    s = sub.add_parser("submit"); s.add_argument("workflow_id"); s.add_argument("task"); s.add_argument("file", type=Path)
    a = sub.add_parser("advance"); a.add_argument("workflow_id")
    st = sub.add_parser("status"); st.add_argument("workflow_id", nargs="?")
    r = sub.add_parser("request"); r.add_argument("action")
    args = ap.parse_args(argv)
    if args.cmd == "request":
        try:
            print(request_action(args.action))
            return 0
        except Refused as exc:
            print(str(exc))
            return 3
    store = _store()
    try:
        if args.cmd == "start":
            print(json.dumps(start(store), indent=2))
        elif args.cmd == "submit":
            print(json.dumps(submit(store, args.workflow_id, args.task, json.loads(args.file.read_text(encoding="utf-8"))), indent=2, default=str))
        elif args.cmd == "advance":
            print(json.dumps(advance(store, args.workflow_id), indent=2, default=str))
        else:
            wid = args.workflow_id or _active(store) or (store.db.execute("SELECT id FROM pipelines ORDER BY rowid DESC LIMIT 1").fetchone() or [None])[0]
            print(json.dumps(status(store, wid) if wid else {"workflows": []}, indent=2, default=str))
    except Refused as exc:
        print(str(exc))
        return 3
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
