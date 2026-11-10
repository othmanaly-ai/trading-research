"""Evidence trace: one monitored session, from stored evidence through the EXISTING checks to the stored report.

    stored live bars + worker runs  ->  capture_inventory        (Data Centre)
                                    ->  structural_validation    (Data Centre; existing quality.bar_defects)
    q_runs / q_compare              ->  iex_sip_comparison       (Data Centre; results of the existing QualityChecker)
    q_obs revisions                 ->  revision_tracking        (Data Centre)
    all of the above                ->  reliability_assessment   (Operations; existing reliability.daily_report and
                                                                  the existing "report completion" criterion)
    q_reports versions              ->  report_finalization      (Evidence Archive; integrity + reproduction check)

Nothing here collects data, calls a provider or changes monitoring records: the monitoring database is opened
read-only. It writes only its own task records (`data/jobs/desk.sqlite`), using the research-job store
(`trading.jobs.JobStore`: states, retry/attempt numbering, restart recovery, one-completed-result-per-input).

Each task record holds: task and run ids, task type and implementation version, parent run and dependency ids,
input references and fingerprints, configuration and code versions, timestamps, status, failure details,
attempt (retry) history, output and output fingerprint, and whether it came from real records or a fixture.
A result whose inputs, configuration and code are unchanged is REUSED (recorded as such), not recomputed.

CLI:  python -m trading.monitor.evidence_trace run --date 2026-11-09
      python -m trading.monitor.evidence_trace list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading.jobs import JobStore
from trading.monitor import store as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DESK_DB = PROJECT_ROOT / "data" / "jobs" / "desk.sqlite"
SYMBOLS = ("SPY", "QQQ", "IWM")

# (task, department, implementation version, depends on, handler description)
TASKS = [
    ("capture_inventory", "Data Centre", "1", [], "stored live bars (bars) and worker runs (m_workers)"),
    ("structural_validation", "Data Centre", "1", ["capture_inventory"], "trading.monitor.quality.bar_defects on every stored live bar"),
    ("iex_sip_comparison", "Data Centre", "1", ["capture_inventory"], "recorded QualityChecker runs (q_runs) and comparisons (q_compare)"),
    ("revision_tracking", "Data Centre", "1", ["iex_sip_comparison"], "observation revisions (q_obs)"),
    ("reliability_assessment", "Operations", "1", ["structural_validation", "iex_sip_comparison", "revision_tracking"],
     "trading.monitor.reliability.daily_report + the existing report-completion criterion (docs/MONITORING.md)"),
    ("report_finalization", "Evidence Archive", "1", ["reliability_assessment"],
     "stored q_reports versions: integrity (stored hash) and reproduction (recomputed evidence hash)"),
]
ORDER = [t[0] for t in TASKS]
SPEC = {t[0]: t for t in TASKS}
HOOK = None                      # tests only: called with the task name before its handler runs
HANDLER_OVERRIDES: dict = {}     # tests only: replace a handler to exercise invalid-output rejection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fp(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def config_version() -> dict:
    from trading.monitor import quality, reliability
    cfg = {"normal_live_latency_s": reliability.NORMAL_LIVE_LATENCY_S, "stale_gap_s": reliability.STALE_GAP_S,
           "sip_delay_min": quality.SIP_DELAY.total_seconds() / 60, "safety_margin_min": quality.SAFETY_MARGIN.total_seconds() / 60,
           "categories": list(quality.CATEGORIES), "report_completion_rule": "docs/MONITORING.md: FINALIZED, or INCOMPLETE with a reason",
           "reliability_gate": "PROPOSED, NOT ACTIVE (docs/RELIABILITY_GATE_PROPOSAL.md)"}
    return {"fingerprint": _fp(cfg)[:16], "values": cfg}


SOURCE_FILES = ("trading/monitor/evidence_trace.py", "trading/monitor/reliability.py", "trading/monitor/quality.py",
                "trading/monitor/store.py")


def code_version() -> str | None:
    """Git label plus a hash of the source files the handlers run. A git label alone ('…+dirty') does not change
    when uncommitted code changes, which would let a stale result be reused."""
    try:
        from trading.monitor.worker import code_version as cv
        label = cv()
    except Exception:
        label = "unknown"
    h = hashlib.sha256()
    for rel in SOURCE_FILES:
        f = PROJECT_ROOT / rel
        h.update(rel.encode() + (f.read_bytes() if f.is_file() else b"<missing>"))
    return f"{label}|src:{h.hexdigest()[:12]}"


def open_monitor_readonly(path: Path | None = None) -> sqlite3.Connection:
    """A snapshot of the monitoring database, opened read-only (the store itself is never modified here)."""
    p = path or st.DB_PATH
    if not p.is_file():
        raise FileNotFoundError(f"input missing: monitoring store not found ({p.name})")
    src = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=10)
    try:
        db = sqlite3.connect(":memory:")       # consistent in-memory snapshot; the existing report code may add
        src.backup(db)                         # derived columns there, never in the monitoring store itself
    finally:
        src.close()
    db.row_factory = sqlite3.Row
    return db


def _rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]


def _session(date_s: str):
    from trading.monitor import reliability
    return reliability._session(date_s)


# ------------------------------------------------------------------ inputs (references + fingerprints)

def gather_inputs(db, date_s: str) -> dict:
    """Input references and fingerprints per task, read from the monitoring records (no computation)."""
    bars = _rows(db, "SELECT symbol, feed, t_utc, o, h, l, c, v, received_utc FROM bars WHERE session_date=? AND feed='iex' "
                    "ORDER BY symbol, t_utc", (date_s,))
    # Only worker runs inside the window the report uses (open - 30 min to close + 3 h), with last-alive capped at its
    # end: a worker still running today must not change the input fingerprint of a closed session every heartbeat.
    sess = _session(date_s)
    runs = []
    if sess is not None:
        w0, w1 = (sess.open_utc - timedelta(minutes=30)).isoformat(), (sess.close_utc + timedelta(hours=3)).isoformat()
        runs = [dict(r, last_alive_utc=min(r["last_alive_utc"] or "", w1)) for r in _rows(
            db, "SELECT id, pid, started_utc, last_alive_utc, stopped_utc, exit_reason, code_version FROM m_workers "
                "WHERE started_utc < ? AND last_alive_utc >= ? ORDER BY id", (w1, w0))]
    qruns = _rows(db, "SELECT id, kind, status, http_status, started_utc, finished_utc, window_start_utc, window_end_utc, compared, error "
                      "FROM q_runs WHERE session_date=? ORDER BY id", (date_s,))
    qcmp = db.execute("SELECT COUNT(*), COALESCE(MAX(compared_utc), '') FROM q_compare WHERE session_date=?", (date_s,)).fetchone()
    obs = db.execute("SELECT COUNT(*), COALESCE(MAX(revision), 0), COALESCE(MAX(retrieved_utc), '') FROM q_obs WHERE session_date=?",
                     (date_s,)).fetchone()
    state = db.execute("SELECT * FROM q_state WHERE session_date=?", (date_s,)).fetchone()
    reports = _rows(db, "SELECT session_date, version, status, created_utc, report_sha, amends_version FROM q_reports "
                        "WHERE session_date=? ORDER BY version", (date_s,))
    try:
        corrections = _rows(db, "SELECT * FROM q_report_corrections WHERE session_date=?", (date_s,))
    except sqlite3.OperationalError:
        corrections = []
    return {
        "bars": {"ref": f"bars WHERE feed=iex AND session_date={date_s}", "rows": len(bars), "fingerprint": _fp(bars), "_data": bars},
        "worker_runs": {"ref": f"m_workers in the {date_s} report window", "rows": len(runs), "fingerprint": _fp(runs), "_data": runs},
        "q_runs": {"ref": f"q_runs WHERE session_date={date_s}", "rows": len(qruns), "fingerprint": _fp(qruns), "_data": qruns},
        "q_compare": {"ref": f"q_compare WHERE session_date={date_s}", "rows": qcmp[0], "fingerprint": _fp(list(qcmp))},
        "q_obs": {"ref": f"q_obs WHERE session_date={date_s}", "rows": obs[0], "fingerprint": _fp(list(obs))},
        "q_state": {"ref": f"q_state {date_s}", "fingerprint": _fp(dict(state) if state else None), "_data": dict(state) if state else None},
        "q_reports": {"ref": f"q_reports WHERE session_date={date_s}", "rows": len(reports), "fingerprint": _fp([reports, corrections]),
                      "_data": reports, "_corrections": corrections},
    }


TASK_INPUTS = {
    "capture_inventory": ("bars", "worker_runs"),
    "structural_validation": ("bars",),
    "iex_sip_comparison": ("q_runs", "q_compare", "q_state"),
    "revision_tracking": ("q_obs",),
    "reliability_assessment": ("bars", "worker_runs", "q_runs", "q_compare", "q_obs", "q_state"),
    "report_finalization": ("q_reports", "bars", "worker_runs", "q_runs", "q_compare", "q_obs", "q_state"),
}


# ------------------------------------------------------------------ handlers (existing checks only)

class Blocked(Exception):
    """Inputs are not ready yet (for example, a session still in progress). Not a failure."""


def h_capture(ctx) -> dict:
    from trading.monitor import reliability
    bars, session = ctx["inputs"]["bars"]["_data"], ctx["session"]
    if session is None:
        raise ValueError(f"{ctx['date']} is not a scheduled XNYS session")
    if not bars:
        raise ValueError("no live bar recorded for this session (not monitored, or the store was empty)")
    per = {}
    for s in SYMBOLS:
        lat = []
        for b in bars:
            if b["symbol"] == s and b["received_utc"]:
                end = datetime.fromisoformat(b["t_utc"]) + timedelta(minutes=1)
                lat.append((datetime.fromisoformat(b["received_utc"]) - end).total_seconds())
        on_time = sum(1 for x in lat if x <= reliability.NORMAL_LIVE_LATENCY_S)
        per[s] = {"received": len(lat), "on_time": on_time, "late": len(lat) - on_time}
    return {"scheduled_minutes": session.regular_minutes, "per_symbol": per,
            "worker_runs_overlapping": sum(1 for r in ctx["inputs"]["worker_runs"]["_data"]
                                           if r["started_utc"] < session.close_utc.isoformat() and (r["last_alive_utc"] or "") > session.open_utc.isoformat())}


def h_structural(ctx) -> dict:
    from trading.monitor import quality
    session, defects, examples = ctx["session"], {s: 0 for s in SYMBOLS}, []
    for b in ctx["inputs"]["bars"]["_data"]:
        found = quality.bar_defects({"t": b["t_utc"], **{k: b[k] for k in ("o", "h", "l", "c", "v")}}, session)
        if found:
            defects[b["symbol"]] = defects.get(b["symbol"], 0) + 1
            if len(examples) < 5:
                examples.append({"symbol": b["symbol"], "t_utc": b["t_utc"], "defects": found})
    return {"bars_checked": len(ctx["inputs"]["bars"]["_data"]), "defects_per_symbol": defects, "examples": examples,
            "check": "trading.monitor.quality.bar_defects"}


def h_comparison(ctx) -> dict:
    runs, state, session = ctx["inputs"]["q_runs"]["_data"], ctx["inputs"]["q_state"]["_data"], ctx["session"]
    if not runs:
        raise Blocked("no comparison run recorded for this session yet")
    through = (state or {}).get("compared_through_utc")
    if not through or datetime.fromisoformat(through) < session.close_utc:
        raise Blocked(f"comparison in progress: compared through {through or 'nothing yet'}; a minute is compared only "
                      "once its end is at least 20 minutes old (15-minute SIP delay + 5-minute margin)")
    db = ctx["db"]
    cats = {r["category"]: r["n"] for r in db.execute(
        "SELECT category, COUNT(*) AS n FROM q_compare c WHERE session_date=? AND NOT EXISTS (SELECT 1 FROM q_compare d "
        "WHERE d.symbol=c.symbol AND d.t_utc=c.t_utc AND (d.sip_rev > c.sip_rev OR (d.sip_rev = c.sip_rev AND "
        "d.iex_rev > c.iex_rev))) GROUP BY category", (ctx["date"],))}   # latest revision per minute, as the report does
    refused = [r for r in runs if r["status"] == "access_failure"]
    failed = [r for r in runs if r["status"] in ("error", "access_failure")]
    return {"runs": len(runs), "runs_ok": sum(1 for r in runs if r["status"] == "ok"), "runs_failed": len(failed),
            "access_refusals": len(refused), "compared_through_utc": through,
            "post_close_recheck_utc": (state or {}).get("eod_recheck_utc"), "categories": cats,
            "failed_runs": [{"id": r["id"], "status": r["status"], "error": (r["error"] or "")[:200]} for r in failed[:5]]}


def h_revisions(ctx) -> dict:
    db = ctx["db"]
    rows = _rows(db, "SELECT feed, COUNT(*) AS n FROM q_obs WHERE session_date=? AND revision > 1 GROUP BY feed", (ctx["date"],))
    return {"observations": ctx["inputs"]["q_obs"]["rows"], "revisions_by_feed": {r["feed"]: r["n"] for r in rows}}


def h_reliability(ctx) -> dict:
    from trading.monitor import reliability
    rep = reliability.daily_report(ctx["store"], ctx["date"], ctx["now"])
    ev, state = rep["evidence"], rep["status"]["state"]
    cap = ctx["outputs"]["capture_inventory"]
    disagree = [s for s in SYMBOLS if s in ev.get("live", {}) and
                (ev["live"][s].get("received_normal"), ev["live"][s].get("received_by_catch_up")) != (cap["per_symbol"][s]["on_time"], cap["per_symbol"][s]["late"])]
    if disagree:
        raise ValueError(f"reliability report and capture inventory disagree for {disagree} (on-time / late counts)")
    ops = ev.get("operations", {})
    ctx["evidence_now"] = ev
    return {"report_state": state, "evidence_fingerprint": _fp(ev),
            "on_time_by_symbol": {s: ev["live"][s].get("received_normal") for s in ev.get("live", {})},
            "late_by_symbol": {s: ev["live"][s].get("received_by_catch_up") for s in ev.get("live", {})},
            "missing_by_symbol": {s: ev["live"][s].get("not_received_minutes") for s in ev.get("live", {})},
            "unplanned_downtime_minutes": ops.get("unplanned_downtime_minutes"), "request_failures": ops.get("request_failures"),
            "access_refusals": ops.get("access_refusals"), "unresolved_items": len(ev.get("unresolved", [])),
            "report_completion_criterion": {"rule": "FINALIZED, or INCOMPLETE with a stated reason (docs/MONITORING.md)",
                                            "meets": state == "finalized" or (state == "incomplete" and bool(rep["status"].get("detail")))},
            "reliability_gate": {"status": "PROPOSED, NOT ACTIVE", "document": "docs/RELIABILITY_GATE_PROPOSAL.md",
                                 "note": "no capture-quality threshold is applied; this session is not evaluated under it"}}


def _leaves(a, b, path=""):
    """Paths whose values differ between two JSON-like values (lists of equal length compared item by item)."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            yield from _leaves(a.get(k, _ABSENT), b.get(k, _ABSENT), f"{path}.{k}" if path else k)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for n, (x, y) in enumerate(zip(a, b)):
            yield from _leaves(x, y, f"{path}[{n}]")
    elif _fp(a) != _fp(b):
        yield path, a, b


