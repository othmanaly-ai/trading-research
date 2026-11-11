"""Order lifecycle and the append-only event ledger. LOCAL EXECUTION SIMULATION only.

The ledger is the single record. Order states, filled and remaining quantities, positions, cash, costs and exposure
are DERIVED from it by `derive()`; nothing keeps a second running total. The same derivation feeds the scenario
checks, the API and the city view.

Rules:
- Every event has an event id. Broker-originated updates use the broker's update id, so a repeated update is stored
  once; the repeat is recorded in a separate append-only `duplicates` table, never applied twice.
- Fills are applied by their execution id (each fill carries its own quantity), so arrival order does not matter.
- States never move backwards: an acknowledgement that arrives after a fill is recorded but changes nothing.
- An unknown submission outcome (UNKNOWN) is not a rejection: only an explicit broker record can resolve it.
- A cancellation request (CANCEL_PENDING) is not a cancellation: only a broker confirmation is (CANCELLED), and fills
  that arrive while the request is pending still count.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

# ---------------------------------------------------------------- states and valid transitions

CREATED, VALIDATED, BLOCKED = "CREATED", "VALIDATED", "BLOCKED"
SUBMISSION_PENDING, ACCEPTED, PARTIALLY_FILLED, FILLED = "SUBMISSION_PENDING", "ACCEPTED", "PARTIALLY_FILLED", "FILLED"
REJECTED, CANCEL_PENDING, CANCELLED, UNKNOWN = "REJECTED", "CANCEL_PENDING", "CANCELLED", "UNKNOWN"
STATES = (CREATED, VALIDATED, BLOCKED, SUBMISSION_PENDING, ACCEPTED, PARTIALLY_FILLED, FILLED, REJECTED,
          CANCEL_PENDING, CANCELLED, UNKNOWN)
TERMINAL = {FILLED, REJECTED, CANCELLED, BLOCKED}
LIVE = {SUBMISSION_PENDING, ACCEPTED, PARTIALLY_FILLED, CANCEL_PENDING, UNKNOWN}   # may still fill: counts as exposure
LABEL = {UNKNOWN: "OUTCOME UNKNOWN · reconciliation required", CANCEL_PENDING: "CANCELLATION PENDING (not confirmed)",
         BLOCKED: "BLOCKED before submission"}

TRANSITIONS = {
    CREATED: {VALIDATED, BLOCKED},
    VALIDATED: {SUBMISSION_PENDING},
    SUBMISSION_PENDING: {ACCEPTED, REJECTED, UNKNOWN, PARTIALLY_FILLED, FILLED, CANCEL_PENDING},
    UNKNOWN: {ACCEPTED, REJECTED, PARTIALLY_FILLED, FILLED, CANCELLED, CANCEL_PENDING},
    ACCEPTED: {PARTIALLY_FILLED, FILLED, CANCEL_PENDING, CANCELLED},
    PARTIALLY_FILLED: {PARTIALLY_FILLED, FILLED, CANCEL_PENDING, CANCELLED},
    CANCEL_PENDING: {CANCEL_PENDING, PARTIALLY_FILLED, FILLED, CANCELLED},
    FILLED: set(), REJECTED: set(), CANCELLED: set(), BLOCKED: set(),
}
RANK = {CREATED: 0, VALIDATED: 1, BLOCKED: 9, SUBMISSION_PENDING: 2, UNKNOWN: 3, ACCEPTED: 4, PARTIALLY_FILLED: 5,
        CANCEL_PENDING: 6, FILLED: 9, REJECTED: 9, CANCELLED: 9}


def can_transition(a: str, b: str) -> bool:
    return b in TRANSITIONS[a]


# ---------------------------------------------------------------- ledger (append-only)

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, ts_utc TEXT NOT NULL, kind TEXT NOT NULL,
  order_id TEXT, source TEXT NOT NULL, payload_json TEXT NOT NULL, config_version TEXT);
CREATE TABLE IF NOT EXISTS duplicates (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL, ts_utc TEXT NOT NULL, payload_json TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'append-only'); END;
"""


