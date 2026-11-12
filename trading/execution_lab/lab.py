"""Execution core, run against an injected broker port: the FAKE broker by default (LOCAL EXECUTION SIMULATION), or
the offline Alpaca paper adapter with fixture transports in tests. Synthetic instrument and prices, a controllable
clock, and an append-only ledger in memory or in a caller-supplied (temporary) file.

Path: intent -> validation -> risk decision -> durable journal -> broker port -> order updates -> reconciliation
-> account ledger. Every step is a ledger event; positions, cash and exposure are derived from the ledger only.

Checks before any new entry, in order (all reasons are recorded; the intent is persisted as BLOCKED):
  intent source (NO APPROVED ACTIVE STRATEGY refuses strategy intents) · execution policy (any required field UNSET
  blocks the entry) · per-order and per-session policy limits · emergency stop · reconciliation required (unknown
  outcome, discrepancy, or an unreconciled restart) · unprotected shares beyond the policy time · stale market data
  (LAB PARAMETER) · trading.risk.RiskState (daily loss, drawdown) · trading.risk.size_position with
  OWNER_BASELINE_2026_11_03 (exposure includes pending, partially filled and unknown entries). A request above the
  allowed size is refused, not resized.

Client order ids are deterministic: <strategy version>:<session>:<intent sequence>. A submission whose outcome is
unknown is never resubmitted; only reconciliation (lookup by client order id) can resolve it. The ledger records each
submission BEFORE the broker call, so a crash at any point leaves evidence of what may have been sent.

Crash points (TEST HOOK: the environment variable XLAB_CRASH_AT makes the process exit at that point, to prove
recovery in a fresh process): before_intent, after_intent_record (intent recorded, checks' outcome not yet recorded),
after_intent_before_send, after_submit_record_before_send, after_send_before_ack, during_partial_fills, during_cancel.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from trading.costs import BASE, CostModel
from trading.execution_lab import ledger as L
from trading.execution_lab.fake_broker import BrokerUnavailable, ConnectionLost, FakeBroker
from trading.execution_lab.intents import LAB_SYNTHETIC, IntentSource, source_refusal
from trading.execution_lab.policy import APPROVED, ExecutionPolicy, describe_missing
from trading.risk import OWNER_BASELINE_2026_11_03, RiskLimits, RiskState, size_position

CRASH_EXIT_CODE = 86
# Ledger evidence that a submission may have reached the broker (any of these means "not provably unsent").
SUBMISSION_EVIDENCE = ("submit_requested", "submit_outcome_unknown", "broker_ack", "broker_reject", "fill",
                       "broker_cancelled", "cancel_requested", "cancel_rejected", "reconciliation")


def _crash(point: str) -> None:
    """TEST HOOK: simulate the process dying at this point (no cleanup, no flush beyond what is already committed)."""
    if os.getenv("XLAB_CRASH_AT") == point:
        os._exit(CRASH_EXIT_CODE)


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


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


class Lab:
    def __init__(self, ledger: L.Ledger, broker, clock: Clock, config: LabConfig | None = None,
                 restart: bool = False, policy: ExecutionPolicy = APPROVED, entry_controls=None):
        self.ledger, self.broker, self.clock = ledger, broker, clock
        # Injected session controls (kill switch, paper-only account checks): a callable returning blocking reasons.
        # Checked when an entry is validated AND again immediately before it is sent. Entries only: cancels,
        # protective stops, reconciliation and the emergency stop are never blocked by it.
        self.entry_controls = entry_controls
        self.cfg = config or LabConfig()
        self.policy = policy
        self.cv = f"{self.cfg.version()}+{policy.version()}"
        n = len([e for e in ledger.events() if e["kind"] == "process_start"])
        self._evt("process_start", {"restart": restart, "policy": policy.label, "pid": os.getpid(),
                                    "note": "restart: outstanding orders are rebuilt from the ledger; entries stay "
                                            "blocked until reconciliation" if restart else "fresh start"},
                  event_id=f"start:{n + 1}")
        if hasattr(broker, "know"):        # a stateless broker port (paper adapter) relearns our order ids from the ledger
            broker.know({o.order_id: o.broker_order_id for o in self.state()["orders"].values() if o.broker_order_id})

    def _control_reasons(self) -> list[str]:
        if self.entry_controls is None:
            return []
        try:
            return list(self.entry_controls())
        except Exception as exc:                       # a control that cannot be evaluated blocks (fail closed)
            return [f"SESSION CONTROLS UNAVAILABLE ({type(exc).__name__}): entry blocked (fail closed)"]

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

    def unprotected_beyond_policy(self, st: dict | None = None) -> list[dict]:
        st = st or self.state()
        limit = self.policy.max_unprotected_seconds
        out = []
        for p in st["protection"]:
            if p["unprotected_qty"] > 0 and p["unprotected_since"]:
                age = (self.clock.now() - _ts(p["unprotected_since"])).total_seconds()
                if limit is None or age > limit:
                    out.append({**p, "age_s": round(age), "limit_s": limit})
        return out

    def entry_check(self, symbol: str, qty: int, ref_price: float, stop_distance: float, data_age_s: float,
                    source: IntentSource = LAB_SYNTHETIC) -> dict:
        st = self.state()
        reasons = []
        refusal = source_refusal(source)
        if refusal:
            reasons.append(refusal)
        reasons += self._control_reasons()
        reasons += describe_missing(self.policy.missing("entry"))
        reasons += [f"POLICY INVALID: {x}" for x in self.policy.invalid()]
        pol = self.policy
        if pol.max_shares_per_order is not None and qty > pol.max_shares_per_order:
            reasons.append(f"policy: {qty} shares > max_shares_per_order {pol.max_shares_per_order} ({pol.label})")
        if pol.max_notional_per_order is not None and qty * ref_price > pol.max_notional_per_order:
            reasons.append(f"policy: notional {qty * ref_price:.2f} > max_notional_per_order {pol.max_notional_per_order} "
                           f"({pol.label})")
        n_entries = sum(1 for o in st["orders"].values() if o.purpose == "entry")
        if pol.max_orders_per_session is not None and n_entries >= pol.max_orders_per_session:
            reasons.append(f"policy: {n_entries} entry intents already this session (max {pol.max_orders_per_session})")
        if st["flags"]["emergency_stop"]:
            reasons.append("emergency stop active: new entries blocked")
        if st["flags"]["reconciliation_required"]:
            why = [o.order_id for o in st["orders"].values() if o.state == L.UNKNOWN]
            what = (f"unknown outcome: {', '.join(why)}" if why else
                    "unresolved reconciliation discrepancies" if st["flags"]["unresolved_discrepancies"] else
                    "restart not yet reconciled")
            reasons.append(f"reconciliation required before any new entry ({what})")
        for u in self.unprotected_beyond_policy(st):
            reasons.append(f"UNPROTECTED: {u['unprotected_qty']} {u['symbol']} shares without an active stop for "
                           f"{u['age_s']} s (limit {u['limit_s'] if u['limit_s'] is not None else 'UNSET'}, {pol.label})")
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
                "equity": st["equity"], "gross_exposure_in_use": st["gross_exposure"], "policy": pol.label}

    # ---------------------------------------------------------------- orders
    def _spec(self, ref_price: float, stop_distance: float) -> dict:
        pol = self.policy
        spec = {"type": pol.order_type, "time_in_force": pol.time_in_force, "limit_price": round(ref_price, 2),
                "order_class": "bracket" if pol.protection_method == "bracket" else "simple"}
        if pol.protection_method == "bracket":
            spec["stop_loss"] = {"stop_price": round(ref_price - stop_distance, 2)}
        return spec

    def request_entry(self, symbol: str, qty: int, ref_price: float, stop_distance: float, data_age_s: float = 5,
                      source: IntentSource = LAB_SYNTHETIC) -> dict:
        _crash("before_intent")
        n = len([e for e in self.ledger.events() if e["kind"] == "intent_created"]) + 1
        cid = f"{self.cfg.strategy_version}:{self.cfg.session}:{n:04d}"
        chk = self.entry_check(symbol, qty, ref_price, stop_distance, data_age_s, source)
        spec = self._spec(ref_price, stop_distance) if not self.policy.missing("entry") else None
        self._evt("intent_created", {"symbol": symbol, "side": "buy", "qty": qty, "ref_price": ref_price,
                                     "stop_distance": stop_distance, "purpose": "entry", "data_age_s": data_age_s,
                                     "spec": spec, "client_order_id": cid,
                                     "source": {"kind": source.kind, "strategy_id": source.strategy_id,
                                                "version": source.version, "note": source.note}}, cid, f"intent:{cid}")
        _crash("after_intent_record")
        if not chk["allowed"]:
            self._evt("blocked", {"reasons": chk["reasons"], "check": chk}, cid, f"blocked:{cid}")
            return {"order_id": cid, "submitted": False, "reasons": chk["reasons"]}
        self._evt("validated", {"check": chk}, cid, f"validated:{cid}")
        _crash("after_intent_before_send")
        return self._submit(cid, symbol, "buy", qty, spec)

    def _submit(self, cid: str, symbol: str, side: str, qty: int, spec: dict | None) -> dict:
        o = self.state()["orders"][cid]
        if o.state != L.VALIDATED:          # never resubmit: an id that has been submitted is only reconciled
            return {"order_id": cid, "submitted": False, "reasons": [f"not resubmitted: order is {o.state}"]}
        if o.purpose == "entry":
            late = self._control_reasons()                 # the state may have changed since validation
            if late:
                self._evt("blocked", {"reasons": late, "stage": "send-time controls (nothing sent)"}, cid,
                          f"blocked-send:{cid}")
                return {"order_id": cid, "submitted": False, "reasons": late}
        self._evt("submit_requested", {"symbol": symbol, "side": side, "qty": qty, "spec": spec,
                                       "note": "recorded BEFORE the broker call"}, cid, f"submit:{cid}")
        _crash("after_submit_record_before_send")
        try:
            r = self.broker.submit(cid, symbol, side, qty, spec)
        except ConnectionLost as exc:
            self._evt("submit_outcome_unknown", {"error": str(exc)}, cid, f"unknown:{cid}")
            return {"order_id": cid, "submitted": "unknown", "reasons": [str(exc)]}
        _crash("after_send_before_ack")
        if r["status"] == "rejected":
            self._evt("broker_reject", {"reason": r["reason"], "local": bool(r.get("local"))}, cid, f"resp:{cid}",
                      source="local" if r.get("local") else "broker")
            return {"order_id": cid, "submitted": False, "reasons": [r["reason"]]}
        self._evt("broker_ack", {"broker_order_id": r["broker_order_id"], "via": "submit response",
                                 "note": "an acknowledgement is not a fill"}, cid, f"resp:{cid}", source="broker")
        for leg in r.get("legs") or []:
            self._record_leg(cid, leg, spec)
        return {"order_id": cid, "submitted": True, "broker_order_id": r["broker_order_id"]}

    def _record_leg(self, parent: str, leg: dict, spec: dict | None) -> None:
        lc = leg["client_order_id"]
        if lc in self.state()["orders"]:
            return
        p = self.state()["orders"][parent]
        stop = ((spec or {}).get("stop_loss") or {}).get("stop_price") or p.ref_price
        self._evt("intent_created", {"symbol": p.symbol, "side": "sell", "qty": p.qty, "ref_price": stop,
                                     "purpose": "protect", "parent": parent, "client_order_id": lc,
                                     "note": "bracket stop leg created by the broker"}, lc, f"intent:{lc}", source="broker")
        self._evt("leg_held", {"broker_order_id": leg.get("broker_order_id"), "parent": parent,
                               "note": "HELD: inactive until the entry is completely filled; not protection"},
                  lc, f"held:{lc}", source="broker")

    def protect(self, entry_cid: str) -> dict:
        """stop_after_fill: protect the filled quantity of a FINISHED entry with a stop sell. Refused while the entry
        can still fill (a stop sell next to an open buy is wash-trade rejected) or if the policy is unset."""
        st = self.state()
        o = st["orders"][entry_cid]
        miss = self.policy.missing("protect")
        if miss:
            self._evt("protection_alert", {"symbol": o.symbol, "entry": entry_cid, "reasons": describe_missing(miss)})
            return {"submitted": False, "reasons": describe_missing(miss)}
        if self.policy.protection_method != "stop_after_fill":
            return {"submitted": False, "reasons": [f"protection_method is {self.policy.protection_method}"]}
        if o.state not in (L.FILLED, L.CANCELLED) or o.filled_qty == 0:
            return {"submitted": False, "reasons": [f"entry is {o.state} with {o.filled_qty} filled: protect after it is final"]}
        covered = sum(x.qty for x in st["orders"].values() if x.purpose == "protect"
                      and x.order_id.startswith(entry_cid) and x.state not in (L.REJECTED, L.CANCELLED, L.BLOCKED))
        need = o.filled_qty - covered
        if need <= 0:
            return {"submitted": False, "reasons": ["already covered"]}
        n = len([x for x in st["orders"] if x.startswith(entry_cid + ":stop")]) + 1
        sc = f"{entry_cid}:stop{n}"
        stop_px = round(o.ref_price - float(next(e["payload"]["stop_distance"] for e in self.ledger.events()
                                                 if e["kind"] == "intent_created" and e["order_id"] == entry_cid)), 2)
        spec = {"type": "stop", "time_in_force": self.policy.time_in_force, "stop_price": stop_px,
                "order_class": "simple"}
        self._evt("intent_created", {"symbol": o.symbol, "side": "sell", "qty": need, "ref_price": stop_px,
                                     "purpose": "protect", "parent": entry_cid, "spec": spec, "client_order_id": sc},
                  sc, f"intent:{sc}")
        self._evt("validated", {"check": {"protect": True, "policy": self.policy.label}}, sc, f"validated:{sc}")
        return self._submit(sc, o.symbol, "sell", need, spec)

    def exit_position(self, symbol: str, qty: int, ref_price: float, why: str = "") -> dict:
        """Reduce exposure: sell shares the LEDGER holds and no other live sell has reserved. Risk-reducing, so the
        kill switch and the entry gates never block it. Only on an explicit call: nothing here liquidates
        automatically. Needs the policy's order type and time in force (unset = refused, never a default)."""
        st = self.state()
        n = len([e for e in self.ledger.events() if e["kind"] == "intent_created" and e["payload"].get("purpose") == "exit"]) + 1
        cid = f"{self.cfg.strategy_version}:{self.cfg.session}:exit{n:03d}"
        held = (st["positions"].get(symbol) or {}).get("qty", 0)
        reserved = sum(o.remaining_qty for o in st["orders"].values()
                       if o.symbol == symbol and o.side == "sell" and o.state in L.LIVE)
        reasons = [f"POLICY UNSET: {f} (needed to place an exit order)" for f in ("order_type", "time_in_force")
                   if getattr(self.policy, f) is None]
        if qty <= 0 or qty > held - reserved:
            reasons.append(f"exit of {qty} exceeds the unreserved ledger position ({held} held, {reserved} reserved by "
                           "live sells); cancel those first")
        spec = None if reasons else {"type": self.policy.order_type, "time_in_force": self.policy.time_in_force,
                                     "limit_price": round(ref_price, 2), "order_class": "simple"}
        self._evt("intent_created", {"symbol": symbol, "side": "sell", "qty": qty, "ref_price": ref_price,
                                     "purpose": "exit", "why": why, "spec": spec, "client_order_id": cid}, cid,
                  f"intent:{cid}")
        if reasons:
            self._evt("blocked", {"reasons": reasons}, cid, f"blocked:{cid}")
            return {"order_id": cid, "submitted": False, "reasons": reasons}
        self._evt("validated", {"check": {"exit": True, "policy": self.policy.label}}, cid, f"validated:{cid}")
        return self._submit(cid, symbol, "sell", qty, spec)

    def retry_submit(self, cid: str) -> dict:
        """What a naive retry would do. The lab refuses unless the intent was never submitted."""
        o = self.state()["orders"][cid]
        if o.state != L.VALIDATED:
            self._evt("resubmit_refused", {"state": o.state, "reason": "submission outcome must be reconciled, never "
                                           "retried blindly"}, cid)
            return {"order_id": cid, "submitted": False, "reasons": [f"refused: order is {o.state}"]}
        return self._submit(cid, o.symbol, o.side, o.qty, None)

    def poll(self) -> dict:
        try:
            updates = self.broker.poll()
        except BrokerUnavailable as exc:
            self._evt("broker_unreachable", {"error": str(exc), "during": "poll"})
            return {"ok": False, "stored": 0, "duplicates": 0}
        stored = dup = 0
        for i, u in enumerate(updates):
            eid = f"fill:{u['exec_id']}" if u["kind"] == "fill" else f"upd:{u['update_id']}"
            payload = {k: v for k, v in u.items() if k not in ("kind", "client_order_id")}
            if self._evt(u["kind"], payload, u["client_order_id"], eid, source="broker"):
                stored += 1
            else:
                dup += 1
            if u["kind"] == "fill" and i < len(updates) - 1:
                _crash("during_partial_fills")
        return {"ok": True, "stored": stored, "duplicates": dup}

    def cancel(self, cid: str, why: str = "") -> dict:
        o = self.state()["orders"][cid]
        if o.state in L.TERMINAL:
            return {"order_id": cid, "requested": False, "status": f"not needed: {o.state}"}
        # Numbered from the durable ledger, not from the broker client's in-memory counters: a fresh process (or a fresh
        # adapter) must never reuse an earlier request's event id, or its evidence would be filed as a duplicate.
        n = sum(1 for e in self.ledger.events() if e["order_id"] == cid and e["kind"] in
                ("cancel_requested", "cancel_request_failed", "cancel_rejected")) + 1
        try:
            r = self.broker.request_cancel(cid) or {"status": "requested"}
        except BrokerUnavailable as exc:
            self._evt("cancel_request_failed", {"error": str(exc), "why": why}, cid, f"cancelfail:{cid}:{n}")
            return {"order_id": cid, "requested": False, "status": "FAILED: " + str(exc)}
        _crash("during_cancel")
        if r.get("status") == "not_cancelable":
            self._evt("cancel_rejected", {"reason": r.get("reason"), "note": "not cancelable: re-read the order"},
                      cid, f"cancelrej:{cid}:{n}", source="broker")
            return {"order_id": cid, "requested": False, "status": "NOT CANCELABLE: " + str(r.get("reason"))}
        self._evt("cancel_requested", {"why": why, "note": "a request is not a confirmation"}, cid, f"cancelreq:{cid}:{n}")
        return {"order_id": cid, "requested": True, "status": "REQUESTED (not confirmed)"}

    # ---------------------------------------------------------------- reconciliation
    def reconcile(self) -> dict:
        """Compare orders, fills, positions and cash with the broker. Adopt only what the broker records; never
        force the ledger to balance. Discrepancies are recorded and keep entries blocked until a clean run."""
        st = self.state()
        n = len([e for e in self.ledger.events() if e["kind"] in ("reconciliation_complete", "reconciliation_incomplete",
                                                                     "reconciliation_failed")]) + 1
        # "Never sent" requires durable proof: the submission record is committed BEFORE any broker call, so an intent with
        # no submission record and no broker-originated event cannot have reached the broker. Any such evidence makes the
        # intent unresolved (a blocking discrepancy), never "never sent".
        evs = self.ledger.events()
        local = {e["order_id"] for e in evs if e["kind"] == "intent_created" and e["source"] == "local"}
        sent_evidence = {e["order_id"] for e in evs if e["kind"] in SUBMISSION_EVIDENCE or e["source"] == "broker"}
        contradictory = []
        for o in [o for o in st["orders"].values() if o.state in (L.CREATED, L.VALIDATED) and o.order_id in local]:
            if o.order_id in sent_evidence:
                contradictory.append({"kind": "unsent_intent_with_submission_evidence", "order_id": o.order_id,
                                      "state": o.state, "note": "the ledger holds submission or broker evidence for an "
                                      "order it shows as not sent; not closed as never sent; owner review"})
                continue
            why = ("validated but never sent (no submission record); the process stopped before sending" if o.state == L.VALIDATED
                   else "recorded but never validated or blocked (the process stopped during the checks); never sent")
            self._evt("intent_expired_unsent", {"reason": why + "; not resent automatically", "state_before": o.state,
                                                "proof": "no submission record and no broker event exist for this order"},
                      o.order_id, f"expired:{o.order_id}")
        live = [o.order_id for o in st["orders"].values() if o.state in L.LIVE or o.state == L.HELD]
        found, missing, missing_live = {}, [], []
        try:
            for cid in live:
                b = self.broker.lookup(cid)
                o = self.state()["orders"][cid]
                if b is None:
                    missing.append(cid)
                    if o.state == L.SUBMISSION_PENDING:
                        self._evt("submit_outcome_unknown", {"error": "process stopped after recording the submission; "
                                  "the broker has no record yet; it may still be in transit; never resubmitted"},
                                  cid, f"unknown:{cid}")
                    elif o.state != L.UNKNOWN:      # the ledger says live (or a held leg); the broker has no record of it
                        missing_live.append({"kind": "order_missing_at_broker", "order_id": cid, "state": o.state,
                                             "note": "the ledger shows this order live but the broker has no record of its "
                                                     "client order id; not assumed cancelled or filled; owner review"})
                    self._evt("reconciliation", {"broker": None, "note": "not found at the broker by client order id; "
                              "absence is not proof it was never received"}, cid, f"recon:{n}:{cid}")
                    continue
                for x in b["executions"]:
                    self._evt("fill", {"exec_id": x["exec_id"], "qty": x["qty"], "price": x["price"],
                                       "broker_order_id": b["broker_order_id"], "via": "reconciliation"},
                              cid, f"fill:{x['exec_id']}", source="broker")
                if b["status"] == "cancelled":
                    self._evt("broker_cancelled", {"broker_order_id": b["broker_order_id"], "filled_qty": b["filled_qty"],
                                                   "via": "reconciliation"}, cid, f"cancelled:{cid}", source="broker")
                self._evt("reconciliation", {"broker": {k: v for k, v in b.items() if k != "executions"}},
                          cid, f"recon:{n}:{cid}", source="broker")
                found[cid] = b["status"]
            broker_pos = self.broker.positions()
            broker_open = self.broker.open_orders() if hasattr(self.broker, "open_orders") else []
            broker_cash = (self.broker.account() or {}).get("cash") if hasattr(self.broker, "account") else None
        except BrokerUnavailable as exc:
            self._evt("reconciliation_failed", {"error": str(exc)}, event_id=f"reconfail:{n}")
            return {"ok": False, "error": str(exc)}
        st = self.state()
        local_pos = {s: v["qty"] for s, v in st["positions"].items()}
        disc = list(missing_live) + contradictory
        for s in sorted(set(broker_pos) | set(local_pos)):
            if broker_pos.get(s, 0) != local_pos.get(s, 0):
                disc.append({"kind": "position", "symbol": s, "broker": broker_pos.get(s, 0), "ledger": local_pos.get(s, 0),
                             "note": "not corrected automatically; owner review"})
        for x in broker_open:
            if x["client_order_id"] not in st["orders"]:
                disc.append({"kind": "foreign_order", "symbol": x["symbol"], "side": x["side"], "qty": x["qty"],
                             "status": x["status"], "note": "open order not created by this system (manual?)"})
        if broker_cash is not None and abs(broker_cash - st["cash"]) > 0.01:
            disc.append({"kind": "cash", "broker": broker_cash, "ledger": st["cash"],
                         "difference": round(broker_cash - st["cash"], 2), "note": "shown, not forced to balance"})
        unknown = [o.order_id for o in st["orders"].values() if o.state == L.UNKNOWN]
        for u in unknown:
            disc.append({"kind": "unknown_outcome", "order_id": u, "note": "still unresolved: entries stay blocked"})
        result = {"found": found, "not_found": missing, "still_unknown": unknown, "broker_positions": broker_pos,
                  "local_positions": local_pos, "positions_match": not any(d["kind"] == "position" for d in disc),
                  "broker_cash": broker_cash, "ledger_cash": st["cash"], "discrepancies": disc}
        if disc:
            self._evt("reconciliation_incomplete", result, event_id=f"reconinc:{n}")
            return {"ok": False, **result}
        self._evt("reconciliation_complete", result, event_id=f"reconok:{n}")
        return {"ok": True, **result}

    # ---------------------------------------------------------------- attention: what is unresolved, with policy timing
    def attention(self) -> list[dict]:
        st, now, pol, out = self.state(), self.clock.now(), self.policy, []
        evs = self.ledger.events()

        def since(cid, kinds):
            ts = [e["ts_utc"] for e in evs if e["order_id"] == cid and e["kind"] in kinds]
            return (now - _ts(ts[-1])).total_seconds() if ts else None
        for o in st["orders"].values():
            if o.state == L.UNKNOWN:
                age, lim = since(o.order_id, ("submit_outcome_unknown",)), pol.unknown_escalation_seconds
                out.append({"order_id": o.order_id, "what": "unknown submission outcome", "age_s": age,
                            "action": "ESCALATE TO OWNER" if lim is not None and age is not None and age >= lim else
                            ("keep looking up; escalation time UNSET (owner decision A4)" if lim is None else "keep looking up")})
            if o.state == L.CANCEL_PENDING:
                age, lim = since(o.order_id, ("cancel_requested",)), pol.cancel_confirm_timeout_seconds
                out.append({"order_id": o.order_id, "what": "cancellation not confirmed", "age_s": age,
                            "action": "RE-READ ORDER AND ESCALATE" if lim is not None and age is not None and age >= lim else
                            ("wait for confirmation; timeout UNSET (owner decision A5)" if lim is None else "wait for confirmation")})
            if o.state == L.HELD:
                out.append({"order_id": o.order_id, "what": "protective leg HELD (inactive): not protection", "age_s": None,
                            "action": "none possible until the entry is completely filled"})
        for u in self.unprotected_beyond_policy(st):
            out.append({"order_id": None, "what": f"{u['unprotected_qty']} {u['symbol']} shares unprotected", "age_s": u["age_s"],
                        "action": {"block_and_alert": "entries blocked; owner alerted", None: "UNSET (owner decision A3)",
                                   "close_exposure": "NOT IMPLEMENTED: no automatic liquidation exists"}[pol.unprotected_exceeded_action]})
        for d in st["discrepancies"]:
            out.append({"order_id": d.get("order_id"), "what": f"reconciliation discrepancy: {d['kind']}", "age_s": None,
                        "action": "owner review; never auto-corrected"})
        return out

    # ---------------------------------------------------------------- emergency stop
    def emergency_stop(self, why: str) -> dict:
        self._evt("emergency_stop", {"why": why}, event_id="estop")
        self._evt("stop_action", {"step": "block_new_entries", "status": "DONE", "detail": "local flag; blocks entries in "
                                  "this process only and proves nothing about the broker"})
        for o in [o for o in self.state()["orders"].values() if o.state in L.LIVE and o.purpose == "entry"]:
            r = self.cancel(o.order_id, "emergency stop")
            self._evt("stop_action", {"step": "request_cancellation", "order_id": o.order_id,
                                      "status": "REQUESTED" if r["requested"] else "FAILED", "detail": r["status"]})
        return self.stop_report()

    def stop_report(self) -> dict:
        return stop_report(self.state(), self.ledger.events(), self.policy)