_ABSENT = "<absent>"
AMENDABLE = ("operations.request_failures", "operations.failure_events", "operations.failure_events_reclassified_as_other",
             "operations.other_error_events", "operations.other_errors", "operations.other_error_kinds")


def evidence_cutoff(db, date_s: str, version: int, stored: dict) -> tuple[str, str]:
    """When the stored evidence was taken. New reports record it; for older ones it is the creation time of the
    version the evidence came from (a correction copies its source version's evidence; it never recomputes)."""
    rep = stored.get("reproducibility") or {}
    if rep.get("evidence_cutoff_utc"):
        return rep["evidence_cutoff_utc"], "recorded in the report"
    v = version
    for _ in range(20):
        row = db.execute("SELECT from_version FROM q_report_corrections WHERE session_date=? AND version=?", (date_s, v)).fetchone()             if db.execute("SELECT name FROM sqlite_master WHERE name='q_report_corrections'").fetchone() else None
        if not row:
            break
        v = row[0]
    created = db.execute("SELECT created_utc FROM q_reports WHERE session_date=? AND version=?", (date_s, v)).fetchone()[0]
    return created, f"not recorded; inferred as the creation time of v{v}, where this evidence was computed"


def classify_difference(path: str, old, new, stored: dict, planned: list[dict]) -> str:
    """later_evidence | time_dependent | code_change | amendment | defect | unexplained"""
    if any(path.startswith(c["field"].replace("evidence.", "")) for c in planned):
        return "defect"
    if old == _ABSENT:
        return "code_change"
    if ".last_alive_utc" in path and path.startswith("operations.worker_runs"):
        return "time_dependent"
    if stored.get("correction") and path.startswith(AMENDABLE):
        return "amendment"
    if path.startswith(AMENDABLE):
        return "code_change"
    return "unexplained"


