"""Research-job pipeline over saved experiment artifacts (real jobs, not demo).

Run:  .venv\\Scripts\\python -m trading.jobs run --experiment 001_intraday_momentum
      .venv\\Scripts\\python -m trading.jobs run --experiment 002_opening_range_breakout
      .venv\\Scripts\\python -m trading.jobs list
      .venv\\Scripts\\python -m trading.jobs cancel <job_id>

Pipeline: ingest -> reconcile -> analysis -> rule_checks -> model_review -> report.

- Every job is persisted (SQLite, data/jobs/jobs.sqlite, git-ignored) with inputs, status,
  outputs, evidence, timestamps, attempts and errors.
- States: queued, running, completed, failed, blocked, cancelled.
- A unique index allows only one *completed* job per (worker, experiment, input key), so
  retries or restarts reuse a completed result instead of duplicating it.
- Jobs left "running" by a dead process are marked failed ("interrupted") on the next start.
- model_review is an AUTOMATED SECOND REVIEW by a language model (trading/reviewer). It is
  BLOCKED until the owner authorizes a provider, model and budget, the SDK and key are present,
  and one owner-approved verification call has succeeded. It never overrides the deterministic
  checks and no output is ever substituted. rule_checks is a deterministic checklist.

This module reads saved artifacts only. It never fetches market data, touches validation or
final data, or imports broker code.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import sqlite3
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = PROJECT_ROOT / "research"
DB_PATH = PROJECT_ROOT / "data" / "jobs" / "jobs.sqlite"
REPORT_DIR = PROJECT_ROOT / "results" / "jobs"
HISTORY_MANIFEST = PROJECT_ROOT / "data" / "history" / "SPY" / "sip" / "all" / "manifest.json"
STATES = ("queued", "running", "completed", "failed", "blocked", "cancelled")
# The only work the browser may request: predefined pipelines over predefined saved experiments.
ALLOWED_EXPERIMENTS = ("001_intraday_momentum", "002_opening_range_breakout")
PIPELINES = {"reconcile_report": "Ingest saved artifacts, reconcile recorded gates, analyse, run the "
                                 "deterministic checklist, and write a report. Never re-runs trading evaluations."}
EXPECTED_ARTIFACTS = ("STATUS.json", "EXPERIMENT_LOCK.json", "SPEC.md", "RESULTS_development.md")
STEP_HOOK = None          # tests only: called before each job runs

WORKERS = [
    # name, kind, version, depends on
    ("ingest", "deterministic", "1", []),
    ("reconcile", "deterministic", "1", ["ingest"]),
    ("analysis", "deterministic", "1", ["ingest"]),
    ("rule_checks", "deterministic", "1", ["reconcile", "analysis"]),
    ("model_review", "model", "1", ["analysis", "rule_checks"]),
    ("report", "deterministic", "1", ["reconcile", "analysis", "rule_checks"]),
]
UNIMPLEMENTED_ROLES = [
    {"role": "news analysis", "kind": "unimplemented", "status": "no verified news source"},
    {"role": "broker reconciliation", "kind": "unimplemented", "status": "order submission disabled; nothing to reconcile"},
    {"role": "live performance monitoring", "kind": "unimplemented", "status": "no running service"},
]
MODEL_POLICY = {
    "credential": "ANTHROPIC_API_KEY in the process environment only (never Claude Desktop configuration, never chat)",
    "authorization": "owner-written research/MODEL_REVIEW_AUTHORIZATION.json: provider, model, token limits, "
                     "max calls, per-run and monthly USD caps",
    "proposed_limits": {"max_input_tokens": 30000, "max_output_tokens": 8000, "max_calls_per_run": 1,
                        "max_usd_per_run": 0.50, "max_usd_per_month": 5.00},
    "billing": "Anthropic API usage is billed per token to a Claude Console account with prepaid credits; "
               "a Claude.ai or Claude Code subscription does not cover it",
    "authority": "deterministic checks decide arithmetic and pass/fail; the review is an automated second "
                 "opinion and is rejected if it contradicts them",
}
REVIEW_OVERRIDES = None    # tests only: {"provider": <mock provider>, "auth": {...}}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rel(path: Path) -> str:
    """Project-relative path when possible, otherwise absolute."""
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


_INIT_LOCK = threading.Lock()


class JobStore:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        with _INIT_LOCK:                 # concurrent first opens of a new file can report "locked"
            self._init_schema()

    def _init_schema(self) -> None:
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, pipeline_id TEXT, worker TEXT, kind TEXT, experiment TEXT,
            input_key TEXT, status TEXT, attempt INTEGER, created_utc TEXT, started_utc TEXT,
            finished_utc TEXT, inputs_json TEXT, outputs_json TEXT, evidence_json TEXT, error TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS one_completed
            ON jobs(worker, experiment, input_key) WHERE status = 'completed';
        CREATE TABLE IF NOT EXISTS pipelines (
            id TEXT PRIMARY KEY, experiment TEXT, created_utc TEXT, finished_utc TEXT,
            status TEXT, job_ids_json TEXT);
        """)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(pipelines)")}
        for col, decl in (("pipeline", "TEXT"), ("started_utc", "TEXT"), ("cancel_requested", "INTEGER DEFAULT 0"),
                          ("cancel_requested_utc", "TEXT"), ("error", "TEXT")):
            if col not in cols:
                self.db.execute(f"ALTER TABLE pipelines ADD COLUMN {col} {decl}")
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def recover_interrupted(self) -> int:
        """After a backend restart: work that was running is FAILED (interrupted), never completed.
        Queued jobs of an interrupted pipeline are cancelled (not run). Returns jobs marked failed."""
        now = _now()
        cur = self.db.execute("UPDATE jobs SET status='failed', finished_utc=?, "
                              "error='interrupted: process stopped while running' WHERE status='running'", (now,))
        n = cur.rowcount
        for row in self.db.execute("SELECT id, job_ids_json FROM pipelines WHERE status='running'").fetchall():
            for jid in json.loads(row["job_ids_json"]):
                self.db.execute("UPDATE jobs SET status='cancelled', finished_utc=?, error='not run: pipeline "
                                "interrupted by backend restart' WHERE id=? AND status='queued'", (now, jid))
            self.db.execute("UPDATE pipelines SET status='failed', finished_utc=?, error='interrupted by backend "
                            "restart; work was not completed' WHERE id=?", (now, row["id"]))
        self.db.execute("UPDATE pipelines SET status='cancelled', finished_utc=? WHERE status='queued' "
                        "AND cancel_requested=1", (now,))
        self.db.commit()
        return n

    def pipeline(self, pipeline_id):
        row = self.db.execute("SELECT * FROM pipelines WHERE id=?", (pipeline_id,)).fetchone()
        return dict(row) | {"job_ids": json.loads(row["job_ids_json"])} if row else None

    def active_pipeline(self, experiment):
        row = self.db.execute("SELECT id FROM pipelines WHERE experiment=? AND status IN ('queued','running') "
                              "ORDER BY rowid DESC LIMIT 1", (experiment,)).fetchone()
        return row["id"] if row else None

    def next_queued_pipeline(self):
        row = self.db.execute("SELECT id FROM pipelines WHERE status='queued' AND COALESCE(cancel_requested,0)=0 "
                              "ORDER BY rowid LIMIT 1").fetchone()
        return row["id"] if row else None

    def reusable(self, worker, experiment, key):
        """A completed job, or (for the unimplemented model review) an existing blocked record."""
        row = self.completed(worker, experiment, key)
        if row is None and worker == "model_review":
            row = self.db.execute("SELECT * FROM jobs WHERE worker=? AND experiment=? AND input_key=? AND "
                                  "status='blocked' ORDER BY rowid DESC LIMIT 1", (worker, experiment, key)).fetchone()
        return row

    def completed(self, worker, experiment, key):
        return self.db.execute("SELECT * FROM jobs WHERE worker=? AND experiment=? AND input_key=? "
                               "AND status='completed'", (worker, experiment, key)).fetchone()

    def create(self, pipeline_id, worker, kind, experiment, key, inputs, commit: bool = True) -> str:
        attempt = 1 + self.db.execute("SELECT COUNT(*) FROM jobs WHERE worker=? AND experiment=? AND input_key=?",
                                      (worker, experiment, key)).fetchone()[0]
        job_id = f"{experiment}:{worker}:{key[:10]}:a{attempt}"
        self.db.execute("INSERT INTO jobs (id, pipeline_id, worker, kind, experiment, input_key, status, attempt, "
                        "created_utc, inputs_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (job_id, pipeline_id, worker, kind, experiment, key, "queued", attempt, _now(),
                         json.dumps(inputs, default=str)))
        if commit:
            self.db.commit()
        return job_id

    def set(self, job_id, status, outputs=None, evidence=None, error=None):
        assert status in STATES
        field = "started_utc" if status == "running" else "finished_utc"
        self.db.execute(f"UPDATE jobs SET status=?, {field}=?, outputs_json=COALESCE(?, outputs_json), "
                        "evidence_json=COALESCE(?, evidence_json), error=? WHERE id=?",
                        (status, _now(),
                         json.dumps(_finite(outputs), default=str, allow_nan=False) if outputs is not None else None,
                         json.dumps(_finite(evidence), default=str, allow_nan=False) if evidence is not None else None,
                         error, job_id))
        self.db.commit()

    def get(self, job_id):
        row = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return _row(row) if row else None

    def cancel(self, job_id) -> bool:
        cur = self.db.execute("UPDATE jobs SET status='cancelled', finished_utc=? WHERE id=? AND status='queued'",
                              (_now(), job_id))
        self.db.commit()
        return cur.rowcount == 1

    def snapshot(self) -> dict:
        pipes = [dict(r) | {"job_ids": json.loads(r["job_ids_json"]), "cancel_requested": bool(r["cancel_requested"])}
                 for r in self.db.execute("SELECT * FROM pipelines ORDER BY rowid")]
        jobs = [_row(r) for r in self.db.execute("SELECT * FROM jobs ORDER BY rowid")]
        return {"pipelines": pipes, "jobs": jobs, "workers": [{"worker": w, "kind": k, "version": v, "depends_on": d}
                                                              for w, k, v, d in WORKERS],
                "roles": UNIMPLEMENTED_ROLES, "model_policy": MODEL_POLICY}


