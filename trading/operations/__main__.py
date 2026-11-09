"""Command line for the Milestone 1 dry run. Nothing here submits orders or starts anything in the background.

    python -m trading.operations run            # foreground; one trading day; Ctrl+C stops it
    python -m trading.operations status         # latest run, today's phase, kill switch (no network)
    python -m trading.operations preflight      # run the pre-open checks once now (read-only GETs)
    python -m trading.operations report [--date YYYY-MM-DD]
    python -m trading.operations acceptance     # five-consecutive-PASS tracker
    python -m trading.operations kill-switch on|off --reason "..."
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone

from trading.operations import ENVIRONMENT, killswitch, paths, report
from trading.operations import schedule as sc
from trading.operations.store import OpsStore


def _store():
    return OpsStore(paths.db_path())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m trading.operations", description="Milestone 1 DRY_RUN (no orders)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("status")
    sub.add_parser("preflight")
    r = sub.add_parser("report")
    r.add_argument("--date")
    sub.add_parser("acceptance")
    k = sub.add_parser("kill-switch")
    k.add_argument("action", choices=["on", "off", "status"])
    k.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    try:
        rd = paths.runtime_dir()
    except paths.RuntimeDirRefused as exc:
        print(f"REFUSED: {exc}")
        return 3

    if a.cmd == "kill-switch":
        if a.action == "on":
            killswitch.set_on(a.reason or "no reason given")
        elif a.action == "off":
            if not a.reason.strip():
                print("A --reason is required to turn the kill switch off.")
                return 2
            killswitch.set_off(a.reason)
        s = killswitch.state()
        print(f"kill switch: {'ON' if s.on else 'off'} ({s.reason})")
        return 0

    if a.cmd == "run":
        from trading.monitor.worker import SingleInstanceLock
        from trading.operations.runner import Runner
        lock = SingleInstanceLock(rd / "runner.lock")
        if not lock.acquire():
            print("Another dry-run runner is already running; this one exits (no second runner).")
            return 4
        store = _store()
        print(f"DRY_RUN runner ({ENVIRONMENT}): no orders exist. Records: {paths.db_path()}")
        print("Leave this window open until the report is written (about 20 minutes after the close). Ctrl+C stops it.")
        try:
            return Runner(store, reports_dir=paths.reports_dir()).run()
        finally:
            store.close()
            lock.release()

    if a.cmd == "preflight":
        from trading.operations import checks
        from trading.operations.runner import MONITOR_DB, default_client_factory
        from trading.operations.approvals import APPROVALS_PATH
        store = _store()
        plan = sc.plan_for(sc.et_date(now))
        run_id = f"{now:%Y%m%dT%H%M%S}Z-{os.getpid()}-preflight"
        store.begin_run(run_id, "preflight_only", str(plan.date), ENVIRONMENT, os.getpid(), now.isoformat(), "preflight",
                        "", "", {})
        items = checks.safety_checks(ENVIRONMENT) + checks.local_checks(store, APPROVALS_PATH, MONITOR_DB, now)
        items += checks.broker_checks(default_client_factory, plan, lambda: datetime.now(timezone.utc))[0]
        for name, ok, dep, detail in items:
            store.add_check(run_id, str(plan.date), now.isoformat(), "preflight_only", name, ok, dep, detail)
            print(f"{'OK  ' if ok else 'FAIL'} {name:26s} {json.dumps(detail, default=str)[:150]}")
        store.end_run(run_id, datetime.now(timezone.utc).isoformat(), "preflight only")
        store.close()
        return 0 if all(ok for _, ok, _, _ in items) else 1

    if a.cmd == "status":
        store = _store()
        plan = sc.plan_for(sc.et_date(now))
        last = store.latest_run()
        s = killswitch.state()
        print(json.dumps({"environment": ENVIRONMENT, "now_et": now.astimezone(sc.ET).isoformat(timespec="seconds"),
                          "today": plan.as_dict(), "phase": sc.phase_at(plan, now),
                          "kill_switch": {"on": s.on, "reason": s.reason}, "latest_run": last,
                          "decisions_today": len(store.decisions_for(str(plan.date))), "records": str(paths.db_path())},
                         indent=1, default=str))
        store.close()
        return 0

    if a.cmd == "report":
        store = _store()
        d = date.fromisoformat(a.date) if a.date else sc.et_date(now)
        rep = report.classify(store, d, now)
        if rep["classification"] not in ("PENDING", "NO_SESSION"):
            store.save_report(str(d), rep["classification"], rep)
        print(json.dumps(rep, indent=1, default=str))
        store.close()
        return 0

    if a.cmd == "acceptance":
        store = _store()
        print(json.dumps(report.acceptance(store, now), indent=1, default=str))
        store.close()
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
