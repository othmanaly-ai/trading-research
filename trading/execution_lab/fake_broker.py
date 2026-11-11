"""In-memory FAKE broker for the LOCAL EXECUTION SIMULATION. It is not a client of any real broker: no network,
no credentials, no relation to trading.alpaca_client. Scenarios script its behaviour explicitly, so every run is
deterministic. It may be saved to a file (save_to / load) so a FRESH PROCESS can find the same "external" broker
state after a crash, which is what a real broker would provide.

Modelled on Alpaca's documented behaviour (docs/EXECUTION_POLICY_DECISIONS.md), as a simulation, not as evidence:
- submit(): accept, reject, or lose the connection BEFORE or AFTER the broker records the order.
- bracket: the stop leg is created HELD and becomes active only when the entry is COMPLETELY filled; cancelling the
  entry cancels its legs.
- wash-trade protection: a sell stop is rejected while a buy for the same symbol is open; exit orders are accepted
  only for an existing position (both documented, simplified here).
- updates (acknowledgements, fills with execution ids, cancel confirmations and rejections, leg activation) are queued,
  possibly duplicated or out of order, and delivered by poll().
- cash uses the lab's cost model (trading.costs.BASE); a real broker's fees may differ (UNVERIFIED).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


class BrokerUnavailable(Exception):
    """The fake broker cannot be reached (simulated outage)."""


class ConnectionLost(Exception):
    """The submission's outcome is unknown: no response arrived."""


OPEN = ("accepted", "partially_filled", "held")


@dataclass
class FakeOrder:
    client_order_id: str
    broker_order_id: str
    symbol: str
    side: str
    qty: int
    status: str = "accepted"          # accepted | partially_filled | filled | cancelled | rejected | held
    executions: list = field(default_factory=list)    # {"exec_id", "qty", "price"}
    cancel_requested: bool = False
    order_type: str = "limit"
    stop_price: float | None = None
    parent: str | None = None         # entry cid for a bracket leg
    foreign: bool = False             # created outside the system (manual activity)

    @property
    def filled_qty(self) -> int:
        return sum(x["qty"] for x in self.executions)

    def view(self) -> dict:
        return {"broker_order_id": self.broker_order_id, "client_order_id": self.client_order_id, "status": self.status,
                "filled_qty": self.filled_qty, "qty": self.qty, "executions": list(self.executions), "side": self.side,
                "symbol": self.symbol, "cancel_requested": self.cancel_requested, "order_type": self.order_type,
                "stop_price": self.stop_price, "parent": self.parent, "foreign": self.foreign}


