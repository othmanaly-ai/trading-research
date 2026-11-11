"""Alpaca paper Trading API mapping for the execution core: OFFLINE ONLY (fixture transport).

DOCUMENTED (docs.alpaca.markets/us, checked 2026-11-10/11):
- POST /v2/orders: body symbol, qty, side, type, time_in_force, limit_price, stop_price, client_order_id (<= 128 chars),
  order_class (simple | bracket | oco | oto), stop_loss {stop_price[, limit_price]}, take_profit {limit_price}.
  200 returns the order object; 403 "buying power or shares is not sufficient" (also wash-trade rejections);
  422 "input parameters are not recognized".
- Order object: id, client_order_id, status, qty, filled_qty, filled_avg_price (decimal STRINGS), legs, order_class,
  side, symbol, type, time_in_force, limit_price, stop_price, timestamps.
- GET /v2/orders:by_client_order_id?client_order_id=... returns one order object.
- DELETE /v2/orders/{order_id}: 204 = cancellation request accepted; 422 = no longer cancelable. A 204 is NOT a
  confirmed cancellation; the order's later status decides.
- GET /v2/orders?status=open lists open orders; GET /v2/positions; GET /v2/account (cash).
- Bracket legs stay inactive until the entry is completely filled; cancelling one order cancels the group.
- REST fill activities (GET /v2/account/activities/FILL): id, order_id, qty, cum_qty, leaves_qty, transaction_time.

UNVERIFIED (assumptions; must be established in an authorized paper test):
- The status code and body when no order matches a client order id (treated here: 404 = not found; anything else
  = broker unavailable, never "not found").
- Fill activity fields price, side, symbol (used here); whether activity ids equal the stream's execution_id (this
  adapter uses REST activities as its ONLY fill source, so ids are never mixed).
- Whether a reused client_order_id is rejected.
- The name and lifecycle of the inactive bracket-leg status (treated here as "held").
"""

from __future__ import annotations

from typing import Protocol

from trading.execution_lab.fake_broker import BrokerUnavailable, ConnectionLost

ORDER_STATUS = {      # Alpaca status -> execution-core status
    "new": "accepted", "accepted": "accepted", "pending_new": "accepted", "accepted_for_bidding": "accepted",
    "partially_filled": "partially_filled", "filled": "filled", "canceled": "cancelled", "expired": "cancelled",
    "rejected": "rejected", "pending_cancel": "accepted", "held": "held", "done_for_day": "accepted",
}
UNSUPPORTED_STATUS = {"replaced", "pending_replace", "stopped", "suspended", "calculated"}


class Transport(Protocol):
    def request(self, method: str, path: str, params: dict | None = None, body: dict | None = None) -> tuple[int, object]:
        """Return (HTTP status, decoded JSON). Raise TimeoutError when no response arrives."""


class FixtureTransport:
    """Replays scripted (status, body) responses in order, matched on method and path prefix. OFFLINE: no network.
    A response of ("timeout", None) raises TimeoutError. Every request is recorded for inspection."""

    def __init__(self, script: list[tuple[str, str, object, object]]):
        self.script = list(script)       # (method, path_prefix, status_or_"timeout", body)
        self.requests: list[dict] = []

    def request(self, method, path, params=None, body=None):
        self.requests.append({"method": method, "path": path, "params": params, "body": body})
        for i, (m, prefix, status, resp) in enumerate(self.script):
            if m == method and path.startswith(prefix):
                del self.script[i]
                if status == "timeout":
                    raise TimeoutError(f"no response to {method} {path} (fixture)")
                return status, resp
        raise AssertionError(f"no fixture for {method} {path}")


def build_order_request(cid: str, symbol: str, side: str, qty: int, spec: dict) -> dict:
    """The documented POST /v2/orders body. Numbers are sent as strings, as in the documentation examples."""
    body = {"symbol": symbol, "qty": str(qty), "side": side, "type": spec["type"],
            "time_in_force": spec["time_in_force"], "client_order_id": cid}
    if len(cid) > 128:
        raise ValueError("client_order_id longer than 128 characters (documented limit)")
    if spec.get("limit_price") is not None:
        body["limit_price"] = f"{spec['limit_price']:.2f}"
    if spec.get("stop_price") is not None:
        body["stop_price"] = f"{spec['stop_price']:.2f}"
    if spec.get("order_class") and spec["order_class"] != "simple":
        body["order_class"] = spec["order_class"]
        if spec.get("stop_loss"):
            body["stop_loss"] = {"stop_price": f"{spec['stop_loss']['stop_price']:.2f}"}
    return body