def stop_report(st: dict, events: list[dict], policy: ExecutionPolicy | None = None) -> dict:
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
    live = [o.order_id for o in orders.values() if o.state in L.LIVE and o.purpose == "entry"]
    exposure = st["held_exposure"] + st["pending_exposure"]
    action = (policy.emergency_exposure_action if policy else None)
    reduce = ("NOT NEEDED" if not st["positions"] else
              {None: "UNSET: owner decision A6 (no default chosen)",
               "leave_for_owner": "NOT PERFORMED: policy leaves remaining exposure for the owner",
               "close_exposure": "NOT IMPLEMENTED: no automatic liquidation exists"}[action])
    if st["positions"]:
        unresolved.append(f"open position(s) remain; reduce/close {reduce}")
    unprot = sum(p["unprotected_qty"] for p in st.get("protection", []))
    steps = [
        {"step": "Block new entries", "status": "DONE (local only)"},
        {"step": "Request cancellation", "status": "DONE" if all(r["requested"] == "DELIVERED" for r in cancel_rows)
         else ("NONE NEEDED" if not cancel_rows else "INCOMPLETE")},
        {"step": "Confirm cancellation", "status": "DONE" if not [r for r in cancel_rows if r["confirmation"].startswith(
            ("PENDING", "UNRESOLVED", "NOT DELIVERED"))] else "INCOMPLETE"},
        {"step": "Reduce or close exposure", "status": reduce},
        {"step": "Confirm reconciliation", "status": recon_status},
    ]
    return {"active": True, "overall": "COMPLETE" if not unresolved and not live else "INCOMPLETE",
            "steps": steps, "cancellations": cancel_rows, "unresolved": unresolved, "live_orders": live,
            "remaining_exposure": round(exposure, 2), "positions": st["positions"], "unprotected_shares": unprot,
            "protective_orders_kept": "protective stops are not cancelled by the emergency stop",
            "note": "A local halt does not prove that a remote order was cancelled or a position closed."}
