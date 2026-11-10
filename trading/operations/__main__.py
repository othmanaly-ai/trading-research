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

# Light imports only at module level: the heavy ones (pandas, exchange calendar) are loaded inside main(),
# after the start-up progress file says so, so a hang during loading is visible from outside.
from trading.operations import ENVIRONMENT, killswitch, paths, progress

report = sc = OpsStore = None
STARTUP_WATCHDOG_S = 60          # start-up taking longer than this writes stack traces to runner_faults.log
LOOP_WATCHDOG_S = 300            # one loop iteration taking longer than this does the same


def _load_heavy():
    global report, sc, OpsStore
    from trading.operations import report as _report
    from trading.operations import schedule as _sc
    from trading.operations.store import OpsStore as _OpsStore
    report, sc, OpsStore = _report, _sc, _OpsStore


def _store():
    return OpsStore(paths.db_path())


def _run(rd) -> int:
    """The dry-run runner with visible start-up steps, a log file and a hang watchdog."""
    import faulthandler
    startup = rd / progress.STARTUP_NAME
    status = rd / progress.STATUS_NAME
    log = open(rd / progress.LOG_NAME, "a", encoding="utf-8")
    faults = open(rd / progress.FAULTS_NAME, "a", encoding="utf-8")

    def echo(msg: str) -> None:
        print(msg, flush=True)
        try:
            log.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} pid {os.getpid()} {msg}\n")
            log.flush()
        except OSError:
            pass

    def step(n: int, text: str) -> None:
        progress.record(startup, "starting", step=f"{n}/4 {text}")
        echo(f"[start-up {n}/4] {text}")

    faults.write(f"--- watchdog armed {datetime.now(timezone.utc).isoformat(timespec='seconds')} pid {os.getpid()}\n")
    faults.flush()
    faulthandler.dump_traceback_later(STARTUP_WATCHDOG_S, repeat=True, file=faults)
    try:
        step(1, "loading code (pandas, exchange calendar)")
        _load_heavy()
        from trading.monitor.worker import SingleInstanceLock
        from trading.operations.runner import Runner
        step(2, "taking the single-runner lock")
        lock = SingleInstanceLock(rd / "runner.lock")
        if not lock.acquire():
            progress.record(startup, "refused", step="2/4 another runner holds the lock")
            echo("FAILED: another dry-run runner is already running; this one exits (no second runner).")
            return 4
        step(3, "opening records")
        store = _store()
        step(4, "starting the session loop")
        progress.record(startup, "handed over", step="4/4 runner started; see runner_status.json")
        echo(f"DRY_RUN runner ({ENVIRONMENT}): no orders exist. Records: {paths.db_path()}")
        echo("OK: start-up complete. Leave this window open until the report is written (about 20 minutes after "
             "the close). Ctrl+C stops it.")
    finally:
        faulthandler.cancel_dump_traceback_later()

    def tick():                      # re-armed every loop iteration: a stuck iteration dumps stack traces
        faulthandler.dump_traceback_later(LOOP_WATCHDOG_S, repeat=False, file=faults)

    try:
        return Runner(store, reports_dir=paths.reports_dir(), echo=echo, status_path=status, on_tick=tick).run()
    finally:
        faulthandler.cancel_dump_traceback_later()
        store.close()
        lock.release()
        log.close()
        faults.close()


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
        rd.mkdir(parents=True, exist_ok=True)
        return _run(rd)
    _load_heavy()

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