def _finite(obj):
    """Non-finite floats become None so stored records are valid strict JSON."""
    if isinstance(obj, float):
        return obj if obj == obj and obj not in (float("inf"), float("-inf")) else None
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


def _row(r) -> dict:
    d = dict(r)
    for k in ("inputs_json", "outputs_json", "evidence_json"):
        d[k.replace("_json", "")] = json.loads(d.pop(k)) if d.get(k) else None
    return d


# ---- workers (pure functions of inputs) ----------------------------------------------

def _load_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def ingest(exp_dir: Path) -> tuple[dict, dict]:
    status = json.loads((exp_dir / "STATUS.json").read_text(encoding="utf-8"))
    run_id = status["development_run_id"]
    candidates = sorted((exp_dir / "runs").glob(f"{run_id}*.json"))
    report_path = next((p for p in candidates if p.stem == run_id), None)
    if report_path is None:
        raise FileNotFoundError(f"saved run report runs/{run_id}.json is missing")
    files = {"STATUS.json": exp_dir / "STATUS.json", "report": report_path}
    for name in ("EXPERIMENT_LOCK.json", "SPEC.md", "RESULTS_development.md"):
        if not (exp_dir / name).is_file():
            raise FileNotFoundError(f"{name} is missing")
        files[name] = exp_dir / name
    log = next((exp_dir / n for n in ("experiment_runs.csv", "variants.csv") if (exp_dir / n).is_file()), None)
    if log is None:
        raise FileNotFoundError("run log (experiment_runs.csv or variants.csv) is missing")
    files["run_log"] = log
    report = json.loads(report_path.read_text(encoding="utf-8"))          # raises on corrupt JSON
    lock = json.loads((exp_dir / "EXPERIMENT_LOCK.json").read_text(encoding="utf-8"))
    rows = _load_csv(log)
    hashes = {k: {"path": _rel(p), "sha256": _sha(p.read_bytes())[:16],
                  "bytes": p.stat().st_size} for k, p in files.items()}
    return ({"experiment_id": status["experiment_id"], "run_id": run_id, "state": status.get("state"),
             "closed": status.get("closed", False), "failed_rules_recorded": status.get("failed_rules", []),
             "lock_id": lock["experiment_id"], "log_rows_for_run": [r for r in rows if run_id in r.get("run_id", "")],
             "report": report},
            {"files": hashes})


