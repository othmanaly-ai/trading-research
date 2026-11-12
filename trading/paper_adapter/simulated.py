"""SIMULATED Alpaca paper Trading API: an offline transport for the paper adapter. Nothing here touches a network.

It answers the documented endpoints the adapter uses, in the documented JSON shapes (numbers as strings), from the
execution lab's durable fake broker (`FakeBroker`, saved to a JSON file so it outlives a client process). It exists so
that the REAL adapter code path (request building, response mapping, guarded writes, lookups, fills from activities,
reconciliation) can be exercised end to end, including fresh-process restarts, without any broker.

It is a model, not the broker. Behaviour the documentation does not state is marked SIMULATED/UNVERIFIED:
- the 404 status and body for an unknown client order id;
- 422 for a reused client order id;
- whether an open bracket leg of a filled parent is listed at the top level of GET /v2/orders?status=open&nested=true
  (here: yes, as its own entry);
- activity ids equal to execution ids;
- partial-fill timing, fill prices and cash arithmetic (the fake broker's BASE sell fee).
A passing test here proves our handling of these modelled responses, never Alpaca's real behaviour.
"""

from __future__ import annotations

from trading.execution_lab.fake_broker import OPEN, BrokerUnavailable, ConnectionLost, FakeBroker

PAPER_HOST = "https://paper-api.alpaca.markets"
SIMULATED_ACCOUNT_ID = "SIMULATED-PAPER-ACCOUNT"          # not a real account; its reference is used only in tests
STATUS_OUT = {"accepted": "new", "partially_filled": "partially_filled", "filled": "filled", "cancelled": "canceled",
              "rejected": "rejected", "held": "held"}


class SimulatedPaperTransport:
    """Transport protocol (see alpaca_orders.Transport) over a FakeBroker. `simulated` marks it for the test guard."""

    simulated = True

    def __init__(self, broker: FakeBroker, host: str = PAPER_HOST, market_open: bool = True,
                 account_status: str = "ACTIVE", account_id: str = SIMULATED_ACCOUNT_ID, trading_blocked: bool = False):
        self.b, self.host, self.market_open = broker, host, market_open
        self.account_status, self.account_id, self.trading_blocked = account_status, account_id, trading_blocked
        self.requests: list[dict] = []

    # ---- JSON shapes
    def _order(self, o) -> dict:
        legs = [self._order(x) for x in self.b.orders.values() if x.parent == o.client_order_id]
        px = [e["price"] for e in o.executions]
        avg = sum(e["price"] * e["qty"] for e in o.executions) / o.filled_qty if o.filled_qty else None
        return {"id": o.broker_order_id, "client_order_id": o.client_order_id, "status": STATUS_OUT[o.status],
                "symbol": o.symbol, "side": o.side, "qty": str(o.qty), "filled_qty": str(o.filled_qty),
                "filled_avg_price": f"{avg:.4f}" if px else None, "type": o.order_type, "time_in_force": "day",
                "order_class": "bracket" if legs else "simple", "legs": legs or None,
                "stop_price": None if o.stop_price is None else f"{o.stop_price:.2f}"}

    def _activities(self) -> list[dict]:
        out = []
        for o in self.b.orders.values():
            cum = 0
            for e in o.executions:
                cum += e["qty"]
                out.append({"id": e["exec_id"], "activity_type": "FILL", "order_id": o.broker_order_id,
                            "symbol": o.symbol, "side": o.side, "qty": str(e["qty"]), "price": str(e["price"]),
                            "cum_qty": str(cum), "leaves_qty": str(o.qty - cum), "transaction_time": "SIMULATED"})
        return out

    # ---- the Transport protocol
    def request(self, method, path, params=None, body=None):
        self.requests.append({"method": method, "path": path, "params": params, "body": body})
        if not self.b.available:
            raise TimeoutError(f"simulated: no response to {method} {path}")
        params = params or {}
        if method == "POST" and path == "/v2/orders":
            spec = {"type": body["type"], "time_in_force": body["time_in_force"],
                    "order_class": body.get("order_class", "simple")}
            for k in ("limit_price", "stop_price"):
                if body.get(k) is not None:
                    spec[k] = float(body[k])
            if body.get("stop_loss"):
                spec["stop_loss"] = {"stop_price": float(body["stop_loss"]["stop_price"])}
            try:
                r = self.b.submit(body["client_order_id"], body["symbol"], body["side"], int(body["qty"]), spec)
            except ConnectionLost as exc:
                raise TimeoutError(f"simulated: {exc}") from exc
            if r["status"] == "rejected":
                code = 422 if "duplicate" in r["reason"] else 403      # 422 for reuse: SIMULATED, real behaviour UNVERIFIED
                return code, {"code": code * 100000, "message": r["reason"]}
            return 200, self._order(self.b.orders[body["client_order_id"]])
        if method == "GET" and path == "/v2/orders:by_client_order_id":
            o = self.b.orders.get(params.get("client_order_id"))
            if o is None or o.foreign:
                return 404, {"code": 40410000, "message": "order not found (SIMULATED; real status UNVERIFIED)"}
            return 200, self._order(o)
        if method == "DELETE" and path.startswith("/v2/orders/"):
            bid = path.rsplit("/", 1)[1]
            o = next((x for x in self.b.orders.values() if x.broker_order_id == bid), None)
            if o is None:
                return 404, {"message": "order not found (SIMULATED)"}
            try:
                r = self.b.request_cancel(o.client_order_id)
            except BrokerUnavailable as exc:
                raise TimeoutError(f"simulated: {exc}") from exc
            return (204, None) if r["status"] == "requested" else (422, {"message": r.get("reason")})
        if method == "GET" and path == "/v2/account/activities/FILL":
            return 200, self._activities()
        if method == "GET" and path == "/v2/positions":
            return 200, [{"symbol": s, "qty": str(q), "side": "long" if q > 0 else "short"}
                         for s, q in self.b.positions().items()]
        if method == "GET" and path == "/v2/orders":
            if params.get("status") != "open":
                raise AssertionError("simulated transport lists open orders only")
            top = [o for o in self.b.orders.values() if o.status in OPEN
                   and not (o.parent and self.b.orders.get(o.parent) and self.b.orders[o.parent].status in OPEN)]
            return 200, [self._order(o) for o in top]
        if method == "GET" and path == "/v2/account":
            return 200, {"id": self.account_id, "status": self.account_status, "currency": "USD",
                         "cash": repr(round(self.b.cash, 6)), "trading_blocked": self.trading_blocked,
                         "account_blocked": False, "pattern_day_trader": False}
        if method == "GET" and path == "/v2/clock":
            return 200, {"is_open": self.market_open, "timestamp": "SIMULATED"}
        raise AssertionError(f"simulated transport: unsupported {method} {path}")


def simulated_only_guard(transport):
    """A write guard for tests and drills that passes ONLY for the simulated transport. The real guard
    (`trading.safety.require_order_submission_allowed`) is untouched and still refuses; no environment flag is set."""
    def guard():
        if not isinstance(transport, SimulatedPaperTransport):
            raise PermissionError("simulated-only guard used with a non-simulated transport: refused")
    return guard
