"""Eighteen deterministic SYNTHETIC execution scenarios (s01-s18) for the LOCAL EXECUTION SIMULATION.

Every scenario is a fixed script (no randomness; seed recorded as 0), runs on a controllable clock starting at a
synthetic session (2030-06-03 10:05 ET), uses the synthetic instrument SYN, an in-memory ledger (the restart scenario
uses a temporary file it deletes) and a fresh fake broker. Nothing touches the project's data stores, the network or
any account. Each result carries the full event ledger, a state snapshot after every event, the expectations checked
against the derived records, and the invariant checks.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

from trading.execution_lab import ledger as L
from trading.execution_lab.fake_broker import FakeBroker
from trading.execution_lab.lab import Clock, Lab, LabConfig, stop_report
from dataclasses import replace

from trading.execution_lab.intents import IntentSource
from trading.execution_lab.policy import APPROVED, LAB_TEST_POLICY

T0 = datetime(2030, 6, 3, 14, 5, tzinfo=timezone.utc)      # SYNTHETIC: 10:05 ET on a synthetic session date
SYM, PX, STOP = "SYN", 100.00, 0.50
SEED = 0


def _new(path=None, restart=False, broker=None, clock=None, policy=LAB_TEST_POLICY):
    clock = clock or Clock(T0)
    broker = broker or FakeBroker()
    lab = Lab(L.Ledger(path), broker, clock, LabConfig(), restart=restart, policy=policy)
    if not restart:
        lab.mark(SYM, PX)
    return lab, broker, clock


def _expect(out: list, what: str, ok: bool, detail="") -> None:
    out.append({"check": what, "passed": bool(ok), "detail": str(detail)})


# ---------------------------------------------------------------- scenarios

def s01_normal(x):
    lab, b, c = _new()
    r = lab.request_entry(SYM, 40, PX, STOP)
    c.advance(2); b.ack(r["order_id"], "u1"); b.fill(r["order_id"], "E1", 40, 100.02); lab.poll()
    o = lab.state()["orders"][r["order_id"]]
    _expect(x, "order FILLED with 40 shares", o.state == L.FILLED and o.filled_qty == 40, o.state)
    _expect(x, "remaining quantity is 0", o.remaining_qty == 0)
    st = lab.state()
    _expect(x, "cash = 100,000 - 40 x 100.02", abs(st["cash"] - (100_000 - 4000.8)) < 1e-6, st["cash"])
    return lab


def s02_reject(x):
    lab, b, c = _new()
    b.script_submit("reject:insufficient buying power (synthetic)")
    r = lab.request_entry(SYM, 40, PX, STOP)
    st = lab.state(); o = st["orders"][r["order_id"]]
    _expect(x, "order REJECTED with the broker's reason", o.state == L.REJECTED and "buying power" in o.reasons[0], o.reasons)
    _expect(x, "no position and no pending exposure", not st["positions"] and st["pending_exposure"] == 0)
    rr = lab.retry_submit(r["order_id"])
    _expect(x, "a rejected intent is not resubmitted", not rr["submitted"] and b.submit_calls[r["order_id"]] == 1, rr)
    return lab


def s03_partials(x):
    lab, b, c = _new()
    r = lab.request_entry(SYM, 40, PX, STOP); cid = r["order_id"]
    for i, (q, p) in enumerate(((10, 100.01), (15, 100.02), (15, 100.03)), 1):
        c.advance(5); b.fill(cid, f"P{i}", q, p); lab.poll()
        o = lab.state()["orders"][cid]
        _expect(x, f"after update {i}: filled {sum([10, 15, 15][:i])}, remaining {40 - sum([10, 15, 15][:i])}",
                o.filled_qty == sum([10, 15, 15][:i]) and o.remaining_qty == 40 - sum([10, 15, 15][:i]),
                f"{o.state} {o.filled_qty}/{o.qty}")
    o = lab.state()["orders"][cid]
    _expect(x, "final state FILLED, average price 100.0213 (volume-weighted)", o.state == L.FILLED and
            abs(o.avg_fill_price - (10 * 100.01 + 15 * 100.02 + 15 * 100.03) / 40) < 1e-9, o.avg_fill_price)
    return lab


def s04_dup_order(x):
    lab, b, c = _new()
    b.script_submit("lost_after_record")              # no synchronous acknowledgement: updates must carry the state
    r = lab.request_entry(SYM, 40, PX, STOP); cid = r["order_id"]
    lab.reconcile()                                   # resolves the unknown outcome: ACCEPTED
    b.queue.clear()
    o_bid = b.orders[cid].broker_order_id
    f1 = {"update_id": "exec-D1", "kind": "fill", "client_order_id": cid, "broker_order_id": o_bid, "exec_id": "D1", "qty": 10, "price": 100.01}
    f2 = {"update_id": "exec-D2", "kind": "fill", "client_order_id": cid, "broker_order_id": o_bid, "exec_id": "D2", "qty": 30, "price": 100.02}
    b.orders[cid].executions += [{"exec_id": "D1", "qty": 10, "price": 100.01}, {"exec_id": "D2", "qty": 30, "price": 100.02}]
    b.orders[cid].status = "filled"
    for u in (f2, f1, f1, {"update_id": "a-late", "kind": "broker_ack", "client_order_id": cid, "broker_order_id": o_bid}, f2):
        b.push(u)                                     # out of order, duplicated, and a late acknowledgement
    res = lab.poll()
    o = lab.state()["orders"][cid]
    _expect(x, "filled exactly 40 (two executions), not 70 or 80", o.filled_qty == 40 and len(o.exec_ids) == 2, o.exec_ids)
    _expect(x, "2 duplicate updates stored once, repeats recorded separately",
            res["duplicates"] == 2 and len(lab.ledger.duplicates()) == 2, res)
    _expect(x, "late acknowledgement did not move FILLED back", o.state == L.FILLED and any("late" in i[2] for i in o.ignored),
            o.ignored)
    return lab


def s05_lost(x):
    lab, b, c = _new()
    b.script_submit("lost_after_record")
    r = lab.request_entry(SYM, 40, PX, STOP); cid = r["order_id"]
    st = lab.state(); o = st["orders"][cid]
    _expect(x, "outcome UNKNOWN (not REJECTED)", o.state == L.UNKNOWN, o.state)
    _expect(x, "unknown order counts as pending exposure (40 x 100 = 4,000)", st["pending_exposure"] == 4000.0, st["pending_exposure"])
    rr = lab.retry_submit(cid)
    _expect(x, "automatic resubmission refused; broker received exactly one submit", not rr["submitted"] and b.submit_calls[cid] == 1)
    r2 = lab.request_entry(SYM, 5, PX, STOP)
    _expect(x, "new entry blocked: reconciliation required", not r2["submitted"] and "reconciliation required" in r2["reasons"][0],
            r2["reasons"])
    return lab


def s06_reconcile(x):
    lab, b, c = _new()
    b.script_submit("lost_after_record", "lost_before_record")
    a = lab.request_entry(SYM, 40, PX, STOP)["order_id"]
    c.advance(1)
    bb = lab.request_entry(SYM, 5, PX, STOP)         # blocked: the first outcome is unknown
    _expect(x, "second entry blocked while the first outcome is unknown", not bb["submitted"])
    c.advance(30); b.fill(a, "R1", 40, 100.04); b.queue.clear()     # the broker had it and filled it; updates were lost
    rec = lab.reconcile()
    o = lab.state()["orders"][a]
    _expect(x, "reconciliation found the order by client order id: FILLED 40", o.state == L.FILLED and o.filled_qty == 40, rec)
    _expect(x, "positions agree with the broker; reconciliation complete", rec["ok"] and rec["positions_match"], rec)
    # an order the broker never received
    lab2, b2, c2 = _new()
    b2.script_submit("lost_before_record")
    z = lab2.request_entry(SYM, 40, PX, STOP)["order_id"]
    rec2 = lab2.reconcile()
    o2 = lab2.state()["orders"][z]
    _expect(x, "never-received order: not found, still UNKNOWN (absence is not treated as rejection)",
            o2.state == L.UNKNOWN and rec2["not_found"] == [z] and not rec2["ok"], rec2)
    x.append({"check": "second ledger (never-received case) summary", "passed": True,
              "detail": f"{z}: {o2.state}; reasons {o2.reasons}"})
    return lab


def s07_cancel_race(x):
    lab, b, c = _new()
    a = lab.request_entry(SYM, 40, PX, STOP)["order_id"]
    b.fill(a, "C1", 10, 100.01); lab.poll()
    lab.cancel(a, "test cancel")
    _expect(x, "after the request: CANCEL_PENDING, not CANCELLED", lab.state()["orders"][a].state == L.CANCEL_PENDING)
    c.advance(1); b.fill(a, "C2", 20, 100.02); lab.poll()      # fill arrives while the cancel is pending
    o = lab.state()["orders"][a]
    _expect(x, "fill during pending cancel counted: 30 filled, still CANCEL_PENDING", o.filled_qty == 30 and o.state == L.CANCEL_PENDING)
    c.advance(1); b.confirm_cancel(a, "x1"); lab.poll()
    o = lab.state()["orders"][a]
    _expect(x, "broker confirmation: CANCELLED with 30 filled, 10 cancelled, remaining 0",
            o.state == L.CANCELLED and o.filled_qty == 30 and o.cancelled_qty == 10 and o.remaining_qty == 0)
    # the cancel loses the race completely
    d = lab.request_entry(SYM, 10, PX, STOP)["order_id"]
    lab.cancel(d, "too late"); b.fill(d, "C3", 10, 100.05); b.confirm_cancel(d, "x2"); lab.poll()
    o = lab.state()["orders"][d]
    _expect(x, "cancel lost the race: FILLED, cancel rejected by the broker", o.state == L.FILLED and "already filled" in o.reasons[0], o.reasons)
    _expect(x, "position = 30 + 10", lab.state()["positions"][SYM]["qty"] == 40)
    return lab


def s08_restart(x):
    fd, path = tempfile.mkstemp(suffix=".sqlite", prefix="execlab-")
    os.close(fd)
    try:
        lab, b, c = _new(path)
        a = lab.request_entry(SYM, 40, PX, STOP)["order_id"]
        b.fill(a, "S1", 20, 100.01); lab.poll()
        before = L.order_dict(lab.state()["orders"][a])
        lab.ledger.close()                                       # the process stops
        c.advance(120); b.fill(a, "S2", 10, 100.02)              # meanwhile the broker filled 10 more
        lab2 = Lab(L.Ledger(path), b, c, LabConfig(), restart=True, policy=LAB_TEST_POLICY)
        o = lab2.state()["orders"][a]
        _expect(x, "after restart the outstanding order is rebuilt from the ledger (20/40, remaining 20)",
                o.state == L.PARTIALLY_FILLED and o.filled_qty == 20 and o.remaining_qty == 20, f"{o.state} {o.filled_qty}")
        r = lab2.request_entry(SYM, 5, PX, STOP)
        _expect(x, "entries blocked until reconciliation after restart", not r["submitted"] and "restart" in r["reasons"][0], r["reasons"])
        rec = lab2.reconcile()
        o = lab2.state()["orders"][a]
        _expect(x, "reconciliation applies the fill made while down: 30/40, broker submit count still 1",
                o.filled_qty == 30 and b.submit_calls[a] == 1 and rec["ok"], rec)
        r = lab2.request_entry(SYM, 5, PX, STOP)
        _expect(x, "after reconciliation the restart block is gone, but 30 shares without an active stop for longer than "
                   "the policy time still block new entries", not r["submitted"] and not any("restart" in s for s in r["reasons"])
                and any(s.startswith("UNPROTECTED") for s in r["reasons"]), r["reasons"])
        x.append({"check": "state before the stop", "passed": True, "detail": f"{before['state']} {before['filled_qty']}/{before['qty']}"})
        events = lab2.ledger.events()
        lab2.ledger.close()
        mem = L.Ledger()                                          # keep the result in memory; delete the temp file
        for e in events:
            mem.append(e["event_id"], e["ts_utc"], e["kind"], e["source"], e["payload"], e["order_id"], e["config_version"])
        lab2.ledger = mem
        return lab2
    finally:
        os.remove(path)


def s09_stale(x):
    lab, b, c = _new()
    r = lab.request_entry(SYM, 20, PX, STOP, data_age_s=420)
    _expect(x, "entry blocked: market data stale (420 s)", not r["submitted"] and any("stale" in s for s in r["reasons"]), r["reasons"])
    _expect(x, "nothing reached the broker", not b.submit_calls)
    return lab


def s10_limits(x):
    lab, b, c = _new()
    a = lab.request_entry(SYM, 50, PX, STOP)["order_id"]; b.fill(a, "L1", 50, 100.00); lab.poll()
    p = lab.request_entry(SYM, 40, PX, STOP)                 # pending entry (accepted, not filled)
    r = lab.request_entry(SYM, 30, PX, STOP)
    _expect(x, "third entry blocked by risk: pending entries count toward gross exposure / positions",
            not r["submitted"] and any("risk" in s for s in r["reasons"]), r["reasons"])
    lab.cancel(p["order_id"], "free the slot"); b.confirm_cancel(p["order_id"], "y1"); lab.poll()
    lab.mark(SYM, 89.99)                                      # synthetic loss: 50 x 10.01 = 500.5 = 0.50% of equity
    r2 = lab.request_entry(SYM, 5, 89.99, STOP)
    _expect(x, "daily loss limit (0.50%, owner baseline) blocks new entries", not r2["submitted"] and
            any("daily loss" in s for s in r2["reasons"]), r2["reasons"])
    return lab


def s11_estop(x):
    lab, b, c = _new()
    a = lab.request_entry(SYM, 20, PX, STOP)["order_id"]; b.fill(a, "K1", 20, 100.00)
    p = lab.request_entry(SYM, 30, PX, STOP)["order_id"]; b.fill(p, "K2", 10, 100.01)
    lab.poll()
    rep = lab.emergency_stop("synthetic emergency")
    _expect(x, "right after the stop: INCOMPLETE (cancellation not yet confirmed)", rep["overall"] == "INCOMPLETE", rep["unresolved"])
    r = lab.request_entry(SYM, 1, PX, STOP)
    _expect(x, "new entries blocked by the emergency stop", not r["submitted"] and "emergency stop" in r["reasons"][0])
    c.advance(2); b.fill(p, "K3", 5, 100.02); b.confirm_cancel(p, "z1"); lab.poll()
    lab.reconcile()
    rep = lab.stop_report()
    _expect(x, "cancellation confirmed with 15 filled; reconciliation CONFIRMED",
            any(r["confirmation"].startswith("CONFIRMED") for r in rep["cancellations"]) and
            [s for s in rep["steps"] if s["step"] == "Confirm reconciliation"][0]["status"] == "CONFIRMED", rep["steps"])
    _expect(x, "still INCOMPLETE: 35 shares held; reduce/close not performed (no approved policy)",
            rep["overall"] == "INCOMPLETE" and rep["positions"][SYM]["qty"] == 35, rep["unresolved"])
    return lab


def s12_estop_unavailable(x):
    lab, b, c = _new()
    a = lab.request_entry(SYM, 30, PX, STOP)["order_id"]; b.fill(a, "U1", 10, 100.00); lab.poll()
    b.available = False
    rep = lab.emergency_stop("synthetic emergency during broker outage")
    _expect(x, "cancellation request FAILED (broker unreachable); not reported as cancelled",
            rep["cancellations"][0]["confirmation"].startswith("NOT DELIVERED") and lab.state()["orders"][a].state == L.PARTIALLY_FILLED,
            rep["cancellations"])
    lab.reconcile()
    rep = lab.stop_report()
    _expect(x, "reconciliation FAILED; stop INCOMPLETE; remaining exposure shown (10 held + 20 pending)",
            rep["overall"] == "INCOMPLETE" and "FAILED" in [s for s in rep["steps"] if s["step"] == "Confirm reconciliation"][0]["status"]
            and abs(rep["remaining_exposure"] - 3000.0) < 1e-6, rep["remaining_exposure"])
    c.advance(60); b.available = True                       # the broker comes back: the stop is retried, not assumed
    lab.cancel(a, "emergency stop retry"); b.confirm_cancel(a, "w1"); lab.poll(); lab.reconcile()
    rep = lab.stop_report()
    _expect(x, "after recovery: cancel confirmed, reconciled; still INCOMPLETE only because 10 shares are held",
            rep["overall"] == "INCOMPLETE" and rep["unresolved"] == [u for u in rep["unresolved"] if "open position" in u], rep["unresolved"])
    return lab


def s13_bracket_partial(x):
    lab, b, c = _new(policy=replace(LAB_TEST_POLICY, protection_method="bracket"))
    a = lab.request_entry(SYM, 40, PX, STOP)["order_id"]
    leg = f"{a}:stop"
    st = lab.state()
    _expect(x, "bracket stop leg recorded as HELD (inactive), not as protection", st["orders"][leg].state == L.HELD)
    b.fill(a, "B1", 25, 100.01); lab.poll()
    pr = lab.state()["protection"][0]
    _expect(x, "25 filled, 0 protected, 25 unprotected while the entry is partly filled (documented: legs wait for a complete fill)",
            pr["position"] == 25 and pr["protected_qty"] == 0 and pr["unprotected_qty"] == 25 and pr["held_inactive_qty"] == 40, pr)
    c.advance(45)
    r = lab.request_entry(SYM, 5, PX, STOP)
    _expect(x, "after 45 s unprotected (limit 30, LAB TEST VALUE) new entries are blocked", not r["submitted"] and
            any(s.startswith("UNPROTECTED") for s in r["reasons"]), r["reasons"])
    _expect(x, "attention lists the HELD leg as 'not protection'", any("HELD" in a2["what"] for a2 in lab.attention()), lab.attention())
    b.fill(a, "B2", 15, 100.02); lab.poll()
    pr = lab.state()["protection"][0]
    _expect(x, "entry complete: the leg becomes active, 40 protected, 0 unprotected",
            lab.state()["orders"][leg].state == L.ACCEPTED and pr["protected_qty"] == 40 and pr["unprotected_qty"] == 0, pr)
    _expect(x, "the unprotected interval is kept in the record", len(lab.state()["unprotected_intervals"]) == 1,
            lab.state()["unprotected_intervals"])
    return lab


def s14_stop_after_fill(x):
    lab, b, c = _new()
    a = lab.request_entry(SYM, 40, PX, STOP)["order_id"]
    b.fill(a, "F1", 20, 100.00); lab.poll()
    r = lab.protect(a)
    _expect(x, "protect refused while the entry can still fill (a stop sell next to an open buy is wash-trade rejected)",
            not r["submitted"] and "final" in r["reasons"][0], r)
    lab.cancel(a, "stop working the remainder"); c.advance(2); b.confirm_cancel(a, "k1"); lab.poll()
    r = lab.protect(a)
    st = lab.state()
    pr = st["protection"][0]
    _expect(x, "after the cancel is CONFIRMED a stop for the 20 filled shares is accepted: 20 protected",
            r["submitted"] is True and pr["protected_qty"] == 20 and pr["unprotected_qty"] == 0, (r, pr))
    _expect(x, "the unprotected interval (fill to stop acknowledgement) is recorded", st["unprotected_intervals"],
            st["unprotected_intervals"])
    return lab


def s15_missing_policy(x):
    lab, b, c = _new(policy=APPROVED)
    r = lab.request_entry(SYM, 10, PX, STOP)
    _expect(x, "no approved execution policy: entry BLOCKED with each unset field named, nothing sent",
            not r["submitted"] and sum(s.startswith("POLICY UNSET") for s in r["reasons"]) == 8 and not b.submit_calls, r["reasons"])
    r2 = lab.request_entry(SYM, 10, PX, STOP, source=IntentSource("strategy", "any-strategy", "v1"))
    _expect(x, "a strategy intent is refused: NO APPROVED ACTIVE STRATEGY", any("NO APPROVED ACTIVE STRATEGY" in s for s in r2["reasons"]),
            r2["reasons"])
    rec = lab.reconcile()
    _expect(x, "risk-reducing work still runs without policy: reconciliation completes", rec["ok"], rec)
    return lab


def s16_manual_mismatch(x):
    lab, b, c = _new()
    a = lab.request_entry(SYM, 20, PX, STOP)["order_id"]; b.fill(a, "G1", 20, 100.00); lab.poll()
    b.manual_trade(SYM, "buy", 5, 100.50)
    b.manual_order(SYM, "buy", 7)
    rec = lab.reconcile()
    kinds = sorted(d["kind"] for d in rec["discrepancies"])
    _expect(x, "manual activity found: position, foreign order and cash discrepancies; not corrected",
            kinds == ["cash", "foreign_order", "position"] and lab.state()["positions"][SYM]["qty"] == 20, rec["discrepancies"])
    r = lab.request_entry(SYM, 1, PX, STOP)
    _expect(x, "entries blocked while discrepancies are unresolved", not r["submitted"] and
            any("discrepancies" in s for s in r["reasons"]), r["reasons"])
    return lab


def s17_ack_not_fill(x):
    lab, b, c = _new()
    a = lab.request_entry(SYM, 30, PX, STOP)["order_id"]
    b.ack(a, "q1"); lab.poll()
    st = lab.state()
    _expect(x, "acknowledged order: ACCEPTED, 0 filled, no position, 3,000 pending exposure",
            st["orders"][a].state == L.ACCEPTED and st["orders"][a].filled_qty == 0 and not st["positions"]
            and st["pending_exposure"] == 3000.0)
    rec = lab.reconcile()
    _expect(x, "reconciliation clean: positions and cash agree (broker 100,000.00)", rec["ok"] and rec["broker_cash"] == 100000.0, rec)
    return lab


def s18_missing_at_broker(x):
    lab, b, c = _new()
    a = lab.request_entry(SYM, 20, PX, STOP)["order_id"]
    b.ack(a, "m1"); lab.poll()
    b.forget(a)                                       # SIMULATION: the broker has no record of this client order id
    rec = lab.reconcile()
    o = lab.state()["orders"][a]
    _expect(x, "reconciliation is NOT complete: the ledger's live order is missing at the broker",
            not rec["ok"] and any(d["kind"] == "order_missing_at_broker" and d["order_id"] == a for d in rec["discrepancies"]),
            rec["discrepancies"])
    _expect(x, "the order is not assumed cancelled or filled: it stays ACCEPTED, 20 shares pending exposure",
            o.state == L.ACCEPTED and lab.state()["pending_exposure"] == 2000.0, o.state)
    r = lab.request_entry(SYM, 1, PX, STOP)
    _expect(x, "new entries blocked until an owner resolves the discrepancy", not r["submitted"] and
            any("discrepancies" in s for s in r["reasons"]), r["reasons"])
    _expect(x, "attention lists the discrepancy for owner review",
            any("order_missing_at_broker" in a2["what"] for a2 in lab.attention()), lab.attention())
    return lab


SCENARIOS = [
    ("s01", "Normal acceptance and fill", s01_normal),
    ("s02", "Broker rejection", s02_reject),
    ("s03", "Partial fills over several updates", s03_partials),
    ("s04", "Duplicate and out-of-order updates", s04_dup_order),
    ("s05", "Connection lost after submission, before acknowledgement", s05_lost),
    ("s06", "Reconciliation after an unknown outcome", s06_reconcile),
    ("s07", "Cancellation racing with fills", s07_cancel_race),
    ("s08", "Process restart with an outstanding order", s08_restart),
    ("s09", "Stale market data blocks new entries", s09_stale),
    ("s10", "Exposure and daily-loss limits block orders", s10_limits),
    ("s11", "Emergency stop with outstanding orders", s11_estop),
    ("s12", "Broker unavailable during emergency-stop handling", s12_estop_unavailable),
    ("s13", "Bracket entry partly filled: stop leg held, shares unprotected", s13_bracket_partial),
    ("s14", "Stop after fill: protect only after a confirmed cancel", s14_stop_after_fill),
    ("s15", "Missing policy and unapproved strategy refuse entries", s15_missing_policy),
    ("s16", "Manual account activity: discrepancies shown, not corrected", s16_manual_mismatch),
    ("s17", "An acknowledgement is not a fill", s17_ack_not_fill),
    ("s18", "Live order missing at the broker: discrepancy, not completion", s18_missing_at_broker),
]


# ---------------------------------------------------------------- invariants (from the records only)

def invariants(events: list[dict], start_cash: float) -> list[dict]:
    st = L.derive(events, start_cash)
    out = []
    fills = [e for e in events if e["kind"] == "fill"]
    ids = [e["payload"]["exec_id"] for e in fills]
    out.append({"check": "each execution id stored once (duplicates never duplicate fills)", "passed": len(ids) == len(set(ids))})
    ok = all(o.filled_qty + o.remaining_qty + o.cancelled_qty == o.qty or (o.state in (L.REJECTED, L.BLOCKED) and o.filled_qty == 0)
             for o in st["orders"].values())
    out.append({"check": "filled + remaining + cancelled = ordered (or 0 filled when rejected/blocked)", "passed": ok})
    out.append({"check": "no fill exceeds its order quantity", "passed": all(o.filled_qty <= o.qty for o in st["orders"].values())})
    # cash recomputed independently from fill events
    by = {e["order_id"]: e for e in events if e["kind"] == "intent_created"}
    cash = start_cash
    pos = {}
    for e in fills:
        side = by[e["order_id"]]["payload"]["side"]
        v = e["payload"]["qty"] * e["payload"]["price"]
        cash += -v if side == "buy" else v
        pos[by[e["order_id"]]["payload"]["symbol"]] = pos.get(by[e["order_id"]]["payload"]["symbol"], 0) + (1 if side == "buy" else -1) * e["payload"]["qty"]
    cash -= st["fees"]
    out.append({"check": "cash = start - buys + sells - fees (recomputed from fills)", "passed": abs(cash - st["cash"]) < 1e-6})
    out.append({"check": "positions = signed sum of fills", "passed": {k: v for k, v in pos.items() if v} ==
                {s: v["qty"] for s, v in st["positions"].items()}})
    live_entries = [o for o in st["orders"].values() if o.purpose == "entry" and o.state in L.LIVE and o.remaining_qty > 0]
    out.append({"check": "every live entry (incl. UNKNOWN) counts toward pending exposure",
                "passed": {x["order_id"] for x in st["pending_entries"]} == {o.order_id for o in live_entries}})
    out.append({"check": "no order shows an invalid state transition", "passed": not any(o.anomalies for o in st["orders"].values())})
    rep = stop_report(st, events)
    if rep.get("active"):
        out.append({"check": "emergency stop reports COMPLETE only with nothing unresolved",
                    "passed": rep["overall"] != "COMPLETE" or (not rep["unresolved"] and not rep["live_orders"])})
    return out


def _snapshot(st: dict, events: list[dict]) -> dict:
    return {"orders": {k: {"state": o.state, "filled_qty": o.filled_qty, "remaining_qty": o.remaining_qty,
                           "cancelled_qty": o.cancelled_qty} for k, o in st["orders"].items()},
            "cash": round(st["cash"], 2), "equity": round(st["equity"], 2),
            "positions": {s: v["qty"] for s, v in st["positions"].items()},
            "held_exposure": round(st["held_exposure"], 2), "pending_exposure": round(st["pending_exposure"], 2),
            "flags": st["flags"], "protection": st["protection"], "discrepancies": len(st["discrepancies"])}


def run(sid: str) -> dict:
    title, fn = next((t, f) for s, t, f in SCENARIOS if s == sid)
    checks: list = []
    lab = fn(checks)
    events = lab.ledger.events()
    st = L.derive(events, lab.cfg.start_cash)
    snaps = [_snapshot(L.derive(events[: i + 1], lab.cfg.start_cash), events[: i + 1]) for i in range(len(events))]
    inv = invariants(events, lab.cfg.start_cash)
    unknown = [o.order_id for o in st["orders"].values() if o.state == L.UNKNOWN]
    unresolved = ([f"{o}: outcome unknown, reconciliation required" for o in unknown] +
                  [f"{o.order_id}: cancellation requested, not confirmed" for o in st["orders"].values() if o.state == L.CANCEL_PENDING])
    rep = stop_report(st, events)
    if rep.get("active"):
        unresolved += [u for u in rep["unresolved"] if u not in unresolved]
    return {
        "id": sid, "title": title, "seed": SEED, "config_version": lab.cv, "synthetic": True,
        "passed": all(c["passed"] for c in checks) and all(c["passed"] for c in inv),
        "expectations": checks, "invariants": inv,
        "events": [{k: e[k] for k in ("seq", "event_id", "ts_utc", "kind", "order_id", "source", "config_version")} |
                   {"payload": e["payload"]} for e in events],
        "duplicates": lab.ledger.duplicates(), "snapshots": snaps,
        "orders": [L.order_dict(o) for o in st["orders"].values()],
        "cash": round(st["cash"], 2), "equity": round(st["equity"], 2), "fees": round(st["fees"], 4),
        "positions": st["positions"], "held_exposure": round(st["held_exposure"], 2),
        "pending_exposure": round(st["pending_exposure"], 2), "gross_exposure": round(st["gross_exposure"], 2),
        "flags": st["flags"], "risk_rejections": [{"order_id": o.order_id, "reasons": o.reasons} for o in st["orders"].values()
                                                  if o.state == L.BLOCKED],
        "unknown_outcomes": unknown, "unresolved": unresolved, "emergency_stop": rep,
        "broker_submit_calls": dict(lab.broker.submit_calls), "broker_cancel_calls": dict(lab.broker.cancel_calls),
        "protection": st["protection"], "unprotected_intervals": st["unprotected_intervals"],
        "discrepancies": st["discrepancies"], "attention": lab.attention(), "policy_label": lab.policy.label,
        "policy": lab.policy.table(), "intents": _intents(events),
    }


def _intents(events: list[dict]) -> list[dict]:
    """Every intent with its validation outcome, straight from the ledger."""
    out = {}
    for e in events:
        p, oid = e["payload"], e["order_id"]
        if e["kind"] == "intent_created":
            out[oid] = {"order_id": oid, "seq": e["seq"], "purpose": p.get("purpose"), "symbol": p.get("symbol"),
                        "side": p.get("side"), "qty": p.get("qty"), "spec": p.get("spec"),
                        "source": (p.get("source") or {}).get("kind", "broker leg" if e["source"] == "broker" else "lab"),
                        "validation": "PENDING", "reasons": []}
        elif oid in out and e["kind"] == "validated":
            out[oid]["validation"] = "VALIDATED"
        elif oid in out and e["kind"] == "blocked":
            out[oid]["validation"], out[oid]["reasons"] = "BLOCKED", p.get("reasons", [])
        elif oid in out and e["kind"] == "leg_held":
            out[oid]["validation"] = "CREATED BY BROKER (HELD)"
        elif oid in out and e["kind"] == "intent_expired_unsent":
            out[oid]["validation"] += " · EXPIRED UNSENT"
    return list(out.values())


def run_all() -> list[dict]:
    return [run(s) for s, _, _ in SCENARIOS]


POLICY_GAPS = [
    "Breach action after a daily-loss or drawdown block: hold positions under protective stops, or flatten (roadmap: owner decision).",
    "Emergency-stop exposure handling: whether and how to reduce or close positions; the lab never liquidates automatically.",
    "Stale-data threshold and recovery rule (roadmap: 'freshness passes for N consecutive minutes'); the lab uses 180 s as a LAB PARAMETER.",
    "Unknown-outcome resolution: how many lookups, how long, and when absence at the broker may count as 'never received'.",
    "Requested size above the allowed size: refuse (lab behaviour) or resize down to the cap.",
    "Cancel-pending timeout and escalation when a broker confirmation never arrives.",
    "Remainder of a partially filled entry: keep working, cancel at a deadline, or cancel immediately.",
    "Maximum orders per day and the trading-hours window for entries (roadmap Milestone 3 decision).",
    "Order type and time-in-force, and whether broker-side protective stops are placed at entry.",
    "Emergency-stop reset: who may clear it and what must be reconciled first.",
    "Whether the real broker rejects a reused client order id (must be verified in its paper documentation, not assumed).",
    "Detection and handling of manual positions or orders made outside the system.",
]


# What is enforced by code (and where the evidence is) versus proposed, unset or missing. Never infer "enforced" from a
# document or an animation: each ENFORCED row names the code path and the test that proves it.
CONTROLS = [
    {"control": "Order-submission guard (trading.safety: paper mode plus an explicit enable flag)", "status": "ENFORCED",
     "evidence": "trading/safety.py; the offline order adapter calls it before every write (adapter tests)"},
    {"control": "No broker-write networking anywhere in trading/", "status": "ENFORCED",
     "evidence": "only a fixture transport exists; a repository-wide test refuses any HTTP write call (adapter tests)"},
    {"control": "Approved-strategy gate", "status": "ENFORCED",
     "evidence": "config/approved_strategies.json is empty: every strategy intent is refused (NO APPROVED ACTIVE STRATEGY)"},
    {"control": "Execution policy required before any entry", "status": "ENFORCED",
     "evidence": "every APPROVED field is UNSET, so every real entry is blocked (tests/test_execution_core.py)"},
    {"control": "Journal before broker call; no resubmission; unknown outcome blocks entries", "status": "ENFORCED (offline simulation)",
     "evidence": "scenarios s05, s06; fresh-process crash drills (tests/test_execution_recovery.py)"},
    {"control": "Reconciliation gate (incl. an order the broker has no record of)", "status": "ENFORCED (offline simulation)",
     "evidence": "scenarios s06, s08, s16; tests/test_execution_core.py"},
    {"control": "Owner risk baseline (size, exposure incl. pending/unknown, daily loss, drawdown)", "status": "ENFORCED (offline simulation)",
     "evidence": "trading/risk.py OWNER_BASELINE_2026_11_03 reused unchanged; scenario s10"},
    {"control": "Maximum unprotected time (A3)", "status": "PROPOSED / UNSET",
     "evidence": "enforced only with a policy value; the approved value is UNSET, so entries are blocked instead"},
    {"control": "Unknown-outcome and cancellation escalation timers (A4, A5)", "status": "PROPOSED / UNSET",
     "evidence": "shown as attention items only; no timer is approved"},
    {"control": "Emergency stop: block, cancel, confirm, reconcile", "status": "ENFORCED (offline simulation)",
     "evidence": "scenarios s11, s12; it never reports COMPLETE while anything is unresolved"},
    {"control": "Emergency exposure action (A6) / automatic liquidation", "status": "UNSET / NOT IMPLEMENTED",
     "evidence": "no default chosen; no automatic liquidation code exists"},
    {"control": "Kill switch (trading.operations) checked by the execution core", "status": "NOT CONNECTED",
     "evidence": "the dry run's kill switch is not read by trading/execution_lab or the adapter (plan C7)"},
    {"control": "Test-loss limit for a paper test", "status": "NOT DEFINED",
     "evidence": "owner decision; no code or record defines it"},
]


def api(sid: str | None = None) -> dict:
    """Payload for /api/execution-lab: every scenario's summary plus one scenario in full. Computed in memory."""
    from trading.execution_lab.lab import LabConfig
    results = run_all()
    by = {r["id"]: r for r in results}
    sel = by.get(sid or "s01") or by["s01"]
    cfg = LabConfig()
    return {
        "mode": "LOCAL_EXECUTION_SIMULATION",
        "label": "LOCAL EXECUTION SIMULATION · fake in-memory broker · synthetic instrument, prices and clock",
        "notice": "Not a broker integration, not a paper account, not a validated strategy. No order exists anywhere; "
                  "nothing here leaves this computer.",
        "config": {"version": cfg.version(), "limits": cfg.limits_name, "cost_model": cfg.cost_model,
                   "start_cash": cfg.start_cash, "max_data_age_s": cfg.max_data_age_s,
                   "max_data_age_note": "LAB PARAMETER, not an approved policy", "session": cfg.session + " (synthetic)"},
        "scenarios": [{"id": r["id"], "title": r["title"], "passed": r["passed"], "events": len(r["events"]),
                       "checks": len(r["expectations"]) + len(r["invariants"]),
                       "failed_checks": sum(1 for c in r["expectations"] + r["invariants"] if not c["passed"]),
                       "unknown_outcomes": len(r["unknown_outcomes"]), "unresolved": len(r["unresolved"]),
                       "risk_rejections": len(r["risk_rejections"]),
                       "emergency_stop": r["emergency_stop"].get("overall") if r["emergency_stop"].get("active") else None}
                      for r in results],
        "selected": sel,
        "policy_gaps": POLICY_GAPS,
        "controls": CONTROLS,
        "approved_policy": __import__("trading.execution_lab.policy", fromlist=["APPROVED"]).APPROVED.table(),
        "strategy_status": "NO APPROVED ACTIVE STRATEGY",
    }