def _rules_001(r: dict) -> dict:
    b, st = r["results_by_cost"]["base"], r["results_by_cost"]["stress"]
    return {"1_positive_after_costs": b["net_return"] > 0 and st["net_return"] >= 0,
            "2_beats_baselines": b["net_return"] > r["baseline_always_long"]["net_return"]
            and r["random_direction"]["strategy_percentile"] >= 95,
            "3_drawdown_within_limit": b["max_drawdown"] <= r["risk_limits"]["max_drawdown"],
            "4_survives_top10_removal": b["pnl_without_top10"] > 0,
            "5_neighbors_same_sign": all(v > 0 for v in r["neighbors_net_return"].values())}


def _rules_002(r: dict) -> dict:
    b, st = r["primary"]["base"], r["primary"]["stress"]
    return {"D1": b["net_return"] > 0 and st["net_return"] >= 0,
            "D2": not b["halted"] and not st["halted"]
            and max(b["max_drawdown_intraday"], st["max_drawdown_intraday"]) <= 0.03,
            "D3": b["net_return"] > r["B3"]["net_return"],
            "D4": b["net_pnl"] - b["top10_winners_pnl"] > 0,
            "D5": all(v["net_return"] > 0 and not v["halted"] for v in r["robustness"].values()),
            "D6": r["diagnostics"]["B1"]["20261104"]["strategy_percentile"] >= 95}


