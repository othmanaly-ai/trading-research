"""Execution rehearsal against the FAKE broker. LOCAL EXECUTION SIMULATION only: synthetic instrument, synthetic
prices, a controllable clock, an in-memory (or caller-supplied temporary) ledger.

Gates before any new entry, in order (all reasons are recorded, the intent is persisted as BLOCKED):
  emergency stop · reconciliation required (unknown outcome, or a restart not yet reconciled) · stale market data
  (LAB PARAMETER, not an approved policy) · trading.risk.RiskState (daily loss block, drawdown halt) ·
  trading.risk.size_position with OWNER_BASELINE_2026_11_03, where gross exposure and position count include pending,
  partially filled and unknown-outcome entries. A request larger than the allowed size is refused, not resized
  (resizing is a policy decision).

Client order ids are deterministic: <strategy version>:<session>:<intent sequence>. A submission whose outcome is
unknown is never resubmitted; only reconciliation (a lookup by client order id) can resolve it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from trading.costs import BASE, CostModel
from trading.execution_lab import ledger as L
from trading.execution_lab.fake_broker import BrokerUnavailable, ConnectionLost, FakeBroker
from trading.risk import OWNER_BASELINE_2026_11_03, RiskLimits, RiskState, size_position


class Clock:
    """Controllable clock (synthetic time)."""

    def __init__(self, start: datetime):
        self.t = start

    def now(self) -> datetime:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += timedelta(seconds=seconds)

    def iso(self) -> str:
        return self.t.isoformat(timespec="seconds")


@dataclass(frozen=True)
class LabConfig:
    start_cash: float = 100_000.0               # the owner baseline's synthetic starting equity
    strategy_version: str = "lab-synthetic-v1"   # not a strategy: a label for client order ids
    session: str = "2030-06-03"                  # SYNTHETIC session date
    max_data_age_s: int = 180                    # LAB PARAMETER, not an approved policy (stale-feed threshold undecided)
    median_minute_volume: float = 1_000_000.0    # synthetic
    limits_name: str = "OWNER_BASELINE_2026_11_03"
    cost_model: str = "base"
    limits: RiskLimits = field(default=OWNER_BASELINE_2026_11_03, compare=False)
    costs: CostModel = field(default=BASE, compare=False)

    def version(self) -> str:
        d = {k: v for k, v in asdict(self).items() if k not in ("limits", "costs")}
        d["limits"], d["costs"] = asdict(self.limits), asdict(self.costs)
        return "lab-" + hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:12]


class Lab:
    def __init__(self, ledger: L.Ledger, broker: FakeBroker, clock: Clock, config: LabConfig | None = None,
                 restart: bool = False):
        self.ledger, self.broker, self.clock = ledger, broker, clock
        self.cfg = config or LabConfig()
        self.cv = self.cfg.version()
        n = len([e for e in ledger.events() if e["kind"] == "process_start"])
        self._evt("process_start", {"restart": restart, "note": "restart: outstanding orders are rebuilt from the "
                                    "ledger; entries stay blocked until reconciliation" if restart else "fresh start"},
                  event_id=f"start:{n + 1}")

    # ---------------------------------------------------------------- records
    def _evt(self, kind: str, payload: dict, order_id: str | None = None, event_id: str | None = None,
             source: str = "local") -> bool:
        eid = event_id or f"{kind}:{order_id or '-'}:{len(self.ledger.events()) + 1}"
        return self.ledger.append(eid, self.clock.iso(), kind, source, payload, order_id, self.cv)

    def state(self) -> dict:
        return L.derive(self.ledger.events(), self.cfg.start_cash, costs=self.cfg.costs)

    def mark(self, symbol: str, price: float) -> None:
        self._evt("mark", {"symbol": symbol, "price": price, "synthetic": True})

    # ---------------------------------------------------------------- risk (reused definitions, state from records)
    def risk_state(self) -> RiskState:
        evs = self.ledger.events()
        rs = RiskState(self.cfg.limits, peak_equity=self.cfg.start_cash)
        rs.start_day(self.cfg.session, self.cfg.start_cash)
        for i, e in enumerate(evs):
            if e["kind"] in ("mark", "fill"):
                rs.observe(self.cfg.session, L.derive(evs[: i + 1], self.cfg.start_cash, costs=self.cfg.costs)["equity"])
        return rs

    def entry_check(self, symbol: str, qty: int, ref_price: float, stop_distance: float, data_age_s: float) -> dict:
        st = self.state()
        reasons = []
        if st["flags"]["emergency_stop"]:
            reasons.append("emergency stop active: new entries blocked")
        if st["flags"]["reconciliation_required"]:
            why = [o.order_id for o in st["orders"].values() if o.state == L.UNKNOWN]
            reasons.append("reconciliation required before any new entry ("
                           + (f"unknown outcome: {', '.join(why)}" if why else "restart not yet reconciled") + ")")
        if data_age_s > self.cfg.max_data_age_s:
            reasons.append(f"market data stale: newest bar {int(data_age_s)} s old > {self.cfg.max_data_age_s} s "
                           "(LAB PARAMETER, not an approved threshold)")
        rb = self.risk_state().block_reason(st["equity"], self.cfg.session)
        if rb:
            reasons.append(rb)
        c = self.cfg.costs
        rt_cost = ref_price * (2 * c.per_side_bp + c.sell_fee_bp) / 1e4
        shares, binding = size_position(self.cfg.limits, st["equity"], ref_price, stop_distance,
                                        self.cfg.median_minute_volume, rt_cost, gross_in_use=st["gross_exposure"],
                                        positions_in_use=st["positions_in_use"])
        if qty > shares:
            reasons.append(f"risk: requested {qty} shares > allowed {shares} (binding cap: {binding}; exposure in use "
                           f"{st['gross_exposure']:.2f} incl. pending/unknown entries {st['pending_exposure']:.2f})")
        return {"allowed": not reasons, "reasons": reasons, "allowed_shares": shares, "binding_cap": binding,
                "equity": st["equity"], "gross_exposure_in_use": st["gross_exposure"]}

    # ---------------------------------------------------------------- orders
    def request_entry(self, symbol: str, qty: int, ref_price: float, stop_distance: float, data_age_s: float = 5) -> dict:
        n = len([e for e in self.ledger.events() if e["kind"] == "intent_created"]) + 1
        cid = f"{self.cfg.strategy_version}:{self.cfg.session}:{n:04d}"
        chk = self.entry_check(symbol, qty, ref_price, stop_distance, data_age_s)
        self._evt("intent_created", {"symbol": symbol, "side": "buy", "qty": qty, "ref_price": ref_price,
                                     "stop_distance": stop_distance, "purpose": "entry", "data_age_s": data_age_s,
                                     "type": "limit (synthetic)", "client_order_id": cid}, cid, f"intent:{cid}")
        if not chk["allowed"]:
            self._evt("blocked", {"reasons": chk["reasons"], "check": chk}, cid, f"blocked:{cid}")
            return {"order_id": cid, "submitted": False, "reasons": chk["reasons"]}
        self._evt("validated", {"check": chk}, cid, f"validated:{cid}")
        return self._submit(cid, symbol, "buy", qty)

    def _submit(self, cid: str, symbol: str, side: str, qty: int) -> dict:
        o = self.state()["orders"][cid]
        if o.state != L.VALIDATED:          # never resubmit: an id that has been submitted is only reconciled
            return {"order_id": cid, "submitted": False, "reasons": [f"not resubmitted: order is {o.state}"]}
        self._evt("submit_requested", {"symbol": symbol, "side": side, "qty": qty}, cid, f"submit:{cid}")
        try:
            r = self.broker.submit(cid, symbol, side, qty)
        except ConnectionLost as exc:
            self._evt("submit_outcome_unknown", {"error": str(exc)}, cid, f"unknown:{cid}")
            return {"order_id": cid, "submitted": "unknown", "reasons": [str(exc)]}
        if r["status"] == "rejected":
            self._evt("broker_reject", {"reason": r["reason"]}, cid, f"resp:{cid}", source="broker")
            return {"order_id": cid, "submitted": False, "reasons": [r["reason"]]}
        self._evt("broker_ack", {"broker_order_id": r["broker_order_id"], "via": "submit response"}, cid, f"resp:{cid}",
                  source="broker")
        return {"order_id": cid, "submitted": True, "broker_order_id": r["broker_order_id"]}

    def retry_submit(self, cid: str) -> dict:
        """What a naive retry would do. The lab refuses unless the intent was never submitted."""
        o = self.state()["orders"][cid]
        if o.state != L.VALIDATED:
            self._evt("resubmit_refused", {"state": o.state, "reason": "submission outcome must be reconciled, never "
                                           "retried blindly"}, cid)
            return {"order_id": cid, "submitted": False, "reasons": [f"refused: order is {o.state}"]}
        return self._submit(cid, o.symbol, o.side, o.qty)

    def poll(self) -> dict:
        try:
            updates = self.broker.poll()
        except BrokerUnavailable as exc:
            self._evt("broker_unreachable", {"error": str(exc), "during": "poll"})
            return {"ok": False, "stored": 0, "duplicates": 0}
        stored = dup = 0
        for u in updates:
            eid = f"fill:{u['exec_id']}" if u["kind"] == "fill" else f"upd:{u['update_id']}"
            payload = {k: v for k, v in u.items() if k not in ("kind", "client_order_id")}
            if self._evt(u["kind"], payload, u["client_order_id"], eid, source="broker"):
                stored += 1
            else:
                dup += 1
        return {"ok": True, "stored": stored, "duplicates": dup}

    def cancel(self, cid: str, why: str = "") -> dict:
        o = self.state()["orders"][cid]
        if o.state in L.TERMINAL:
            return {"order_id": cid, "requested": False, "status": f"not needed: {o.state}"}
        n = self.broker.cancel_calls.get(cid, 0) + 1
        try:
            self.broker.request_cancel(cid)
        except BrokerUnavailable as exc:
            self._evt("cancel_request_failed", {"error": str(exc), "why": why}, cid, f"cancelfail:{cid}:{n}")
            return {"order_id": cid, "requested": False, "status": "FAILED: " + str(exc)}
        self._evt("cancel_requested", {"why": why, "note": "a request is not a confirmation"}, cid, f"cancelreq:{cid}:{n}")
        return {"order_id": cid, "requested": True, "status": "REQUESTED (not confirmed)"}

    # ---------------------------------------------------------------- reconciliation
    def reconcile(self) -> dict:
        st = self.state()
        n = len([e for e in self.ledger.events() if e["kind"] in ("reconciliation_complete", "reconciliation_incomplete",
                                                                     "reconciliation_failed")]) + 1
        open_ids = [o.order_id for o in st["orders"].values() if o.state in L.LIVE]
        found, missing = {}, []
        try:
            for cid in open_ids:
                b = self.broker.lookup(cid)
                if b is None:
                    missing.append(cid)
                    self._evt("reconciliation", {"broker": None, "note": "not found at the broker by client order id; "
                              "absence is not proof it was never received (policy decision needed)"}, cid, f"recon:{n}:{cid}")
                    continue
                for x in b["executions"]:
                    self._evt("fill", {"exec_id": x["exec_id"], "qty": x["qty"], "price": x["price"],
                                       "broker_order_id": b["broker_order_id"], "via": "reconciliation"},
                              cid, f"fill:{x['exec_id']}", source="broker")
                if b["status"] == "cancelled":
                    self._evt("broker_cancelled", {"broker_order_id": b["broker_order_id"], "filled_qty": b["filled_qty"],
                                                   "via": "reconciliation"}, cid, f"cancelled:{cid}", source="broker")
                self._evt("reconciliation", {"broker": b}, cid, f"recon:{n}:{cid}", source="broker")
                found[cid] = b["status"]
            broker_pos = self.broker.positions()
        except BrokerUnavailable as exc:
            self._evt("reconciliation_failed", {"error": str(exc)}, event_id=f"reconfail:{n}")
            return {"ok": False, "error": str(exc)}
        st = self.state()
        local_pos = {s: v["qty"] for s, v in st["positions"].items()}
        unknown = [o.order_id for o in st["orders"].values() if o.state == L.UNKNOWN]
        mismatch = broker_pos != local_pos
        result = {"found": found, "not_found": missing, "still_unknown": unknown, "broker_positions": broker_pos,
                  "local_positions": local_pos, "positions_match": not mismatch}
        if unknown or mismatch:
            self._evt("reconciliation_incomplete", result, event_id=f"reconinc:{n}")
            return {"ok": False, **result}
        self._evt("reconciliation_complete", result, event_id=f"reconok:{n}")
        return {"ok": True, **result}

    # ---------------------------------------------------------------- emergency stop
    def emergency_stop(self, why: str) -> dict:
        self._evt("emergency_stop", {"why": why}, event_id="estop")
        self._evt("stop_action", {"step": "block_new_entries", "status": "DONE", "detail": "local flag; blocks entries in "
                                  "this process only and proves nothing about the broker"})
        for o in [o for o in self.state()["orders"].values() if o.state in L.LIVE]:
            r = self.cancel(o.order_id, "emergency stop")
            self._evt("stop_action", {"step": "request_cancellation", "order_id": o.order_id,
                                      "status": "REQUESTED" if r["requested"] else "FAILED", "detail": r["status"]})
        return self.stop_report()

    def stop_report(self) -> dict:
        return stop_report(self.state(), self.ledger.events())


def stop_report(st: dict, events: list[dict]) -> dict:
    """Emergency-stop status derived from the records. COMPLETE only when nothing remains unresolved."""
    if not st["flags"]["emergency_stop"]:
        return {"active": False}
    stop_seq = next(e["seq"] for e in events if e["kind"] == "emergency_stop")
    targets = [a["order_id"] for a in st["stop_actions"] if a["step"] == "request_cancellation"]
    orders = st["orders"]
    cancel_rows, unresolved = [], []
    for cid in targets:
        o = orders[cid]
        req = [a for a in st["stop_actions"] if a.get("order_id") == cid]
        delivered = any(e["kind"] == "cancel_requested" and e["order_id"] == cid and e["seq"] > stop_seq for e in events)
        if o.state == L.CANCELLED:
            conf = "CONFIRMED by broker"
        elif o.state == L.FILLED:
            conf = "NOT POSSIBLE: filled before the cancellation took effect"
        elif o.state == L.UNKNOWN:
            conf = "UNRESOLVED: outcome unknown"
        else:
            conf = "PENDING: no broker confirmation" if delivered else "NOT DELIVERED: request failed"
        if conf.startswith(("PENDING", "UNRESOLVED", "NOT DELIVERED")):
            unresolved.append(f"{cid}: {conf}")
        cancel_rows.append({"order_id": cid, "requested": "DELIVERED" if delivered else req[-1]["status"] if req else "-",
                            "confirmation": conf, "state": o.state, "filled_qty": o.filled_qty, "remaining_qty": o.remaining_qty})
    recon = [e for e in events if e["seq"] > stop_seq and e["kind"] in ("reconciliation_complete", "reconciliation_incomplete",
                                                                        "reconciliation_failed")]
    last = recon[-1]["kind"] if recon else None
    recon_status = {"reconciliation_complete": "CONFIRMED", "reconciliation_incomplete": "INCOMPLETE",
                    "reconciliation_failed": "FAILED: broker unreachable", None: "NOT RUN"}[last]
    if recon_status != "CONFIRMED":
        unresolved.append(f"reconciliation: {recon_status}")
    live = [o.order_id for o in orders.values() if o.state in L.LIVE]
    exposure = st["held_exposure"] + st["pending_exposure"]
    if st["positions"]:
        unresolved.append("open position(s) remain; reduce/close NOT PERFORMED (no approved policy: owner decision)")
    steps = [
        {"step": "Block new entries", "status": "DONE (local only)"},
        {"step": "Request cancellation", "status": "DONE" if all(r["requested"] == "DELIVERED" for r in cancel_rows)
         else ("NONE NEEDED" if not cancel_rows else "INCOMPLETE")},
        {"step": "Confirm cancellation", "status": "DONE" if not [r for r in cancel_rows if r["confirmation"].startswith(
            ("PENDING", "UNRESOLVED", "NOT DELIVERED"))] else "INCOMPLETE"},
        {"step": "Reduce or close exposure", "status": "NOT NEEDED" if not st["positions"] else
         "NOT PERFORMED: no approved policy (owner decision)"},
        {"step": "Confirm reconciliation", "status": recon_status},
    ]
    return {"active": True, "overall": "COMPLETE" if not unresolved and not live else "INCOMPLETE",
            "steps": steps, "cancellations": cancel_rows, "unresolved": unresolved, "live_orders": live,
            "remaining_exposure": round(exposure, 2), "positions": st["positions"],
            "note": "A local halt does not prove that a remote order was cancelled or a position closed."}
