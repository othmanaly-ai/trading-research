"""In-memory FAKE broker for the LOCAL EXECUTION SIMULATION. It is not a client of any real broker: no network,
no credentials, no relation to trading.alpaca_client. Scenarios script its behaviour explicitly, so every run is
deterministic.

What it models:
- submit(): accept, reject, or lose the connection either BEFORE the broker records the order or AFTER (the response
  is lost, but the order exists). The caller cannot tell these two apart, which is the point.
- updates: acknowledgements, fills (with execution ids), cancel confirmations and cancel rejections are queued by the
  scenario, possibly duplicated or out of order, and delivered by poll().
- lookup by client order id (reconciliation), and an `available` switch for outages.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class BrokerUnavailable(Exception):
    """The fake broker cannot be reached (simulated outage)."""


class ConnectionLost(Exception):
    """The submission's outcome is unknown: no response arrived."""


@dataclass
class FakeOrder:
    client_order_id: str
    broker_order_id: str
    symbol: str
    side: str
    qty: int
    status: str = "accepted"          # accepted | partially_filled | filled | cancelled | rejected
    executions: list = field(default_factory=list)    # {"exec_id", "qty", "price"}
    cancel_requested: bool = False

    @property
    def filled_qty(self) -> int:
        return sum(x["qty"] for x in self.executions)

    def view(self) -> dict:
        return {"broker_order_id": self.broker_order_id, "client_order_id": self.client_order_id, "status": self.status,
                "filled_qty": self.filled_qty, "qty": self.qty, "executions": list(self.executions),
                "cancel_requested": self.cancel_requested}


class FakeBroker:
    def __init__(self):
        self.orders: dict[str, FakeOrder] = {}
        self.submit_calls: dict[str, int] = {}      # client order id -> times submit() was called (resubmission evidence)
        self.cancel_calls: dict[str, int] = {}
        self.queue: list[dict] = []
        self.available = True
        self.next_submit: list[str] = []            # scripted outcomes for the next submit() calls
        self._n = 0

    # ---- scripted behaviour
    def script_submit(self, *outcomes: str) -> None:
        """'accept' | 'reject:<reason>' | 'lost_before_record' | 'lost_after_record'"""
        self.next_submit.extend(outcomes)

    def _bid(self) -> str:
        self._n += 1
        return f"FAKE-{self._n:04d}"

    def push(self, update: dict) -> None:
        self.queue.append(dict(update))

    def ack(self, cid: str, update_id: str) -> dict:
        u = {"update_id": update_id, "kind": "broker_ack", "client_order_id": cid,
             "broker_order_id": self.orders[cid].broker_order_id}
        self.push(u)
        return u

    def fill(self, cid: str, exec_id: str, qty: int, price: float) -> dict:
        """The broker executes qty at price (recorded at the broker now) and queues the update."""
        o = self.orders[cid]
        if o.status in ("cancelled", "rejected", "filled") or o.filled_qty + qty > o.qty:
            raise ValueError(f"fake broker cannot fill {cid}: {o.status}, {o.filled_qty}/{o.qty}")
        o.executions.append({"exec_id": exec_id, "qty": qty, "price": price})
        o.status = "filled" if o.filled_qty == o.qty else "partially_filled"
        u = {"update_id": f"exec-{exec_id}", "kind": "fill", "client_order_id": cid, "broker_order_id": o.broker_order_id,
             "exec_id": exec_id, "qty": qty, "price": price, "cum_qty": o.filled_qty}
        self.push(u)
        return u

    def confirm_cancel(self, cid: str, update_id: str) -> dict:
        o = self.orders[cid]
        if o.status == "filled":
            u = {"update_id": update_id, "kind": "cancel_rejected", "client_order_id": cid,
                 "broker_order_id": o.broker_order_id, "reason": "order already filled"}
        else:
            o.status = "cancelled"
            u = {"update_id": update_id, "kind": "broker_cancelled", "client_order_id": cid,
                 "broker_order_id": o.broker_order_id, "filled_qty": o.filled_qty}
        self.push(u)
        return u

    # ---- the interface the lab uses
    def submit(self, cid: str, symbol: str, side: str, qty: int) -> dict:
        self.submit_calls[cid] = self.submit_calls.get(cid, 0) + 1
        if not self.available:
            raise ConnectionLost("broker unreachable during submission (simulated); outcome unknown")
        outcome = self.next_submit.pop(0) if self.next_submit else "accept"
        if cid in self.orders:                       # the fake broker refuses a reused client order id
            return {"status": "rejected", "reason": "duplicate client_order_id", "broker_order_id": None}
        if outcome.startswith("reject"):
            return {"status": "rejected", "reason": outcome.partition(":")[2] or "rejected (synthetic)", "broker_order_id": None}
        if outcome == "lost_before_record":
            raise ConnectionLost("connection lost before the broker recorded the order (simulated)")
        self.orders[cid] = FakeOrder(cid, self._bid(), symbol, side, qty)
        if outcome == "lost_after_record":
            raise ConnectionLost("connection lost after the broker recorded the order (simulated)")
        return {"status": "accepted", "broker_order_id": self.orders[cid].broker_order_id}

    def poll(self) -> list[dict]:
        if not self.available:
            raise BrokerUnavailable("broker unavailable (simulated)")
        out, self.queue = self.queue, []
        return out

    def lookup(self, cid: str) -> dict | None:
        if not self.available:
            raise BrokerUnavailable("broker unavailable (simulated)")
        o = self.orders.get(cid)
        return o.view() if o else None

    def request_cancel(self, cid: str) -> None:
        self.cancel_calls[cid] = self.cancel_calls.get(cid, 0) + 1
        if not self.available:
            raise BrokerUnavailable("broker unavailable (simulated): cancellation request not delivered")
        if cid in self.orders:
            self.orders[cid].cancel_requested = True

    def positions(self) -> dict:
        if not self.available:
            raise BrokerUnavailable("broker unavailable (simulated)")
        pos: dict[str, int] = {}
        for o in self.orders.values():
            pos[o.symbol] = pos.get(o.symbol, 0) + (1 if o.side == "buy" else -1) * o.filled_qty
        return {s: q for s, q in pos.items() if q}