EXPLAIN = {
    "later_evidence": "records written after the evidence cutoff (removed by recomputing with the cutoff)",
    "time_dependent": "a still-running worker's last-alive time is overwritten by later heartbeats; the stored value is the only record of it",
    "code_change": "the calculation changed after this report was stored (field added or events classified differently)",
    "amendment": "a recorded amend-only correction changed this field on purpose",
    "defect": "the stored report is internally inconsistent; an amend-only correction is available (not applied)",
    "unexplained": "not explained by the rules above: investigate",
}


def h_report(ctx) -> dict:
    from trading.monitor import reliability
    reports = ctx["inputs"]["q_reports"]["_data"]
    if not reports:
        raise Blocked("no stored report: the session is not finalized yet (finalization needs the comparison through the close and the post-close recheck)")
    latest = reports[-1]
    row = ctx["db"].execute("SELECT report_json FROM q_reports WHERE session_date=? AND version=?",
                            (ctx["date"], latest["version"])).fetchone()
    stored = json.loads(row["report_json"])
    stored_ev_sha = hashlib.sha256(json.dumps(stored["evidence"], sort_keys=True, default=str).encode()).hexdigest()
    if stored_ev_sha != latest["report_sha"]:
        raise ValueError(f"stored report v{latest['version']} fails its integrity check (stored hash does not match its evidence)")
    now_ev = ctx.get("evidence_now")
    if now_ev is None:
        now_ev = reliability.daily_report(ctx["store"], ctx["date"], ctx["now"])["evidence"]
    cutoff, cutoff_source = evidence_cutoff(ctx["db"], ctx["date"], latest["version"], stored)
    at_cutoff = reliability.daily_report(ctx["store"], ctx["date"], ctx["now"], as_of=datetime.fromisoformat(cutoff))["evidence"]
    planned = reliability.plan_correction(stored)
    # what the cutoff removed = later evidence; what still differs is classified field by field
    later = sorted({p for p, _, _ in _leaves(stored["evidence"], now_ev)} - {p for p, _, _ in _leaves(stored["evidence"], at_cutoff)})
    diffs = [{"field": p, "category": classify_difference(p, a, b, stored, planned),
              "stored": json.dumps(a, default=str)[:160], "recomputed": json.dumps(b, default=str)[:160]}
             for p, a, b in _leaves(stored["evidence"], at_cutoff)]
    counts = {}
    for d in diffs:
        counts[d["category"]] = counts.get(d["category"], 0) + 1
    if later:
        counts["later_evidence"] = len(later)
    same = _fp(at_cutoff) == _fp(stored["evidence"])
    return {"versions": [{k: r[k] for k in ("version", "status", "created_utc", "amends_version")} | {"report_sha": r["report_sha"][:16]}
                         for r in reports],
            "latest_version": latest["version"], "latest_status": latest["status"], "integrity": "stored hash matches stored evidence",
            "evidence_cutoff_utc": cutoff, "evidence_cutoff_source": cutoff_source,
            "stored_calc_version": (stored.get("reproducibility") or {}).get("calc_version", "not recorded (1)"),
            "current_calc_version": reliability.REPORT_CALC_VERSION,
            "reproduction": ("recomputed at the evidence cutoff: identical to the stored report" if same else
                             "recomputed at the evidence cutoff: differs (classified below; reports are amend-only and are never "
                             "edited to match a new calculation)"),
            "difference_counts": counts, "differences": diffs[:60], "later_evidence_fields": later[:30],
            "pending_correction": [{k: c[k] for k in ("field", "old", "new", "why")} for c in planned],
            "explanations": {k: EXPLAIN[k] for k in counts},
            "corrections": [{k: c.get(k) for k in ("version", "reason", "created_utc") if k in c} for c in ctx["inputs"]["q_reports"]["_corrections"]],
            "report_link": f"/api/monitor/report?date={ctx['date']}"}