def _num(x) -> float:
    return float(x) if x not in (None, "") else 0.0


class AlpacaPaperOrderAdapter:
    """The execution core's broker port over Alpaca's paper API, through an injected transport."""

    def __init__(self, transport: Transport, guard=None):
        from trading.safety import require_order_submission_allowed
        self.t = transport
        self.guard = guard or require_order_submission_allowed
        self.submit_calls: dict[str, int] = {}
        self.cancel_calls: dict[str, int] = {}
        self._ids: dict[str, str] = {}            # client order id -> broker order id
        self._seen_fills: set[str] = set()
        self._last_status: dict[str, str] = {}

    def _write_allowed(self) -> str | None:
        try:
            self.guard()
            return None
        except Exception as exc:                  # OrderSubmissionDisabled or anything else: never send
            return f"LOCAL GUARD REFUSED: {exc}"

    # ---- writes (guarded)
    def submit(self, cid, symbol, side, qty, spec=None):
        self.submit_calls[cid] = self.submit_calls.get(cid, 0) + 1
        refusal = self._write_allowed()
        if refusal:
            return {"status": "rejected", "reason": refusal, "broker_order_id": None, "local": True}
        if not spec:
            return {"status": "rejected", "reason": "LOCAL: no order spec (policy unset)", "broker_order_id": None, "local": True}
        body = build_order_request(cid, symbol, side, qty, spec)
        try:
            status, js = self.t.request("POST", "/v2/orders", body=body)
        except TimeoutError as exc:
            raise ConnectionLost(f"no response to POST /v2/orders: {exc}") from exc
        if status == 200:
            self._ids[cid] = js["id"]
            legs = [{"client_order_id": f"{cid}:stop", "broker_order_id": l.get("id"), "status": l.get("status")}
                    for l in (js.get("legs") or []) if l.get("type") in ("stop", "stop_limit")]
            return {"status": "accepted", "broker_order_id": js["id"], "legs": legs}
        if status in (403, 422):
            msg = js.get("message") if isinstance(js, dict) else str(js)
            return {"status": "rejected", "reason": f"HTTP {status}: {msg}", "broker_order_id": None}
        raise ConnectionLost(f"unexpected HTTP {status} on submission: outcome unknown")

    def request_cancel(self, cid):
        self.cancel_calls[cid] = self.cancel_calls.get(cid, 0) + 1
        refusal = self._write_allowed()
        if refusal:
            raise BrokerUnavailable(refusal)
        bid = self._ids.get(cid) or (self.lookup(cid) or {}).get("broker_order_id")
        if not bid:
            raise BrokerUnavailable("cannot cancel: broker order id unknown (order not found)")
        try:
            status, js = self.t.request("DELETE", f"/v2/orders/{bid}")
        except TimeoutError as exc:
            raise BrokerUnavailable(f"no response to cancel: {exc}") from exc
        if status == 204:
            return {"status": "requested"}
        if status == 422:
            return {"status": "not_cancelable", "reason": "HTTP 422: order no longer cancelable"}
        raise BrokerUnavailable(f"unexpected HTTP {status} on cancel")

    # ---- reads
    def _get(self, path, params=None):
        try:
            status, js = self.t.request("GET", path, params=params)
        except TimeoutError as exc:
            raise BrokerUnavailable(str(exc)) from exc
        return status, js

    def _fills_for(self, bid: str) -> list[dict]:
        status, js = self._get("/v2/account/activities/FILL", {"direction": "asc"})
        if status != 200 or not isinstance(js, list):
            raise BrokerUnavailable(f"fill activities unavailable (HTTP {status})")
        return [{"exec_id": a["id"], "qty": int(_num(a["qty"])), "price": _num(a["price"])} for a in js
                if a.get("order_id") == bid]

    def lookup(self, cid):
        status, js = self._get("/v2/orders:by_client_order_id", {"client_order_id": cid, "nested": "true"})
        if status == 404:                         # UNVERIFIED: documented 200 only; 404 assumed to mean not found
            return None
        if status != 200 or not isinstance(js, dict):
            raise BrokerUnavailable(f"lookup failed (HTTP {status}): not treated as 'not found'")
        if js.get("status") in UNSUPPORTED_STATUS:
            raise BrokerUnavailable(f"unsupported order status {js['status']!r}: owner review")
        self._ids[cid] = js["id"]
        return {"broker_order_id": js["id"], "client_order_id": cid, "status": ORDER_STATUS.get(js["status"], "accepted"),
                "filled_qty": int(_num(js.get("filled_qty"))), "qty": int(_num(js.get("qty"))),
                "executions": self._fills_for(js["id"]), "symbol": js.get("symbol"), "side": js.get("side")}

    def poll(self):
        """Fills from REST activities (the single fill source), plus status changes of known orders."""
        status, acts = self._get("/v2/account/activities/FILL", {"direction": "asc"})
        if status != 200 or not isinstance(acts, list):
            raise BrokerUnavailable(f"fill activities unavailable (HTTP {status})")
        by_bid = {v: k for k, v in self._ids.items()}
        out = []
        for a in acts:
            cid = by_bid.get(a.get("order_id"))
            if cid is None or a["id"] in self._seen_fills:
                continue
            self._seen_fills.add(a["id"])
            out.append({"update_id": f"act-{a['id']}", "kind": "fill", "client_order_id": cid, "broker_order_id": a["order_id"],
                        "exec_id": a["id"], "qty": int(_num(a["qty"])), "price": _num(a["price"]),
                        "cum_qty": int(_num(a.get("cum_qty")))})
        for cid, bid in list(self._ids.items()):
            st, js = self._get("/v2/orders:by_client_order_id", {"client_order_id": cid, "nested": "true"})
            if st != 200:
                continue
            s = js.get("status")
            if s != self._last_status.get(cid):
                self._last_status[cid] = s
                if s in ("canceled", "expired"):
                    out.append({"update_id": f"st-{bid}-{s}", "kind": "broker_cancelled", "client_order_id": cid,
                                "broker_order_id": bid, "filled_qty": int(_num(js.get("filled_qty")))})
                elif s == "rejected":
                    out.append({"update_id": f"st-{bid}-{s}", "kind": "broker_reject", "client_order_id": cid,
                                "broker_order_id": bid, "reason": "rejected after acceptance"})
            for leg in js.get("legs") or []:
                lc = f"{cid}:stop"
                active = leg.get("type") in ("stop", "stop_limit") and leg.get("status") in ("new", "accepted")
                if active and self._last_status.get(lc) != "active":
                    self._last_status[lc] = "active"
                    self._ids.setdefault(lc, leg.get("id"))
                    out.append({"update_id": f"leg-{leg.get('id')}", "kind": "leg_active", "client_order_id": lc,
                                "broker_order_id": leg.get("id")})
        return out

    def positions(self):
        status, js = self._get("/v2/positions")
        if status != 200 or not isinstance(js, list):
            raise BrokerUnavailable(f"positions unavailable (HTTP {status})")
        return {p["symbol"]: int(_num(p["qty"])) for p in js if _num(p.get("qty"))}

    def open_orders(self):
        status, js = self._get("/v2/orders", {"status": "open", "nested": "true", "limit": 500})
        if status != 200 or not isinstance(js, list):
            raise BrokerUnavailable(f"open orders unavailable (HTTP {status})")
        if len(js) >= 500:
            raise BrokerUnavailable("open-order page full: list may be truncated")
        return [{"client_order_id": o.get("client_order_id"), "symbol": o.get("symbol"), "side": o.get("side"),
                 "qty": int(_num(o.get("qty"))), "status": o.get("status")} for o in js]

    def account(self):
        status, js = self._get("/v2/account")
        if status != 200 or not isinstance(js, dict):
            raise BrokerUnavailable(f"account unavailable (HTTP {status})")
        return {"cash": _num(js.get("cash"))}
