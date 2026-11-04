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
- model_review is a model-powered role. It stays BLOCKED unless an API key and an explicit
  spending authorization exist, and even then it is not implemented in this milestone.
  No agent output is ever substituted. rule_checks is a deterministic checklist, not an
  independent review.

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
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = PROJECT_ROOT / "research"
DB_PATH = PROJECT_ROOT / "data" / "jobs" / "jobs.sqlite"
REPORT_DIR = PROJECT_ROOT / "results" / "jobs"
HISTORY_MANIFEST = PROJECT_ROOT / "data" / "history" / "SPY" / "sip" / "all" / "manifest.json"
STATES = ("queued", "running", "completed", "failed", "blocked", "cancelled")

WORKERS = [
    # name, kind, version, depends on
    ("ingest", "deterministic", "1", []),
    ("reconcile", "deterministic", "1", ["ingest"]),
    ("analysis", "deterministic", "1", ["ingest"]),
    ("rule_checks", "deterministic", "1", ["reconcile", "analysis"]),
    ("model_review", "model", "0", ["analysis", "rule_checks"]),
    ("report", "deterministic", "1", ["reconcile", "analysis", "rule_checks"]),
]
UNIMPLEMENTED_ROLES = [
    {"role": "independent model review", "kind": "model", "status": "blocked: needs API key, billing and owner authorization"},
    {"role": "news analysis", "kind": "unimplemented", "status": "no verified news source"},
    {"role": "broker reconciliation", "kind": "unimplemented", "status": "order submission disabled; nothing to reconcile"},
    {"role": "live performance monitoring", "kind": "unimplemented", "status": "no running service"},
]
MODEL_POLICY = {
    "credential": "ANTHROPIC_API_KEY (not read from Claude Desktop configuration)",
    "authorization": "an owner-written research/MODEL_REVIEW_AUTHORIZATION.json with max_usd and max_calls",
    "proposed_limits": {"max_calls_per_pipeline": 1, "max_usd_per_pipeline": 1.00, "max_usd_per_month": 10.00},
    "billing": "API usage is billed per token to the key owner's Anthropic account",
}


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


class JobStore:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
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
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def recover_interrupted(self) -> int:
        cur = self.db.execute("UPDATE jobs SET status='failed', finished_utc=?, "
                              "error='interrupted: process stopped while running' WHERE status='running'", (_now(),))
        self.db.commit()
        return cur.rowcount

    def completed(self, worker, experiment, key):
        return self.db.execute("SELECT * FROM jobs WHERE worker=? AND experiment=? AND input_key=? "
                               "AND status='completed'", (worker, experiment, key)).fetchone()

    def create(self, pipeline_id, worker, kind, experiment, key, inputs) -> str:
        attempt = 1 + self.db.execute("SELECT COUNT(*) FROM jobs WHERE worker=? AND experiment=? AND input_key=?",
                                      (worker, experiment, key)).fetchone()[0]
        job_id = f"{experiment}:{worker}:{key[:10]}:a{attempt}"
        self.db.execute("INSERT INTO jobs (id, pipeline_id, worker, kind, experiment, input_key, status, attempt, "
                        "created_utc, inputs_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (job_id, pipeline_id, worker, kind, experiment, key, "queued", attempt, _now(),
                         json.dumps(inputs, default=str)))
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
        pipes = [dict(r) | {"job_ids": json.loads(r["job_ids_json"])}
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


def model_review(env: dict) -> tuple[str, dict | None, str]:
    """Never calls a model in this milestone. Returns (status, outputs, reason)."""
    if not env.get("ANTHROPIC_API_KEY"):
        return "blocked", None, "model review unavailable: ANTHROPIC_API_KEY is not set in this process"
    if not (RESEARCH_DIR / "MODEL_REVIEW_AUTHORIZATION.json").is_file():
        return "blocked", None, "model review unavailable: paid usage not authorized by the owner"
    return "blocked", None, "model review not implemented in this milestone"


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
    lines += ["", f"Model review: {review_reason}. No model output was produced or substituted."]
    path = out_dir / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"report_path": _rel(path), "reconciled": rec["reconciled"]}, {"lines": len(lines)}


# ---- pipeline ---------------------------------------------------------------------------

def run_pipeline(experiment: str, store: JobStore, research_dir: Path = RESEARCH_DIR, env=None) -> dict:
    env = os.environ if env is None else env
    exp_dir = research_dir / experiment
    store.recover_interrupted()
    pipeline_id = f"{experiment}@{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    files = sorted(p for p in exp_dir.rglob("*") if p.is_file()) if exp_dir.is_dir() else []
    artifact_key = _sha(json.dumps([(str(p.relative_to(exp_dir)), _sha(p.read_bytes())) for p in files]).encode())
    results, job_ids, keys, reasons = {}, [], {}, {}
    for worker, kind, version, deps in WORKERS:
        key = _sha(json.dumps([worker, version, artifact_key, [keys.get(d) for d in deps]]).encode())
        keys[worker] = key
        done = store.completed(worker, experiment, key)
        if done is not None:                                 # reuse: never duplicate a completed job
            job_ids.append(done["id"])
            results[worker] = _row(done)["outputs"]
            continue
        inputs = {"experiment_dir": _rel(exp_dir), "artifact_key": artifact_key[:16], "depends_on": {d: keys[d][:10] for d in deps}}
        job_id = store.create(pipeline_id, worker, kind, experiment, key, inputs)
        job_ids.append(job_id)
        if store.get(job_id)["status"] == "cancelled":
            continue
        missing = [d for d in deps if d not in results and not (d == "model_review")]
        if missing:
            store.set(job_id, "blocked", error=f"upstream not completed: {missing}")
            continue
        store.set(job_id, "running")
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
                status, out, reason = model_review(env)
                reasons["model_review"] = reason
                store.set(job_id, status, evidence={"policy": MODEL_POLICY}, error=reason)
                continue
            else:
                out, ev = report(pipeline_id, results["ingest"], results["reconcile"], results["analysis"],
                                 results["rule_checks"], reasons.get("model_review", "not run"))
        except Exception as exc:                                # recorded, never hidden
            store.set(job_id, "failed", error=f"{type(exc).__name__}: {exc}")
            continue
        store.set(job_id, "completed", outputs=out, evidence=ev)
        results[worker] = out
    statuses = [store.get(j)["status"] for j in job_ids]
    overall = "failed" if "failed" in statuses else ("completed" if all(s in ("completed", "blocked") for s in statuses)
                                                     and results.get("report") else "blocked")
    store.db.execute("INSERT INTO pipelines VALUES (?,?,?,?,?,?)",
                     (pipeline_id, experiment, _now(), _now(), overall, json.dumps(job_ids)))
    store.db.commit()
    return {"pipeline_id": pipeline_id, "status": overall, "jobs": dict(zip(job_ids, statuses))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Research-job pipeline over saved experiment artifacts")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--experiment", required=True, choices=["001_intraday_momentum", "002_opening_range_breakout"])
    sub.add_parser("list")
    c = sub.add_parser("cancel")
    c.add_argument("job_id")
    args = parser.parse_args(argv)
    store = JobStore()
    if args.cmd == "run":
        print(json.dumps(run_pipeline(args.experiment, store), indent=2))
    elif args.cmd == "list":
        snap = store.snapshot()
        for j in snap["jobs"]:
            print(f"{j['created_utc']}  {j['status']:9s}  {j['id']}  {j['error'] or ''}")
    else:
        print("cancelled" if store.cancel(args.job_id) else "not cancelled (only queued jobs can be cancelled)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