HANDLERS = {"capture_inventory": h_capture, "structural_validation": h_structural, "iex_sip_comparison": h_comparison,
            "revision_tracking": h_revisions, "reliability_assessment": h_reliability, "report_finalization": h_report}


def _int(x):
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def validate_output(task: str, out) -> list[str]:
    """Deterministic shape and consistency checks; an invalid result is rejected (FAILED), never stored as success."""
    e = []
    if not isinstance(out, dict):
        return ["output is not an object"]
    if task == "capture_inventory":
        for s, v in (out.get("per_symbol") or {}).items():
            if not all(_int(v.get(k)) for k in ("received", "on_time", "late")) or v["on_time"] + v["late"] != v["received"]:
                e.append(f"{s}: counts must be non-negative integers with on_time + late = received")
            if _int(v.get("received")) and v["received"] > (out.get("scheduled_minutes") or 0):
                e.append(f"{s}: more bars than scheduled minutes")
        if not out.get("per_symbol"):
            e.append("per_symbol missing")
    elif task == "structural_validation":
        if not _int(out.get("bars_checked")) or not all(_int(v) for v in (out.get("defects_per_symbol") or {}).values()):
            e.append("bars_checked and defect counts must be non-negative integers")
    elif task == "iex_sip_comparison":
        if not all(_int(out.get(k)) for k in ("runs", "runs_ok", "runs_failed", "access_refusals")) or out["runs_ok"] + out["runs_failed"] > out["runs"]:
            e.append("run counts must be consistent non-negative integers")
    elif task == "revision_tracking":
        if not _int(out.get("observations")):
            e.append("observations must be a non-negative integer")
    elif task == "reliability_assessment":
        if out.get("report_state") not in ("in_progress", "provisional", "finalized", "incomplete", "not_monitored"):
            e.append(f"unknown report state {out.get('report_state')!r}")
        if not (isinstance(out.get("evidence_fingerprint"), str) and len(out["evidence_fingerprint"]) == 64):
            e.append("evidence_fingerprint must be a sha256 hex digest")
        if out.get("reliability_gate", {}).get("status") != "PROPOSED, NOT ACTIVE":
            e.append("the reliability gate is only proposed; a result may not claim it is active")
    elif task == "report_finalization":
        if not _int(out.get("latest_version")) or not out.get("versions"):
            e.append("latest_version and versions are required")
    return e