def reconcile(ing: dict) -> tuple[dict, dict]:
    r = ing["report"]
    if "results_by_cost" in r:
        recomputed, recorded = _rules_001(r), r["pass_rules"]
        log_checks = [(row["run_id"], float(row["net_return_base"]), r["results_by_cost"]["base"]["net_return"])
                      for row in ing["log_rows_for_run"]]
    else:
        recomputed, recorded = _rules_002(r), {k: v["pass"] for k, v in r["rules"].items()}
        cfg = {"primary": r["primary"]["base"], **r["robustness"]}
        log_checks = [(row["configuration"], float(row["net_return_base"]), cfg[row["configuration"]]["net_return"])
                      for row in ing["log_rows_for_run"]]
    checks = []
    for rule, value in recomputed.items():
        checks.append({"check": f"gate {rule}: recomputed vs recorded in report", "recomputed": value,
                       "recorded": recorded.get(rule), "ok": value == recorded.get(rule)})
    failed = sorted(k for k, v in recomputed.items() if not v)
    checks.append({"check": "failed rules: recomputed vs STATUS.json", "recomputed": failed,
                   "recorded": sorted(ing["failed_rules_recorded"]), "ok": failed == sorted(ing["failed_rules_recorded"])})
    checks.append({"check": "run log rows exist for the recorded run", "recomputed": len(log_checks),
                   "recorded": ">= 1", "ok": len(log_checks) >= 1})
    for name, logged, rep in log_checks:
        checks.append({"check": f"run log net_return_base ({name}) vs report", "recomputed": rep,
                       "recorded": logged, "ok": abs(logged - rep) < 1e-12})
    checks.append({"check": "lock id matches STATUS experiment id", "recomputed": ing["lock_id"],
                   "recorded": ing["experiment_id"], "ok": ing["lock_id"] == ing["experiment_id"]})
    ok = all(c["ok"] for c in checks)
    return ({"reconciled": ok, "discrepancies": [c for c in checks if not c["ok"]], "n_checks": len(checks)},
            {"checks": checks})


def analysis(ing: dict) -> tuple[dict, dict]:
    r = ing["report"]
    if "results_by_cost" in r:
        b, st = r["results_by_cost"]["base"], r["results_by_cost"]["stress"]
        row = {"experiment_id": ing["experiment_id"], "net_return_base": b["net_return"],
               "net_return_stress": st["net_return"], "net_pnl_base": b["net_pnl"], "trades": b["trades"],
               "max_drawdown": b["max_drawdown"], "max_drawdown_basis": "end-of-day equity (001 engine)",
               "win_rate": b["win_rate"], "profit_factor": b["profit_factor"], "sharpe": b["sharpe"],
               "sharpe_ci95": b["sharpe_ci95"], "gross_pnl_base": None,
               "gross_note": "not in the saved report; see RESULTS_development.md (corrected gross -$509.98)"}
    else:
        b, st = r["primary"]["base"], r["primary"]["stress"]
        row = {"experiment_id": ing["experiment_id"], "net_return_base": b["net_return"],
               "net_return_stress": st["net_return"], "net_pnl_base": b["net_pnl"], "trades": b["trades"],
               "max_drawdown": b["max_drawdown_intraday"], "max_drawdown_basis": "intraday marks after costs",
               "win_rate": b["win_rate"], "profit_factor": b["profit_factor"], "sharpe": b["sharpe"],
               "sharpe_ci95": b["sharpe_ci95"], "gross_pnl_base": b["gross_pnl"], "modeled_costs_base": b["modeled_costs"],
               "gross_note": "from the saved report"}
    row["sharpe_ci_includes_zero"] = row["sharpe_ci95"][0] <= 0 <= row["sharpe_ci95"][1]
    return row, {"source": "saved run report", "run_id": ing["run_id"]}


