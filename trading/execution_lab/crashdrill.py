"""Fresh-process crash drills for the execution core (LOCAL EXECUTION SIMULATION; fake broker; synthetic data).

Each STEP runs in its own new Python process (python -m trading.execution_lab.crashdrill step ...). State lives only in
two files in the drill folder: the append-only ledger (ledger.sqlite) and the fake broker's durable state
(broker.json), which stands in for the external broker. A step may be killed at a named crash point (os._exit, no
cleanup); the next step is a fresh process that must rebuild everything from those files and reconcile.

Every step installs an audit hook that refuses any network connection. Nothing here can reach a real broker.

    python -m trading.execution_lab.crashdrill run-all --out results/execution_lab/crash_drills.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

T0 = datetime(2030, 6, 3, 14, 5, tzinfo=timezone.utc)      # SYNTHETIC session time
SYM, PX, STOP = "SYN", 100.00, 0.50

DRILLS = {
    "before_submission": {
        "title": "Crash before the intent is recorded",
        "steps": [("init", None), ("entry", "before_intent"), ("restart_reconcile", None), ("probe_entry", None)]},
    "after_intent_record": {
        "title": "Crash after the intent is recorded, before its check outcome is recorded",
        "steps": [("init", None), ("entry", "after_intent_record"), ("restart_reconcile", None), ("probe_entry", None)]},
    "after_intent_before_send": {
        "title": "Crash after the intent is recorded and validated, before anything is sent",
        "steps": [("init", None), ("entry", "after_intent_before_send"), ("restart_reconcile", None), ("probe_entry", None)]},
    "after_submit_record_before_send": {
        "title": "Crash after the submission is recorded, before the broker call",
        "steps": [("init", None), ("entry", "after_submit_record_before_send"), ("restart_reconcile", None),
                  ("retry", None), ("probe_entry", None)]},
    "after_send_before_ack": {
        "title": "Crash after a possible send, before the acknowledgement is recorded",
        "steps": [("init", None), ("entry", "after_send_before_ack"), ("restart_reconcile", None), ("retry", None)]},
    "during_partial_fills": {
        "title": "Crash while applying partial fills",
        "steps": [("init", None), ("entry", None), ("broker_partials", None), ("poll", "during_partial_fills"),
                  ("restart_reconcile", None)]},
    "during_cancel": {
        "title": "Crash after the broker accepted a cancel request, before it was recorded",
        "steps": [("init", None), ("entry", None), ("broker_fill10", None), ("cancel", "during_cancel"),
                  ("restart_reconcile", None), ("broker_confirm_cancel", None), ("poll", None)]},
}


# ---------------------------------------------------------------- one step (runs in its own process)

def _no_network(event, args):
    if event in ("socket.connect", "socket.getaddrinfo"):
        raise RuntimeError("crash drill: network access is refused")


def _open(d: Path, restart: bool):
    from trading.execution_lab import ledger as L
    from trading.execution_lab.fake_broker import FakeBroker
    from trading.execution_lab.lab import Clock, Lab, LabConfig
    from trading.execution_lab.policy import LAB_TEST_POLICY
    clock_file = d / "clock.txt"
    t = datetime.fromisoformat(clock_file.read_text()) if clock_file.exists() else T0
    t += timedelta(seconds=1)
    clock_file.write_text(t.isoformat())
    broker = FakeBroker.load(str(d / "broker.json")) if (d / "broker.json").exists() else FakeBroker().save_to(str(d / "broker.json"))
    lab = Lab(L.Ledger(str(d / "ledger.sqlite")), broker, Clock(t), LabConfig(), restart=restart, policy=LAB_TEST_POLICY)
    return lab, broker


def _summary(lab, broker) -> dict:
    st = lab.state()
    return {"pid": os.getpid(),
            "orders": {k: {"state": o.state, "filled": o.filled_qty, "cancelled": o.cancelled_qty, "exec_ids": o.exec_ids}
                       for k, o in st["orders"].items()},
            "positions": {s: v["qty"] for s, v in st["positions"].items()}, "cash": st["cash"],
            "flags": {k: v for k, v in st["flags"].items() if isinstance(v, bool)},
            "broker_submit_calls": broker.submit_calls, "broker_cancel_calls": broker.cancel_calls,
            "broker_orders": {k: {"status": v.status, "filled": v.filled_qty} for k, v in broker.orders.items()},
            "events": len(lab.ledger.events())}


def run_step(d: Path, step: str) -> dict:
    sys.addaudithook(_no_network)
    restart = step not in ("init",) and (d / "ledger.sqlite").exists() and step in ("restart_reconcile",)
    lab, broker = _open(d, restart)
    cid = "lab-synthetic-v1:2030-06-03:0001"
    out = {"step": step}
    if step == "init":
        lab.mark(SYM, PX)
    elif step == "entry":
        out["result"] = lab.request_entry(SYM, 40, PX, STOP)
    elif step == "broker_partials":
        broker.fill(cid, "P1", 10, 100.01)
        broker.fill(cid, "P2", 15, 100.02)
    elif step == "broker_fill10":
        broker.fill(cid, "C1", 10, 100.01)
        lab.poll()
    elif step == "poll":
        out["result"] = lab.poll()
    elif step == "cancel":
        out["result"] = lab.cancel(cid, "drill")
    elif step == "broker_confirm_cancel":
        broker.confirm_cancel(cid, "drill-cancel")
    elif step == "restart_reconcile":
        out["result"] = {k: v for k, v in lab.reconcile().items() if k != "discrepancies"} | {
            "discrepancies": [d_["kind"] for d_ in lab.state()["discrepancies"]]}
    elif step == "retry":
        out["result"] = lab.retry_submit(cid) if cid in lab.state()["orders"] else {"note": "no intent"}
    elif step == "probe_entry":
        out["result"] = lab.entry_check(SYM, 5, PX, STOP, 5)
    out["summary"] = _summary(lab, broker)
    lab.ledger.close()
    return out


# ---------------------------------------------------------------- a whole drill (each step = fresh process)

def run_drill(name: str, d: Path) -> dict:
    steps = []
    for step, crash in DRILLS[name]["steps"]:
        # an allowlist of system variables only: no credentials of any kind reach the drill processes
        env = {k: os.getenv(k) for k in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "PYTHONPATH", "PYTHONHOME", "COMSPEC",
                                         "PATHEXT", "WINDIR") if os.getenv(k) is not None}
        if crash:
            env["XLAB_CRASH_AT"] = crash
        p = subprocess.run([sys.executable, "-m", "trading.execution_lab.crashdrill", "step", "--dir", str(d), "--step", step],
                           env=env, capture_output=True, text=True, timeout=120,
                           cwd=str(Path(__file__).resolve().parents[2]))
        rec = {"step": step, "crash_at": crash, "exit_code": p.returncode}
        if p.returncode == 0:
            rec.update(json.loads(p.stdout.strip().splitlines()[-1]))
        else:
            rec["stderr_tail"] = p.stderr.strip().splitlines()[-3:]
        steps.append(rec)
    final = steps[-1].get("summary", {})
    return {"drill": name, "title": DRILLS[name]["title"], "steps": steps, "final": final,
            "checks": check(name, steps)}


def check(name: str, steps: list[dict]) -> list[dict]:
    """What must hold after recovery, from the fresh processes' own summaries."""
    out = []

    def c(what, ok):
        out.append({"check": what, "passed": bool(ok)})
    crashed = [s for s in steps if s["crash_at"]]
    c("the process died at the crash point (exit code 86)", all(s["exit_code"] == 86 for s in crashed))
    pids = [s.get("summary", {}).get("pid") for s in steps if s["exit_code"] == 0]
    c("every completed step ran in a different process", len(pids) == len(set(pids)))
    final = steps[-1].get("summary", {})
    orders, calls = final.get("orders", {}), final.get("broker_submit_calls", {})
    cid = "lab-synthetic-v1:2030-06-03:0001"
    c("no order was ever submitted twice", all(v <= 1 for v in calls.values()))
    if name == "before_submission":
        c("no intent was recorded and nothing reached the broker", not orders and not calls)
        c("after reconciliation a new entry would pass the gates", steps[-1]["result"]["allowed"])
    elif name == "after_intent_record":
        c("the orphaned intent is closed as EXPIRED UNSENT (BLOCKED), never sent", orders[cid]["state"] == "BLOCKED" and not calls)
        c("after reconciliation a new entry would pass the gates", steps[-1]["result"]["allowed"])
    elif name == "after_intent_before_send":
        c("the unsent intent is closed as EXPIRED UNSENT (BLOCKED), not sent", orders[cid]["state"] == "BLOCKED" and not calls)
        c("after reconciliation a new entry would pass the gates", steps[-1]["result"]["allowed"])
    elif name == "after_submit_record_before_send":
        c("the recorded-but-unsent submission is UNKNOWN (it could be in transit), not rejected",
          orders[cid]["state"] == "UNKNOWN" and not calls)
        c("a retry is refused", steps[3]["result"]["submitted"] is False)
        c("new entries stay blocked", not steps[-1]["result"]["allowed"])
    elif name == "after_send_before_ack":
        c("reconciliation found the order the broker received: ACCEPTED", orders[cid]["state"] == "ACCEPTED")
        c("the broker received exactly one submission and the retry was refused",
          calls.get(cid) == 1 and steps[-1]["result"]["submitted"] is False)
    elif name == "during_partial_fills":
        c("both fills applied exactly once after recovery (25 shares, 2 executions)",
          orders[cid]["filled"] == 25 and sorted(orders[cid]["exec_ids"]) == ["P1", "P2"])
        c("ledger position equals the broker's own record (25)", final["positions"].get(SYM) == 25
          and final["broker_orders"][cid]["filled"] == 25)
    elif name == "during_cancel":
        c("after recovery and the broker's confirmation: CANCELLED with 10 filled, 30 cancelled",
          orders[cid]["state"] == "CANCELLED" and orders[cid]["filled"] == 10 and orders[cid]["cancelled"] == 30)
        c("the cancel request reached the broker once", final["broker_cancel_calls"].get(cid) == 1)
    return out


def run_all(out: Path | None = None) -> dict:
    res = {"recorded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "label": "LOCAL EXECUTION SIMULATION: fresh-process crash drills (fake broker, synthetic data)", "drills": []}
    for name in DRILLS:
        with tempfile.TemporaryDirectory(prefix=f"xlab-{name}-") as td:
            res["drills"].append(run_drill(name, Path(td)))
    res["passed"] = all(c["passed"] for d in res["drills"] for c in d["checks"])
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fresh-process crash drills (offline, fake broker)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("step"); s.add_argument("--dir", required=True); s.add_argument("--step", required=True)
    r = sub.add_parser("run-all"); r.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "step":
        print(json.dumps(run_step(Path(a.dir), a.step), default=str))
        return 0
    res = run_all(Path(a.out) if a.out else None)
    for d in res["drills"]:
        print(f"{'PASS' if all(c['passed'] for c in d['checks']) else 'FAIL'}  {d['drill']}: {d['title']}")
        for c in d["checks"]:
            print(f"    {'ok ' if c['passed'] else 'BAD'} {c['check']}")
    return 0 if res["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
