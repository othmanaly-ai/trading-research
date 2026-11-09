"""Read-only snapshot of the dry run for the dashboard (GET /api/operations).

Opens the operations store read-only. Imports no broker code and loads no credentials, so it is safe
inside the dashboard server. Every value comes from records; with no record a field says so.
"""

import json
from datetime import datetime, timezone

from trading import safety
from trading.operations import ENVIRONMENT, approvals, killswitch, paths, report
from trading.operations import schedule as sc
from trading.operations.store import OpsStore

RUNNER_ALIVE_S = 60


def collect(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    plan = sc.plan_for(sc.et_date(now))
    k = killswitch.state()
    appr = approvals.load_approval()
    out = {"label": report.LABEL, "environment": ENVIRONMENT, "now_utc": now.isoformat(),
           "today": plan.as_dict(), "phase": sc.phase_at(plan, now),
           "approved_strategy": appr.summary(), "approval_reasons": list(appr.reasons),
           "order_gate": {"enabled": safety.order_submission_enabled(), "trading_mode": safety.trading_mode()},
           "kill_switch": {"on": k.on, "reason": k.reason},
           "broker_reconciliation": "not applicable in DRY_RUN: no orders exist and no positions are evaluated"}
    try:
        db = paths.db_path()
    except paths.RuntimeDirRefused as exc:
        return {**out, "available": False, "note": str(exc)}
    if not db.exists():
        return {**out, "available": False, "note": "no dry-run records yet (start: python -m trading.operations run)",
                "records": str(db)}
    store = OpsStore(db, read_only=True)
    try:
        last = store.latest_run()
        runner = None
        if last:
            hb = datetime.fromisoformat(last["heartbeat_utc"]) if last["heartbeat_utc"] else None
            age = None if hb is None else (now - hb).total_seconds()
            runner = {k2: last[k2] for k2 in ("run_id", "kind", "session_date", "started_utc", "start_class", "ended_utc",
                                              "exit_reason", "code_fingerprint", "code_version")}
            runner["heartbeat_age_s"] = None if age is None else round(age)
            runner["alive"] = bool(last["ended_utc"] is None and age is not None and age <= RUNNER_ALIVE_S)
        decisions = store.decisions_for(str(plan.date))
        latest = None
        if decisions:
            d = decisions[-1]
            inputs = json.loads(d["inputs_json"])
            latest = {"minute_utc": d["minute_utc"], "decided_utc": d["decided_utc"], "allowed": bool(d["allowed"]),
                      "reasons": json.loads(d["reasons_json"]), "data": inputs.get("data"), "clock_ok": inputs.get("clock_ok")}
        reports = store.rows("SELECT session_date, version, classification, created_utc FROM reports r1 WHERE version ="
                             " (SELECT MAX(version) FROM reports r2 WHERE r2.session_date = r1.session_date)"
                             " ORDER BY session_date DESC LIMIT 10")
        return {**out, "available": True, "records": str(db), "runner": runner,
                "today_decisions": {"recorded": len(decisions), "expected": len(plan.decision_minutes()),
                                    "allowed": sum(1 for x in decisions if x["allowed"])},
                "latest_decision": latest, "recent_reports": reports, "acceptance": report.acceptance(store, now)}
    finally:
        store.close()