def rule_checks(ing: dict, rec: dict, ana: dict) -> tuple[dict, dict]:
    """Deterministic checklist. Not an independent review."""
    held_out = None
    if HISTORY_MANIFEST.is_file():
        bp = json.loads(HISTORY_MANIFEST.read_text(encoding="utf-8"))["summary"]["by_period"]
        held_out = {"validation_sessions_stored": bp.get("validation", 0), "final_sessions_stored": bp.get("final", 0)}
    findings = [
        {"item": "experiment closed after failing development", "ok": ing["closed"] and ing["state"] == "FAILED_DEVELOPMENT"},
        {"item": "recorded gates reproduce from saved metrics", "ok": rec["reconciled"]},
        {"item": "validation and final data untouched",
         "ok": held_out is not None and not any(held_out.values()), "evidence": held_out},
        {"item": "no positive net result at stress costs", "ok": ana["net_return_stress"] < 0,
         "note": "the result does not survive adverse costs"},
        {"item": "Sharpe interval includes zero (no evidence of an edge)", "ok": ana["sharpe_ci_includes_zero"],
         "note": "an interval entirely below zero is evidence against the rule"},
        {"item": "development data reused across experiments 001 and 002", "ok": False,
         "note": "disclosed limitation, not a defect"},
    ]
    return {"label": "deterministic checklist; not an independent review", "findings": findings}, {}


def model_review(experiment: str, research_dir: Path, env: dict, pipeline_id: str):
    """Automated second review via trading.reviewer. Returns (job status, outputs, reason)."""
    from trading.reviewer import budget, review
    over = REVIEW_OVERRIDES or {}
    store = budget.ReviewStore()
    try:
        res = review.run_review(experiment, research_dir, env, store, run_ref=pipeline_id,
                                provider=over.get("provider"), auth=over.get("auth"))
    finally:
        store.close()
    if res["status"] == "completed":
        out = {k: res.get(k) for k in ("review_id", "review", "model", "prompt_version", "evidence_fingerprint",
                                       "cost_usd", "cached", "mock", "note")}
        out["label"] = "automated second review; not proof of independent correctness"
        return "completed", out, None
    if res["status"] == "blocked":
        return "blocked", None, "UNAVAILABLE: " + "; ".join(res["reasons"])
    return "failed", ({"review_id": res.get("review_id"), "validation_errors": res.get("validation_errors"),
                       "charged_usd": res.get("charged_usd")}), f"{res['status'].upper()}: {res.get('error')}"


def _review_availability() -> str:
    from trading.reviewer import budget, review
    store = budget.ReviewStore()
    try:
        r = review.readiness(dict(os.environ), store)
    finally:
        store.close()
    if r["available"]:
        return "automated second review AVAILABLE: may make one budgeted, billable call unless a cached review matches"
    missing = [c["check"] for c in r["checks"] if not c["ok"]]
    return "UNAVAILABLE: no model call, no output; missing: " + "; ".join(missing)


def _review_gate(env) -> str:
    from trading.reviewer import budget, review
    store = budget.ReviewStore()
    try:
        return review.gate_fingerprint(env, store)
    finally:
        store.close()