# ------------------------------------------------------------------ runner

def _active_run(store: JobStore, key: str):
    row = store.db.execute("SELECT id FROM pipelines WHERE experiment=? AND status IN ('queued','running') ORDER BY rowid DESC LIMIT 1",
                           (key,)).fetchone()
    return row["id"] if row else None


def _try_lock(path: Path):
    """Exclusive, non-blocking lock held for a whole run (released by the OS if the process dies)."""
    f = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except OSError:
        f.close()
        return None


def _unlock(f) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        f.close()


def run_trace(date_s: str, desk: JobStore | None = None, monitor_db: Path | None = None, now: datetime | None = None,
              source: str = "real monitoring records") -> dict:
    """Run (or reuse) the trace for one session. Returns its status. Never writes the monitoring database.
    Only one trace runs at a time: a request while another is running returns that run (duplicate_request)."""
    own = desk is None
    desk = desk or JobStore(DESK_DB)
    key = f"evidence_trace:{date_s}"
    db_file = Path(desk.db.execute("PRAGMA database_list").fetchone()[2])
    lock = _try_lock(db_file.with_suffix(".lock"))
    try:
        if lock is None:                                 # another run is in progress: never start a second one
            active = _active_run(desk, key)
            if active:
                return status(desk, active) | {"duplicate_request": True}
            return {"run_id": None, "session_date": date_s, "status": "BUSY", "duplicate_request": True, "tasks": [],
                    "error": "another evidence-trace run is in progress; try again when it has finished"}
        desk.recover_interrupted()                       # no run holds the lock: running records were cut off -> FAILED
        active = _active_run(desk, key)
        if active:
            return status(desk, active) | {"duplicate_request": True}
        now = now or datetime.now(timezone.utc)
        cfg, code = config_version(), code_version()
        run_id = f"{key}@{now.strftime('%Y%m%dT%H%M%S%fZ')}"
        try:
            db = open_monitor_readonly(monitor_db)
            inputs = gather_inputs(db, date_s)
        except Exception as exc:
            db, inputs = None, None
            input_error = f"{type(exc).__name__}: {exc}"
        ids = {}
        for task, dept, ver, deps, handler in TASKS:
            refs = {k: {kk: vv for kk, vv in inputs[k].items() if not kk.startswith("_")} for k in TASK_INPUTS[task]} if inputs else {}
            fp = _fp({"inputs": {k: v["fingerprint"] for k, v in refs.items()}, "config": cfg["fingerprint"], "code": code,
                      "version": ver, "deps": deps})
            ids[task] = desk.create(run_id, task, "deterministic", key, fp, {
                "task_type": task, "department": dept, "implementation_version": ver, "handler": handler,
                "parent_run_id": run_id, "depends_on": deps, "input_refs": refs, "input_fingerprint": fp,
                "config_version": cfg, "code_version": code, "source": source, "session_date": date_s,
                "queued_utc": _now()}, commit=False)
        desk.db.execute("INSERT INTO pipelines (id, experiment, pipeline, created_utc, started_utc, status, job_ids_json) "
                        "VALUES (?,?,?,?,?,?,?)", (run_id, key, "evidence_trace", _now(), _now(), "running", json.dumps(list(ids.values()))))
        desk.db.commit()
        outputs: dict[str, dict] = {}
        store = None
        try:
            if inputs is not None:
                store = st.MonitorStore.__new__(st.MonitorStore)     # read-only handle for daily_report (no schema writes)
                store.db = db
            session = _session(date_s)
            ctx = {"date": date_s, "session": session, "inputs": inputs, "db": db, "store": store, "now": now, "outputs": outputs}
            for task in ORDER:
                jid = ids[task]
                deps = SPEC[task][3]
                if inputs is None:
                    desk.set(jid, "failed" if task == "capture_inventory" else "blocked",
                             error=input_error if task == "capture_inventory" else "upstream failed: ['capture_inventory']")
                    continue
                dep_status = {d: desk.get(ids[d])["status"] for d in deps}
                not_ok = {d: s for d, s in dep_status.items() if s not in ("completed", "skipped")}
                if not_ok:
                    desk.set(jid, "blocked", error=("upstream failed: " if any(s == "failed" for s in not_ok.values())
                                                    else "upstream not completed: ") + str(sorted(not_ok)))
                    continue
                job = desk.get(jid)
                prev = desk.completed(task, key, job["input_key"])
                if prev is not None:                              # same inputs, config, code: reuse, don't recompute
                    prev_out = json.loads(prev["outputs_json"])
                    outputs[task] = prev_out
                    desk.set(jid, "skipped", outputs={"reused_from": prev["id"], "reused_output_fingerprint": _fp(prev_out),
                                                      "result": prev_out}, evidence={"reused": True})
                    continue
                desk.set(jid, "running")
                if HOOK:
                    HOOK(task)
                try:
                    out = (HANDLER_OVERRIDES.get(task) or HANDLERS[task])(ctx)
                except Blocked as exc:
                    desk.set(jid, "blocked", error=f"input not ready: {exc}")
                    continue
                except Exception as exc:                          # recorded, never hidden
                    desk.set(jid, "failed", error=f"{type(exc).__name__}: {exc}"[:2000])
                    continue
                errs = validate_output(task, out)
                if errs:
                    desk.set(jid, "failed", error="invalid output rejected: " + "; ".join(errs)[:2000])
                    continue
                desk.set(jid, "completed", outputs=out, evidence={"output_fingerprint": _fp(out)})
                outputs[task] = out
        finally:
            if db is not None:
                db.close()
        final = [desk.get(i)["status"] for i in ids.values()]
        overall = ("failed" if "failed" in final else "blocked" if "blocked" in final else "completed")
        desk.db.execute("UPDATE pipelines SET status=?, finished_utc=? WHERE id=?", (overall, _now(), run_id))
        desk.db.commit()
        return status(desk, run_id)
    finally:
        if lock is not None:
            _unlock(lock)
        if own:
            desk.close()


