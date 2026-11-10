"""One inspectable start-up for a trading day (manual; not a service, not a scheduled task).

    .venv\\Scripts\\python.exe -m trading.startup

Steps, each printed as OK / WAIT / WARN / FAIL / SKIP, ending in READY (exit 0) or NOT READY (exit 1):
1. Environment: the project's .venv interpreter; order submission blocked (TRADING_MODE=paper,
   ORDER_SUBMISSION_ENABLED not true).
2. City server on 127.0.0.1:8765: reused if this project's server already answers; otherwise started in
   its OWN visible window and awaited. Anything else on the port is a FAIL.
3. Market monitor: waits until readiness reports exactly one worker with a fresh heartbeat (the
   server's supervisor launches it when the desired state is "running"). A desired state of
   paused/stopped is reported, never overridden.
4. Dry-run runner: reused if healthy; a stalled runner is reported as FAIL (never killed); otherwise
   started in its OWN visible window and awaited until it reports "running", with each start-up step
   shown. A runner that does not reach "running" is NOT READY, with its last step and the fault log.

Duplicate protection: the server detects an existing server, the worker and runner hold OS locks, and
this script reuses healthy processes instead of starting new ones. It never stops or restarts anything.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PORT = 8765
SERVER_WAIT_S, WORKER_WAIT_S, RUNNER_WAIT_S = 60, 90, 120


def _say(tag: str, text: str) -> None:
    print(f"  {tag:<5} {text}", flush=True)


def launch_window(args: list[str]) -> int:
    """Start a process in its own new, visible console window (Windows); returns its pid."""
    flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    p = subprocess.Popen([sys.executable, *args], cwd=str(PROJECT_ROOT), creationflags=flags,
                         stdin=subprocess.DEVNULL, close_fds=True)
    return p.pid


def get_readiness(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/monitor/readiness", timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except ValueError:
            return None
    except (OSError, ValueError):
        return None


def run(port: int = PORT, *, check_only: bool = False, probe_server=None, launch=launch_window, readiness_fn=get_readiness,
        runner_check_fn=None, sleep=time.sleep, now_fn=None, venv_ok=None) -> int:
    from trading import safety
    from trading.dashboard.server import existing_server
    from trading.monitor import readiness
    probe_server = probe_server or existing_server
    runner_check_fn = runner_check_fn or (lambda t: readiness.runner_check(t))
    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    problems: list[str] = []
    print(f"TradingProject start-up check · {now_fn().astimezone().strftime('%a %Y-%m-%d %H:%M:%S %Z')} · "
          "no orders exist; nothing here trades" + (" · CHECK ONLY: nothing will be started" if check_only else ""),
          flush=True)

    print("1. Environment", flush=True)
    in_venv = venv_ok if venv_ok is not None else Path(sys.executable).resolve().is_relative_to((PROJECT_ROOT / ".venv").resolve())
    _say("OK" if in_venv else "FAIL", f"interpreter {sys.executable}" + ("" if in_venv else " is not the project's .venv"))
    if not in_venv:
        problems.append("wrong interpreter: use .venv\\Scripts\\python.exe")
    if safety.order_submission_enabled() or safety.trading_mode() != "paper":
        _say("FAIL", f"order submission must be blocked (TRADING_MODE={safety.trading_mode()}, "
                     f"enabled={safety.order_submission_enabled()})")
        problems.append("order-submission flags unsafe")
    else:
        _say("OK", "order submission blocked (paper mode, ORDER_SUBMISSION_ENABLED not true)")

    print(f"2. City server (http://127.0.0.1:{port})", flush=True)
    found = probe_server(port)
    if found and found.get("unrecognised"):
        _say("FAIL", f"port {port} is used by another program; close it and run this again")
        problems.append("port in use by another program")
    elif found:
        _say("OK", f"already running ({found['mode']}); reused, not restarted")
    elif check_only:
        _say("FAIL", "not running (check only: nothing was started)")
        problems.append("city server not running")
    else:
        pid = launch(["-m", "trading.dashboard.server", "--port", str(port)])
        _say("WAIT", f"started in its own window (pid {pid}); waiting up to {SERVER_WAIT_S} s")
        t0 = time.monotonic()
        while not found and time.monotonic() - t0 < SERVER_WAIT_S:
            sleep(2)
            found = probe_server(port)
        if found and not found.get("unrecognised"):
            _say("OK", "server answering")
        else:
            _say("FAIL", "server did not answer; read the messages in its window")
            problems.append("city server not answering")

    print("3. Market monitor", flush=True)
    worker_ok = False
    if not (found and not found.get("unrecognised")):
        _say("SKIP", "not checked: the city server is not answering")
    else:
        t0 = time.monotonic()
        while True:
            rd = readiness_fn(port)
            checks = {c["id"]: c for c in (rd or {}).get("checks", [])}
            wc, hb, dv = checks.get("worker_count"), checks.get("heartbeat"), checks.get("desired_vs_actual")
            worker_ok = bool(wc and hb and wc["status"] == "PASS" and hb["status"] == "PASS")
            if worker_ok or (dv and "by request" in dv.get("summary", "")) or time.monotonic() - t0 >= WORKER_WAIT_S:
                break
            sleep(5)
        if rd is None:
            _say("FAIL", "readiness unavailable from the server")
            problems.append("readiness unavailable")
        else:
            for c in rd.get("checks", []):
                if c["id"] == "runner":
                    continue               # step 4 checks the runner locally
                tag = {"PASS": "OK", "WARNING": "WARN"}.get(c["status"], c["status"])
                _say(tag, f"{c['label']}: {c['summary']}")
                if c["status"] in ("FAIL", "UNKNOWN") and c["id"] not in ("code_version",):
                    problems.append(f"{c['label']}: {c['status']}")
            if not worker_ok and not any("worker" in p_.lower() for p_ in problems):
                problems.append("monitoring worker not confirmed (one worker with a fresh heartbeat)")

    print("4. Dry-run runner", flush=True)
    rc = runner_check_fn(now_fn())
    summary = rc["summary"]
    if rc["status"] == "PASS":
        _say("OK" if "running" in summary else "SKIP", summary)
    elif "STALLED" in summary or "runner processes found" in summary:
        _say("FAIL", summary)
        _say("", "Do not start a second one. Close that runner's window (Ctrl+C), then run this again.")
        problems.append("dry-run runner stalled or duplicated")
    elif "not required" in summary or "did not complete" in summary:
        _say("SKIP" if rc["status"] == "PASS" else "WARN", summary)
    elif check_only:
        _say("FAIL" if rc["status"] == "FAIL" else "WARN", f"{summary} (check only: nothing was started)")
        if rc["status"] == "FAIL":
            problems.append("dry-run runner not running")
    else:
        pid = launch(["-m", "trading.operations", "run"])
        _say("WAIT", f"started in its own window (pid {pid}); waiting up to {RUNNER_WAIT_S} s for it to report 'running'")
        t0, last = time.monotonic(), None
        while time.monotonic() - t0 < RUNNER_WAIT_S:
            sleep(3)
            rc = runner_check_fn(now_fn())
            step = ((rc.get("detail") or {}).get("runner_startup") or {}).get("step")
            if step and step != last:
                _say("", f"start-up step: {step}")
                last = step
            if rc["status"] == "PASS" or "STALLED" in rc["summary"]:
                break
        if rc["status"] == "PASS":
            _say("OK", rc["summary"])
        else:
            _say("FAIL", f"{rc['summary']}")
            _say("", "Look at the runner's window; see runner.log and runner_faults.log in "
                     "%LOCALAPPDATA%\\TradingProject\\operations")
            problems.append("dry-run runner did not reach 'running'")

    print("", flush=True)
    if problems:
        print("NOT READY:", flush=True)
        for p_ in problems:
            print(f"  - {p_}", flush=True)
        return 1
    from trading.operations import schedule as osc
    t = now_fn()
    plan = osc.plan_for(osc.et_date(t))
    if plan.trading_day and t < plan.close_utc + osc.timedelta(minutes=45):
        print("READY: keep both windows open and this computer awake and on mains power until about "
              f"{(plan.close_utc + osc.timedelta(minutes=45)).astimezone(osc.ET):%H:%M} ET.", flush=True)
    else:
        print("READY (no session in progress now): the monitor makes no API calls while the market is closed; "
              "run this command again before the next open.", flush=True)
    return 0


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m trading.startup", description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--check-only", action="store_true", help="report only; start nothing")
    a = ap.parse_args(argv)
    return run(a.port, check_only=a.check_only)


if __name__ == "__main__":
    sys.exit(main())