def report(pipeline_id: str, ing: dict, rec: dict, ana: dict, chk: dict, review_reason: str) -> tuple[dict, dict]:
    out_dir = REPORT_DIR / pipeline_id
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# Research job report: {ing['experiment_id']} (pipeline {pipeline_id})", "",
             f"State: {ing['state']}; closed: {ing['closed']}; run {ing['run_id']}.", "",
             f"Reconciliation: {'all checks pass' if rec['reconciled'] else 'DISCREPANCIES FOUND'} "
             f"({rec['n_checks']} checks).", "",
             "| Metric | Value |", "|---|---|"]
    for k in ("net_return_base", "net_return_stress", "net_pnl_base", "gross_pnl_base", "trades",
              "max_drawdown", "max_drawdown_basis", "sharpe", "sharpe_ci95"):
        lines.append(f"| {k} | {ana.get(k)} |")
    lines += ["", f"Checklist ({chk['label']}):"] + [f"- [{'x' if f['ok'] else ' '}] {f['item']}" for f in chk["findings"]]
    lines += ["", f"Model review (automated second review, not proof of independent correctness): {review_reason}.",
              "The checklist and gate results above come from deterministic code and are the authority."]
    path = out_dir / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"report_path": _rel(path), "reconciled": rec["reconciled"]}, {"lines": len(lines)}


# ---- pipeline ---------------------------------------------------------------------------

def _validate(experiment: str, pipeline: str = "reconcile_report") -> None:
    if experiment not in ALLOWED_EXPERIMENTS:
        raise ValueError(f"experiment not allowed: {experiment!r}")
    if pipeline not in PIPELINES:
        raise ValueError(f"pipeline not allowed: {pipeline!r}")


def _keys(exp_dir: Path, env=None) -> tuple[str, dict]:
    files = sorted(p for p in exp_dir.rglob("*") if p.is_file()) if exp_dir.is_dir() else []
    artifact_key = _sha(json.dumps([(str(p.relative_to(exp_dir)), _sha(p.read_bytes())) for p in files]).encode())
    keys = {}
    gate = _review_gate(os.environ if env is None else env)
    for worker, _, version, deps in WORKERS:
        parts = [worker, version, artifact_key, [keys[d] for d in deps]]
        if worker == "model_review":
            parts.append(gate)          # re-evaluated when any reviewer gate changes; other keys unchanged
        if worker == "report":
            parts.append(keys["model_review"])     # the report states the current review status
        keys[worker] = _sha(json.dumps(parts).encode())
    return artifact_key, keys


def inventory(experiment: str, research_dir: Path = RESEARCH_DIR) -> dict:
    """Read-only artifact listing for the browser. Never raises for missing or corrupt files."""
    _validate(experiment)
    exp_dir = research_dir / experiment
    out = {"experiment": experiment, "artifacts": [], "status": None, "problems": []}
    try:
        status = json.loads((exp_dir / "STATUS.json").read_text(encoding="utf-8"))
        out["status"] = {k: status.get(k) for k in ("experiment_id", "state", "closed", "status", "failed_rules",
                                                    "development_run_id")}
    except (OSError, ValueError) as exc:
        out["problems"].append(f"STATUS.json unreadable: {type(exc).__name__}")
    names = list(EXPECTED_ARTIFACTS)
    if out["status"] and out["status"].get("development_run_id"):
        names.append(f"runs/{out['status']['development_run_id']}.json")
    names.append("experiment_runs.csv" if (exp_dir / "experiment_runs.csv").is_file() else "variants.csv")
    for name in names:
        path = exp_dir / name
        if path.is_file():
            out["artifacts"].append({"name": name, "present": True, "bytes": path.stat().st_size,
                                     "sha256": _sha(path.read_bytes())[:16]})
        else:
            out["artifacts"].append({"name": name, "present": False})
            out["problems"].append(f"{name} is missing")
    return out


def preview(experiment: str, store: "JobStore", research_dir: Path = RESEARCH_DIR) -> dict:
    """What starting the pipeline would do, without creating anything."""
    _validate(experiment)
    _, keys = _keys(research_dir / experiment)
    tasks = []
    for worker, kind, version, deps in WORKERS:
        row = store.reusable(worker, experiment, keys[worker])
        action = f"reuse {row['status']} record {row['id']}" if row is not None else "will run"
        if worker == "model_review":
            action += f" ({_review_availability()})"
        tasks.append({"worker": worker, "kind": kind, "version": version, "depends_on": deps, "action": action})
    return {"experiment": experiment, "pipeline": "reconcile_report", "description": PIPELINES["reconcile_report"],
            "active_pipeline": store.active_pipeline(experiment), "tasks": tasks}