def status(desk: JobStore, run_id: str) -> dict:
    p = desk.pipeline(run_id)
    tasks = []
    for jid in p["job_ids"]:
        j = desk.get(jid)
        out = j["outputs"] or {}
        reused = j["status"] == "skipped" and "reused_from" in out
        tasks.append({"task": j["worker"], "department": SPEC[j["worker"]][1], "id": j["id"], "attempt": j["attempt"],
                      "status": "REUSED" if reused else {"completed": "SUCCEEDED", "failed": "FAILED", "blocked": "BLOCKED",
                                                         "running": "RUNNING", "queued": "QUEUED", "cancelled": "CANCELLED"}.get(j["status"], j["status"].upper()),
                      "queued_utc": (j["inputs"] or {}).get("queued_utc") or j["created_utc"], "started_utc": j["started_utc"],
                      "finished_utc": j["finished_utc"], "error": j["error"], "inputs": j["inputs"],
                      "output": out.get("result") if reused else out, "reused_from": out.get("reused_from"),
                      "output_fingerprint": (j["evidence"] or {}).get("output_fingerprint") or out.get("reused_output_fingerprint")})
    return {"run_id": run_id, "session_date": run_id.split(":", 1)[1].split("@")[0], "status": p["status"].upper(),
            "created_utc": p["created_utc"], "finished_utc": p["finished_utc"], "error": p.get("error"), "tasks": tasks}


def recent_runs(desk_db: Path | None = None, limit: int = 20) -> list[dict]:
    p = desk_db or DESK_DB
    if not p.is_file():
        return []
    desk = JobStore(p)
    try:
        ids = [r["id"] for r in desk.db.execute("SELECT id FROM pipelines WHERE pipeline='evidence_trace' ORDER BY rowid DESC LIMIT ?", (limit,))]
        return [status(desk, i) for i in ids]
    finally:
        desk.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Evidence trace for one monitored session (read-only on monitoring records)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--date", required=True)
    sub.add_parser("list")
    args = ap.parse_args(argv)
    if args.cmd == "run":
        res = run_trace(args.date)
        if res["status"] == "BUSY":
            print(res["error"])
            return 1
        print(json.dumps({"run_id": res["run_id"], "status": res["status"],
                          "tasks": {t["task"]: t["status"] + (f" ({t['error']})" if t["error"] else "") for t in res["tasks"]}}, indent=2))
    else:
        for run in recent_runs():
            print(run["run_id"], run["status"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