class FakeBroker:
    START_CASH = 100_000.0

    def __init__(self):
        self.orders: dict[str, FakeOrder] = {}
        self.submit_calls: dict[str, int] = {}      # client order id -> times submit() was called (resubmission evidence)
        self.cancel_calls: dict[str, int] = {}
        self.queue: list[dict] = []
        self.available = True
        self.next_submit: list[str] = []            # scripted outcomes for the next submit() calls
        self.cash = self.START_CASH
        self._n = 0
        self._manual = 0
        self.path: str | None = None                # when set, every change is saved (durable "external" broker)

    # ---- persistence (the broker outlives the client process)
    def save_to(self, path: str) -> "FakeBroker":
        self.path = path
        self._save()
        return self

    def _save(self) -> None:
        if not self.path:
            return
        d = {k: getattr(self, k) for k in ("submit_calls", "cancel_calls", "queue", "available", "next_submit", "cash",
                                           "_n", "_manual")}
        d["orders"] = {k: asdict(v) for k, v in self.orders.items()}
        tmp = Path(self.path + ".tmp")
        tmp.write_text(json.dumps(d), encoding="utf-8")
        tmp.replace(self.path)

    @classmethod
    def load(cls, path: str) -> "FakeBroker":
        b = cls()
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        for k in ("submit_calls", "cancel_calls", "queue", "available", "next_submit", "cash", "_n", "_manual"):
            setattr(b, k, d[k])
        b.orders = {k: FakeOrder(**v) for k, v in d["orders"].items()}
        b.path = path
        return b

    # ---- scripted behaviour
    def script_submit(self, *outcomes: str) -> None:
        """'accept' | 'reject:<reason>' | 'lost_before_record' | 'lost_after_record'"""
        self.next_submit.extend(outcomes)
        self._save()

    def _bid(self) -> str:
        self._n += 1
        return f"FAKE-{self._n:04d}"

    def push(self, update: dict) -> None:
        self.queue.append(dict(update))
        self._save()

    def ack(self, cid: str, update_id: str) -> dict:
        u = {"update_id": update_id, "kind": "broker_ack", "client_order_id": cid,
             "broker_order_id": self.orders[cid].broker_order_id}
        self.push(u)
        return u

    def _position(self, symbol: str) -> int:
        return sum((1 if o.side == "buy" else -1) * o.filled_qty for o in self.orders.values() if o.symbol == symbol)

    def fill(self, cid: str, exec_id: str, qty: int, price: float) -> dict:
        """The broker executes qty at price (recorded at the broker now) and queues the update."""
        from trading.costs import BASE
        o = self.orders[cid]
        if o.status in ("cancelled", "rejected", "filled", "held") or o.filled_qty + qty > o.qty:
            raise ValueError(f"fake broker cannot fill {cid}: {o.status}, {o.filled_qty}/{o.qty}")
        o.executions.append({"exec_id": exec_id, "qty": qty, "price": price})
        o.status = "filled" if o.filled_qty == o.qty else "partially_filled"
        value = qty * price
        self.cash += -value if o.side == "buy" else value - BASE.sell_fee(value)
        u = {"update_id": f"exec-{exec_id}", "kind": "fill", "client_order_id": cid, "broker_order_id": o.broker_order_id,
             "exec_id": exec_id, "qty": qty, "price": price, "cum_qty": o.filled_qty}
        self.queue.append(u)
        if o.status == "filled":                     # documented: bracket legs activate only on a COMPLETE fill
            for leg in [x for x in self.orders.values() if x.parent == cid and x.status == "held"]:
                leg.status = "accepted"
                self.queue.append({"update_id": f"leg-{leg.client_order_id}", "kind": "leg_active",
                                   "client_order_id": leg.client_order_id, "broker_order_id": leg.broker_order_id})
        self._save()
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
        self.queue.append(u)
        if o.status == "cancelled":                  # documented: cancelling one order cancels the rest of the group
            for leg in [x for x in self.orders.values() if x.parent == cid and x.status in OPEN]:
                leg.status = "cancelled"
                self.queue.append({"update_id": f"{update_id}-leg", "kind": "broker_cancelled",
                                   "client_order_id": leg.client_order_id, "broker_order_id": leg.broker_order_id,
                                   "filled_qty": leg.filled_qty, "reason": "parent cancelled (group cancel)"})
        self._save()
        return u

    def manual_trade(self, symbol: str, side: str, qty: int, price: float) -> str:
        """Activity made outside the system (for mismatch tests): a filled order with a foreign id."""
        self._manual += 1
        cid = f"manual-{self._manual}"
        self.orders[cid] = FakeOrder(cid, self._bid(), symbol, side, qty, status="accepted", foreign=True)
        self.fill(cid, f"M{self._manual}", qty, price)
        self.queue = [u for u in self.queue if u.get("client_order_id") != cid]   # not ours: no update for us
        self._save()
        return cid

    def manual_order(self, symbol: str, side: str, qty: int) -> str:
        """An OPEN order placed outside the system (for mismatch tests)."""
        self._manual += 1
        cid = f"manual-{self._manual}"
        self.orders[cid] = FakeOrder(cid, self._bid(), symbol, side, qty, status="accepted", foreign=True)
        self._save()
        return cid

    def forget(self, cid: str) -> None:
        """SIMULATION of 'the broker has no record of this client order id' (for example a wrong account, or a record
        the broker never kept). Used only to prove the core does not treat absence as completion."""
        self.orders.pop(cid, None)
        self._save()

    # ---- the interface the lab uses (a later paper adapter implements the same methods)
    def submit(self, cid: str, symbol: str, side: str, qty: int, spec: dict | None = None) -> dict:
        spec = spec or {}
        self.submit_calls[cid] = self.submit_calls.get(cid, 0) + 1
        if not self.available:
            self._save()
            raise ConnectionLost("broker unreachable during submission (simulated); outcome unknown")
        outcome = self.next_submit.pop(0) if self.next_submit else "accept"
        reject = None
        if cid in self.orders:
            reject = "duplicate client_order_id (fake broker behaviour; real behaviour UNVERIFIED)"
        elif outcome.startswith("reject"):
            reject = outcome.partition(":")[2] or "rejected (synthetic)"
        elif side == "sell":
            open_buy = any(o.symbol == symbol and o.side == "buy" and o.status in ("accepted", "partially_filled")
                           for o in self.orders.values())
            committed = sum(o.qty - o.filled_qty for o in self.orders.values()
                            if o.symbol == symbol and o.side == "sell" and o.status in OPEN)
            if open_buy and spec.get("type") == "stop":
                reject = "wash trade protection: open buy order for the same symbol (HTTP 403, simulated)"
            elif qty > self._position(symbol) - committed:
                reject = "exit order exceeds the existing position (simulated)"
        if reject:
            self._save()
            return {"status": "rejected", "reason": reject, "broker_order_id": None}
        if outcome == "lost_before_record":
            self._save()
            raise ConnectionLost("connection lost before the broker recorded the order (simulated)")
        self.orders[cid] = FakeOrder(cid, self._bid(), symbol, side, qty, order_type=spec.get("type", "limit"),
                                     stop_price=spec.get("stop_price"))
        legs = []
        if spec.get("order_class") == "bracket" and spec.get("stop_loss"):
            lc = f"{cid}:stop"
            self.orders[lc] = FakeOrder(lc, self._bid(), symbol, "sell" if side == "buy" else "buy", qty, status="held",
                                        order_type="stop", stop_price=spec["stop_loss"]["stop_price"], parent=cid)
            legs.append({"client_order_id": lc, "broker_order_id": self.orders[lc].broker_order_id, "status": "held"})
        self._save()
        if outcome == "lost_after_record":
            raise ConnectionLost("connection lost after the broker recorded the order (simulated)")
        return {"status": "accepted", "broker_order_id": self.orders[cid].broker_order_id, "legs": legs}

    def poll(self) -> list[dict]:
        if not self.available:
            raise BrokerUnavailable("broker unavailable (simulated)")
        out, self.queue = self.queue, []
        self._save()
        return out

    def lookup(self, cid: str) -> dict | None:
        if not self.available:
            raise BrokerUnavailable("broker unavailable (simulated)")
        o = self.orders.get(cid)
        return o.view() if o else None

    def request_cancel(self, cid: str) -> dict:
        self.cancel_calls[cid] = self.cancel_calls.get(cid, 0) + 1
        if not self.available:
            self._save()
            raise BrokerUnavailable("broker unavailable (simulated): cancellation request not delivered")
        o = self.orders.get(cid)
        if o is not None and o.status in ("filled", "cancelled", "rejected"):
            self._save()
            return {"status": "not_cancelable", "reason": f"order is {o.status} (HTTP 422, simulated)"}
        if o is not None:
            o.cancel_requested = True
        self._save()
        return {"status": "requested"}

    def positions(self) -> dict:
        if not self.available:
            raise BrokerUnavailable("broker unavailable (simulated)")
        syms = {o.symbol for o in self.orders.values()}
        return {s: q for s in syms if (q := self._position(s))}

    def open_orders(self) -> list[dict]:
        if not self.available:
            raise BrokerUnavailable("broker unavailable (simulated)")
        return [o.view() for o in self.orders.values() if o.status in OPEN]

    def account(self) -> dict:
        if not self.available:
            raise BrokerUnavailable("broker unavailable (simulated)")
        return {"cash": round(self.cash, 6)}