def plan_pipeline(experiment: str, store: "JobStore", research_dir: Path = RESEARCH_DIR,
                  pipeline: str = "reconcile_report") -> tuple[str, bool]:
    """Create a queued pipeline, reusing completed work. If one is already queued or running for
    this experiment, return it instead: repeated clicks never duplicate work."""
    _validate(experiment, pipeline)
    exp_dir = research_dir / experiment
    artifact_key, keys = _keys(exp_dir)
    # One write transaction for check + insert: simultaneous requests (threads or processes)
    # serialize here, so only the first creates a pipeline and the rest see it as active.
    if store.db.in_transaction:
        store.db.commit()
    store.db.execute("BEGIN IMMEDIATE")
    try:
        active = store.active_pipeline(experiment)
        if active:
            store.db.rollback()
            return active, False
        pipeline_id = _plan_rows(experiment, store, exp_dir, artifact_key, keys, pipeline)
        store.db.commit()
    except BaseException:
        store.db.rollback()
        raise
    return pipeline_id, True


def _plan_rows(experiment, store, exp_dir, artifact_key, keys, pipeline) -> str:
    pipeline_id = f"{experiment}@{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    job_ids = []
    for worker, kind, version, deps in WORKERS:
        row = store.reusable(worker, experiment, keys[worker])
        if row is not None:
            job_ids.append(row["id"])
            continue
        inputs = {"experiment_dir": _rel(exp_dir), "artifact_key": artifact_key[:16],
                  "depends_on": {d: keys[d][:10] for d in deps}}
        job_ids.append(store.create(pipeline_id, worker, kind, experiment, keys[worker], inputs, commit=False))
    store.db.execute("INSERT INTO pipelines (id, experiment, created_utc, status, job_ids_json, pipeline, "
                     "cancel_requested) VALUES (?,?,?,?,?,?,0)",
                     (pipeline_id, experiment, _now(), "queued", json.dumps(job_ids), pipeline))
    return pipeline_id


def request_cancel(pipeline_id: str, store: "JobStore") -> str:
    """Queued pipeline: cancelled immediately. Running pipeline: cancellation REQUESTED; the job
    currently running finishes (each step is atomic and short), then every remaining queued job is
    cancelled and the pipeline becomes cancelled. Completed jobs and their evidence are kept."""
    p = store.pipeline(pipeline_id)
    if p is None:
        raise KeyError(pipeline_id)
    now = _now()
    if p["status"] == "queued":
        for jid in p["job_ids"]:
            store.db.execute("UPDATE jobs SET status='cancelled', finished_utc=?, error='cancelled before start' "
                             "WHERE id=? AND status='queued'", (now, jid))
        store.db.execute("UPDATE pipelines SET status='cancelled', cancel_requested=1, cancel_requested_utc=?, "
                         "finished_utc=? WHERE id=?", (now, now, pipeline_id))
        store.db.commit()
        return "cancelled"
    if p["status"] == "running":
        store.db.execute("UPDATE pipelines SET cancel_requested=1, cancel_requested_utc=? WHERE id=?",
                         (now, pipeline_id))
        store.db.commit()
        return "cancel_requested"
    return f"already {p['status']}"