class Ledger:
    """Append-only SQLite event log. `path=None` keeps it in memory (scenarios); a file path is used only for a
    temporary file supplied by the caller (the restart scenario)."""

    def __init__(self, path: str | None = None):
        self.path = path
        self.db = sqlite3.connect(path or ":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def append(self, event_id: str, ts_utc: str, kind: str, source: str, payload: dict,
               order_id: str | None = None, config_version: str | None = None) -> bool:
        """True if stored; False if this event id was already recorded (the repeat goes to `duplicates`)."""
        body = json.dumps(payload, sort_keys=True, default=str)
        cur = self.db.execute("INSERT OR IGNORE INTO events (event_id, ts_utc, kind, order_id, source, payload_json, "
                              "config_version) VALUES (?,?,?,?,?,?,?)",
                              (event_id, ts_utc, kind, order_id, source, body, config_version))
        if cur.rowcount == 0:
            self.db.execute("INSERT INTO duplicates (event_id, ts_utc, payload_json) VALUES (?,?,?)", (event_id, ts_utc, body))
        self.db.commit()
        return cur.rowcount == 1

    def events(self) -> list[dict]:
        return [dict(r) | {"payload": json.loads(r["payload_json"])} for r in self.db.execute("SELECT * FROM events ORDER BY seq")]

    def duplicates(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM duplicates ORDER BY seq")]


# ---------------------------------------------------------------- derivation (the only place totals are computed)

@dataclass
class OrderView:
    order_id: str
    symbol: str
    side: str            # "buy" | "sell"
    qty: int
    ref_price: float
    purpose: str         # "entry" | "exit"
    state: str = CREATED
    broker_order_id: str | None = None
    filled_qty: int = 0
    notional: float = 0.0
    fees: float = 0.0
    cancelled_qty: int = 0
    exec_ids: list = field(default_factory=list)
    history: list = field(default_factory=list)      # (seq, from, to, kind)
    ignored: list = field(default_factory=list)      # (seq, kind, why) events that changed nothing
    anomalies: list = field(default_factory=list)
    reasons: list = field(default_factory=list)
    submit_attempts: int = 0
    config_version: str | None = None

    @property
    def remaining_qty(self) -> int:
        """Quantity that can still fill. Zero once the order is terminal."""
        return 0 if self.state in TERMINAL else max(0, self.qty - self.filled_qty)

    @property
    def avg_fill_price(self) -> float | None:
        return round(self.notional / self.filled_qty, 6) if self.filled_qty else None


def _move(o: OrderView, to: str, seq: int, kind: str) -> None:
    if to == o.state:
        return
    if not can_transition(o.state, to):
        if RANK.get(to, 0) <= RANK.get(o.state, 0) or o.state in TERMINAL:
            o.ignored.append((seq, kind, f"late or stale update: {o.state} kept (would be {to})"))
            return
        o.anomalies.append(f"seq {seq}: invalid transition {o.state} -> {to} ({kind})")
        return
    o.history.append((seq, o.state, to, kind))
    o.state = to


def derive(events: list[dict], start_cash: float, marks: dict | None = None, costs=None) -> dict:
    """Fold the ledger into orders, positions, cash, costs and exposure. Pure: same events -> same result."""
    from trading.costs import BASE
    costs = costs or BASE
    orders: dict[str, OrderView] = {}
    cash = start_cash
    pos: dict[str, int] = {}
    marks = dict(marks or {})
    flags = {"emergency_stop": False, "reconciliation_required": False, "restart_pending_reconciliation": False}
    stop_actions: list[dict] = []
    refusals: list[dict] = []
    for e in events:
        p, seq, kind, oid = e["payload"], e["seq"], e["kind"], e["order_id"]
        o = orders.get(oid) if oid else None
        if kind == "mark":
            marks[p["symbol"]] = p["price"]
        elif kind == "intent_created":
            orders[oid] = OrderView(oid, p["symbol"], p["side"], p["qty"], p["ref_price"], p["purpose"],
                                    config_version=e["config_version"])
            orders[oid].history.append((seq, None, CREATED, kind))
        elif kind == "validated" and o:
            _move(o, VALIDATED, seq, kind)
        elif kind == "blocked" and o:
            o.reasons = p["reasons"]
            _move(o, BLOCKED, seq, kind)
        elif kind == "entry_refused":
            refusals.append({"seq": seq, "ts_utc": e["ts_utc"], **p})
        elif kind == "submit_requested" and o:
            o.submit_attempts += 1
            _move(o, SUBMISSION_PENDING, seq, kind)
        elif kind == "submit_outcome_unknown" and o:
            o.reasons = [p.get("error", "no response")]
            _move(o, UNKNOWN, seq, kind)
        elif kind in ("broker_ack", "broker_reject", "fill", "broker_cancelled", "cancel_rejected") and o:
            if p.get("broker_order_id"):
                o.broker_order_id = p["broker_order_id"]
            if kind == "broker_ack":
                _move(o, ACCEPTED, seq, kind)
            elif kind == "broker_reject":
                o.reasons = [p.get("reason", "rejected")]
                _move(o, REJECTED, seq, kind)
            elif kind == "fill":
                if p["exec_id"] in o.exec_ids:
                    o.ignored.append((seq, kind, f"execution {p['exec_id']} already applied"))
                    continue
                if o.state in (FILLED, CANCELLED, REJECTED, BLOCKED) or o.filled_qty + p["qty"] > o.qty:
                    o.anomalies.append(f"seq {seq}: fill {p['exec_id']} of {p['qty']} not applicable in {o.state} "
                                       f"(filled {o.filled_qty}/{o.qty})")
                    continue
                o.exec_ids.append(p["exec_id"])
                o.filled_qty += p["qty"]
                value = p["qty"] * p["price"]
                o.notional += value
                fee = costs.commission_per_order if len(o.exec_ids) == 1 else 0.0
                if o.side == "sell":
                    fee += costs.sell_fee(value)
                o.fees += fee
                sign = 1 if o.side == "buy" else -1
                pos[o.symbol] = pos.get(o.symbol, 0) + sign * p["qty"]
                cash += -sign * value - fee
                done = o.filled_qty == o.qty
                _move(o, FILLED if done else (CANCEL_PENDING if o.state == CANCEL_PENDING else PARTIALLY_FILLED), seq, kind)
            elif kind == "broker_cancelled":
                o.cancelled_qty = o.qty - o.filled_qty
                _move(o, CANCELLED, seq, kind)
            elif kind == "cancel_rejected":
                o.reasons = [p.get("reason", "cancel rejected")]
        elif kind == "cancel_requested" and o:
            if o.state in TERMINAL:
                o.ignored.append((seq, kind, f"cancel requested for a {o.state} order"))
            else:
                _move(o, CANCEL_PENDING, seq, kind)
        elif kind == "reconciliation" and o:
            b = p.get("broker")
            if b is None:
                o.reasons = [p.get("note", "not found at broker")]
            else:
                o.broker_order_id = b.get("broker_order_id") or o.broker_order_id
                target = {"accepted": ACCEPTED, "partially_filled": PARTIALLY_FILLED, "filled": FILLED,
                          "cancelled": CANCELLED, "rejected": REJECTED}.get(b["status"])
                if target in (ACCEPTED, PARTIALLY_FILLED) and o.state == CANCEL_PENDING:
                    target = CANCEL_PENDING
                if target and target != o.state and not (target == PARTIALLY_FILLED and o.state == PARTIALLY_FILLED):
                    if target == CANCELLED:
                        o.cancelled_qty = o.qty - b.get("filled_qty", o.filled_qty)
                    _move(o, target, seq, kind)
        elif kind == "process_start":
            flags["restart_pending_reconciliation"] = bool(p.get("restart"))
        elif kind == "reconciliation_complete":
            flags["restart_pending_reconciliation"] = False
        elif kind == "emergency_stop":
            flags["emergency_stop"] = True
        elif kind == "stop_action":
            stop_actions.append({"seq": seq, "ts_utc": e["ts_utc"], **p})
    flags["reconciliation_required"] = any(o.state == UNKNOWN for o in orders.values()) or flags["restart_pending_reconciliation"]
    # positions, exposure (pending entries count), equity
    positions = {s: {"qty": q, "mark": marks.get(s), "value": q * marks[s] if s in marks else None} for s, q in pos.items() if q}
    held = sum(abs(v["value"]) for v in positions.values() if v["value"] is not None)
    pending = [{"order_id": o.order_id, "state": o.state, "qty": o.remaining_qty,
                "notional": o.remaining_qty * (marks.get(o.symbol) or o.ref_price)}
               for o in orders.values() if o.purpose == "entry" and o.state in LIVE and o.remaining_qty > 0]
    pending_notional = sum(x["notional"] for x in pending)
    equity = cash + sum(v["value"] for v in positions.values() if v["value"] is not None)
    fees = sum(o.fees for o in orders.values())
    return {"orders": orders, "cash": round(cash, 6), "positions": positions, "equity": round(equity, 6),
            "fees": round(fees, 6), "held_exposure": round(held, 6), "pending_entries": pending,
            "pending_exposure": round(pending_notional, 6), "gross_exposure": round(held + pending_notional, 6),
            "positions_in_use": len({s for s in positions} | {o.symbol for o in orders.values()
                                                              if o.purpose == "entry" and o.state in LIVE}),
            "flags": flags, "stop_actions": stop_actions, "refusals": refusals, "marks": marks}


def order_dict(o: OrderView) -> dict:
    return {"order_id": o.order_id, "symbol": o.symbol, "side": o.side, "purpose": o.purpose, "qty": o.qty,
            "ref_price": o.ref_price, "state": o.state, "state_label": LABEL.get(o.state, o.state),
            "broker_order_id": o.broker_order_id, "filled_qty": o.filled_qty, "remaining_qty": o.remaining_qty,
            "cancelled_qty": o.cancelled_qty, "avg_fill_price": o.avg_fill_price, "fees": round(o.fees, 6),
            "exec_ids": o.exec_ids, "submit_attempts": o.submit_attempts, "reasons": o.reasons,
            "history": [{"seq": s, "from": a, "to": b, "event": k} for s, a, b, k in o.history],
            "ignored": [{"seq": s, "event": k, "why": w} for s, k, w in o.ignored], "anomalies": o.anomalies,
            "config_version": o.config_version}