def execute_pipeline(pipeline_id: str, store: "JobStore", research_dir: Path = RESEARCH_DIR, env=None) -> dict:
    env = os.environ if env is None else env
    p = store.pipeline(pipeline_id)
    exp_dir = research_dir / p["experiment"]
    store.db.execute("UPDATE pipelines SET status='running', started_utc=? WHERE id=? AND status='queued'",
                     (_now(), pipeline_id))
    store.db.commit()
    order = {w: i for i, (w, *_r) in enumerate(WORKERS)}
    jobs = sorted((store.get(j) for j in p["job_ids"]), key=lambda j: order[j["worker"]])
    results, reasons, cancelled = {}, {}, False
    for job in jobs:
        worker, job_id = job["worker"], job["id"]
        if job["status"] == "completed":
            results[worker] = job["outputs"]
            continue
        if job["status"] != "queued":
            if worker == "model_review":
                reasons["model_review"] = job["error"]
            continue
        if cancelled or store.pipeline(pipeline_id)["cancel_requested"]:
            cancelled = True
            store.set(job_id, "cancelled", error="cancelled on request before this job started")
            continue
        deps = next(d for w, _k, _v, d in WORKERS if w == worker)
        missing = [d for d in deps if d not in results]
        if missing:
            store.set(job_id, "blocked", error=f"upstream not completed: {missing}")
            continue
        store.set(job_id, "running")
        if STEP_HOOK:
            STEP_HOOK(worker)
        try:
            if worker == "ingest":
                out, ev = ingest(exp_dir)
            elif worker == "reconcile":
                out, ev = reconcile(results["ingest"])
            elif worker == "analysis":
                out, ev = analysis(results["ingest"])
            elif worker == "rule_checks":
                out, ev = rule_checks(results["ingest"], results["reconcile"], results["analysis"])
            elif worker == "model_review":
                status, out, reason = model_review(p["experiment"], research_dir, env, pipeline_id)
                if status == "completed":
                    reasons["model_review"] = (f"automated second review completed ({out['model']}, "
                                               f"{out['prompt_version']}, review {out['review_id']}); "
                                               "deterministic checks remain the authority")
                else:
                    reasons["model_review"] = reason
                store.set(job_id, status, outputs=out, evidence={"policy": MODEL_POLICY}, error=reason)
                if status == "completed":
                    results[worker] = out
                continue
            else:
                out, ev = report(pipeline_id, results["ingest"], results["reconcile"], results["analysis"],
                                 results["rule_checks"], reasons.get("model_review", "not run"))
        except Exception as exc:                                # recorded, never hidden
            store.set(job_id, "failed", error=f"{type(exc).__name__}: {exc}")
            continue
        store.set(job_id, "completed", outputs=out, evidence=ev)
        results[worker] = out
    statuses = [store.get(j)["status"] for j in p["job_ids"]]
    if cancelled:
        overall = "cancelled"
    elif "failed" in statuses:
        overall = "failed"
    else:
        overall = "completed" if results.get("report") else "blocked"
    store.db.execute("UPDATE pipelines SET status=?, finished_utc=? WHERE id=?", (overall, _now(), pipeline_id))
    store.db.commit()
    return {"pipeline_id": pipeline_id, "status": overall, "jobs": dict(zip(p["job_ids"], statuses))}


def run_pipeline(experiment: str, store: "JobStore", research_dir: Path = RESEARCH_DIR, env=None) -> dict:
    """Synchronous plan + execute (CLI and tests). Reuses an already active pipeline."""
    store.recover_interrupted()
    pipeline_id, created = plan_pipeline(experiment, store, research_dir)
    if not created:
        p = store.pipeline(pipeline_id)
        return {"pipeline_id": pipeline_id, "status": p["status"],
                "jobs": {j: store.get(j)["status"] for j in p["job_ids"]}}
    return execute_pipeline(pipeline_id, store, research_dir, env)


class JobRunner(threading.Thread):
    """Executes queued pipelines outside web requests, one at a time, with its own connection."""

    def __init__(self, db_path: Path = DB_PATH, research_dir: Path = RESEARCH_DIR, poll: float = 0.3):
        super().__init__(daemon=True, name="job-runner")
        self.db_path, self.research_dir, self.poll = db_path, research_dir, poll
        self.stop_event = threading.Event()

    def run(self):
        store = JobStore(self.db_path)
        store.recover_interrupted()
        from trading.reviewer import budget
        rstore = budget.ReviewStore()
        try:
            rstore.recover_in_flight()          # a review call cut off by a restart is UNCERTAIN, not done
        finally:
            rstore.close()
        try:
            while not self.stop_event.wait(self.poll):
                pid = store.next_queued_pipeline()
                if pid:
                    execute_pipeline(pid, store, self.research_dir)
        finally:
            store.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Research-job pipeline over saved experiment artifacts")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--experiment", required=True, choices=list(ALLOWED_EXPERIMENTS))
    sub.add_parser("list")
    c = sub.add_parser("cancel")
    c.add_argument("pipeline_id")
    args = parser.parse_args(argv)
    store = JobStore()
    try:
        if args.cmd == "run":
            print(json.dumps(run_pipeline(args.experiment, store), indent=2))
        elif args.cmd == "list":
            for j in store.snapshot()["jobs"]:
                print(f"{j['created_utc']}  {j['status']:9s}  {j['id']}  {j['error'] or ''}")
        else:
            print(request_cancel(args.pipeline_id, store))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
