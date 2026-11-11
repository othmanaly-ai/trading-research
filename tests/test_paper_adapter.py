"""PROPOSED Alpaca paper adapter, OFFLINE: fixtures written from the official documentation's JSON shapes. These tests
prove the mapping and the safety wiring; they cannot prove real broker behaviour. No network: any non-loopback
connection fails the test. No order can be sent: no network transport exists."""

import ast
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from trading.execution_lab import ledger as L
from trading.execution_lab.lab import Clock, Lab, LabConfig
from trading.execution_lab.policy import LAB_TEST_POLICY
from trading.paper_adapter.alpaca_orders import AlpacaPaperOrderAdapter, FixtureTransport, build_order_request

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2030, 6, 3, 14, 5, tzinfo=timezone.utc)
CID = "lab-synthetic-v1:2030-06-03:0001"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("adapter test attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def writes_enabled(monkeypatch):
    """Isolated to this test process: lets the REAL guard pass so the fixture path can be exercised."""
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "true")


def order(oid, status, qty="40", filled="0", avg=None, legs=None, cid=CID):
    """An order object in the documented shape (numeric fields are strings)."""
    return {"id": oid, "client_order_id": cid, "status": status, "symbol": "SYN", "side": "buy", "qty": qty,
            "filled_qty": filled, "filled_avg_price": avg, "type": "limit", "time_in_force": "day",
            "order_class": "simple" if not legs else "bracket", "legs": legs, "limit_price": "100.00"}


def lab_with(script, enabled=True):
    t = FixtureTransport(script)
    a = AlpacaPaperOrderAdapter(t)
    lab = Lab(L.Ledger(), a, Clock(T0), LabConfig(), policy=LAB_TEST_POLICY)
    lab.mark("SYN", 100.0)
    return lab, a, t


def test_guard_refuses_by_default_and_nothing_is_sent(monkeypatch):
    monkeypatch.delenv("ORDER_SUBMISSION_ENABLED", raising=False)
    lab, a, t = lab_with([])
    r = lab.request_entry("SYN", 40, 100.0, 0.5)
    o = lab.state()["orders"][r["order_id"]]
    assert o.state == L.REJECTED and "LOCAL GUARD REFUSED" in o.reasons[0] and t.requests == []


def test_request_body_matches_the_documented_fields():
    body = build_order_request(CID, "SYN", "buy", 40, {"type": "limit", "time_in_force": "day", "limit_price": 100.0,
                                                      "order_class": "bracket", "stop_loss": {"stop_price": 99.5}})
    assert body == {"symbol": "SYN", "qty": "40", "side": "buy", "type": "limit", "time_in_force": "day",
                    "client_order_id": CID, "limit_price": "100.00", "order_class": "bracket",
                    "stop_loss": {"stop_price": "99.50"}}
    with pytest.raises(ValueError):
        build_order_request("x" * 129, "SYN", "buy", 1, {"type": "limit", "time_in_force": "day"})


def test_accept_fill_and_full_reconciliation_of_orders_fills_positions_and_cash(writes_enabled):
    fill = {"id": "A1", "order_id": "B-1", "qty": "40", "price": "100.02", "cum_qty": "40", "leaves_qty": "0",
            "side": "buy", "symbol": "SYN", "transaction_time": "2030-06-03T14:05:03Z"}
    lab, a, t = lab_with([
        ("POST", "/v2/orders", 200, order("B-1", "new")),
        ("GET", "/v2/account/activities/FILL", 200, [fill, fill]),             # duplicated activity
        ("GET", "/v2/orders:by_client_order_id", 200, order("B-1", "filled", filled="40", avg="100.02")),
        ("GET", "/v2/positions", 200, [{"symbol": "SYN", "qty": "40", "side": "long"}]),
        ("GET", "/v2/orders", 200, []),
        ("GET", "/v2/account", 200, {"cash": "95999.2", "status": "ACTIVE"}),
    ])
    r = lab.request_entry("SYN", 40, 100.0, 0.5)
    assert t.requests[0]["method"] == "POST" and t.requests[0]["body"]["client_order_id"] == r["order_id"]
    assert lab.state()["orders"][r["order_id"]].state == L.ACCEPTED       # an acknowledgement is not a fill
    p = lab.poll()
    o = lab.state()["orders"][r["order_id"]]
    assert p["stored"] == 1 and o.state == L.FILLED and o.filled_qty == 40
    rec = lab.reconcile()
    assert rec["ok"] and rec["positions_match"] and rec["broker_cash"] == 95999.2 and rec["discrepancies"] == []


@pytest.mark.parametrize("status, msg", [(403, "insufficient buying power"), (403, "potential wash trade detected"),
                                         (422, "input parameters are not recognized")])
def test_broker_rejections_are_recorded_with_their_reason(writes_enabled, status, msg):
    lab, a, t = lab_with([("POST", "/v2/orders", status, {"code": 40310000, "message": msg})])
    r = lab.request_entry("SYN", 40, 100.0, 0.5)
    o = lab.state()["orders"][r["order_id"]]
    assert o.state == L.REJECTED and f"HTTP {status}" in o.reasons[0] and msg in o.reasons[0]


def test_timeout_is_unknown_404_keeps_it_unknown_and_nothing_is_resubmitted(writes_enabled):
    lab, a, t = lab_with([
        ("POST", "/v2/orders", "timeout", None),
        ("GET", "/v2/orders:by_client_order_id", 404, {"message": "order not found"}),
        ("GET", "/v2/positions", 200, []), ("GET", "/v2/orders", 200, []), ("GET", "/v2/account", 200, {"cash": "100000"}),
    ])
    r = lab.request_entry("SYN", 40, 100.0, 0.5)
    assert lab.state()["orders"][r["order_id"]].state == L.UNKNOWN
    assert lab.retry_submit(r["order_id"])["submitted"] is False
    rec = lab.reconcile()
    assert not rec["ok"] and lab.state()["orders"][r["order_id"]].state == L.UNKNOWN
    assert [x["method"] for x in t.requests].count("POST") == 1


def test_lookup_server_error_is_never_not_found(writes_enabled):
    lab, a, t = lab_with([("POST", "/v2/orders", "timeout", None),
                          ("GET", "/v2/orders:by_client_order_id", 500, {"message": "internal error"})])
    r = lab.request_entry("SYN", 40, 100.0, 0.5)
    rec = lab.reconcile()
    assert not rec["ok"] and "error" in rec and lab.state()["orders"][r["order_id"]].state == L.UNKNOWN


def test_unknown_resolved_when_the_broker_shows_the_order(writes_enabled):
    lab, a, t = lab_with([
        ("POST", "/v2/orders", "timeout", None),
        ("GET", "/v2/orders:by_client_order_id", 200, order("B-7", "accepted")),
        ("GET", "/v2/account/activities/FILL", 200, []),
        ("GET", "/v2/positions", 200, []), ("GET", "/v2/orders", 200, [{"client_order_id": CID, "symbol": "SYN",
                                                                        "side": "buy", "qty": "40", "status": "accepted"}]),
        ("GET", "/v2/account", 200, {"cash": "100000"}),
    ])
    r = lab.request_entry("SYN", 40, 100.0, 0.5)
    rec = lab.reconcile()
    assert rec["ok"] and lab.state()["orders"][r["order_id"]].state == L.ACCEPTED


def test_cancel_204_is_a_request_not_a_cancellation_and_422_is_not_cancelable(writes_enabled):
    lab, a, t = lab_with([
        ("POST", "/v2/orders", 200, order("B-2", "new")),
        ("DELETE", "/v2/orders/B-2", 204, None),
        ("GET", "/v2/account/activities/FILL", 200, []),
        ("GET", "/v2/orders:by_client_order_id", 200, order("B-2", "canceled")),
    ])
    r = lab.request_entry("SYN", 40, 100.0, 0.5)
    c = lab.cancel(r["order_id"], "test")
    assert c["requested"] and lab.state()["orders"][r["order_id"]].state == L.CANCEL_PENDING
    lab.poll()
    assert lab.state()["orders"][r["order_id"]].state == L.CANCELLED
    lab2, a2, t2 = lab_with([("POST", "/v2/orders", 200, order("B-3", "new")),
                             ("DELETE", "/v2/orders/B-3", 422, {"message": "order is not cancelable"})])
    r2 = lab2.request_entry("SYN", 40, 100.0, 0.5)
    c2 = lab2.cancel(r2["order_id"], "test")
    assert not c2["requested"] and "NOT CANCELABLE" in c2["status"] and lab2.state()["orders"][r2["order_id"]].state == L.ACCEPTED


def test_cancel_is_guarded_too(monkeypatch, writes_enabled):
    lab, a, t = lab_with([("POST", "/v2/orders", 200, order("B-4", "new"))])
    r = lab.request_entry("SYN", 40, 100.0, 0.5)
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "false")
    c = lab.cancel(r["order_id"], "test")
    assert not c["requested"] and "LOCAL GUARD REFUSED" in c["status"]
    assert [x["method"] for x in t.requests] == ["POST"]


def test_unsupported_status_is_escalated_not_guessed(writes_enabled):
    lab, a, t = lab_with([("POST", "/v2/orders", "timeout", None),
                          ("GET", "/v2/orders:by_client_order_id", 200, order("B-5", "replaced"))])
    lab.request_entry("SYN", 40, 100.0, 0.5)
    rec = lab.reconcile()
    assert not rec["ok"] and "unsupported order status" in rec["error"]


def _imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


def test_adapter_is_unreachable_from_dashboard_dry_run_and_lab():
    for d in ("trading/dashboard", "trading/operations", "trading/execution_lab", "trading/monitor"):
        for f in (ROOT / d).glob("*.py"):
            assert not any(m.startswith("trading.paper_adapter") for m in _imports(f)), f
            assert "paper_adapter" not in f.read_text(encoding="utf-8"), f
    for f in (ROOT / "trading").glob("*.py"):
        assert not any(m.startswith("trading.paper_adapter") for m in _imports(f)), f


def test_adapter_has_no_network_transport_and_guards_every_write():
    src = (ROOT / "trading/paper_adapter/alpaca_orders.py").read_text(encoding="utf-8")
    mods = list(_imports(ROOT / "trading/paper_adapter/alpaca_orders.py"))
    assert not any(m.startswith(("requests", "urllib", "http", "socket", "trading.alpaca_client")) for m in mods), mods
    assert "require_order_submission_allowed" in src
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AlpacaPaperOrderAdapter")
    for fn in cls.body:
        if isinstance(fn, ast.FunctionDef):
            body = ast.unparse(fn)
            if '"POST"' in body or '"DELETE"' in body:          # every write method checks the guard first
                assert "_write_allowed()" in body.split('"POST"')[0].split('"DELETE"')[0], fn.name
    transports = [n.name for n in tree.body if isinstance(n, ast.ClassDef) and "Transport" in n.name]
    assert transports == ["Transport", "FixtureTransport"]


def test_no_module_in_the_repository_can_send_an_http_write():
    """No HTTP write anywhere in trading/: no requests.post/put/patch/delete, no session write calls, no urllib Request
    with a write method. (Existing urllib uses are read-only GETs of the local city server's health endpoints.)"""
    import re
    pat = re.compile(r"requests\.(post|put|patch|delete)\(|\.(post|put|patch|delete)\(\s*(url|f?['\"]http)|"
                     r"method\s*=\s*['\"](POST|PUT|PATCH|DELETE)['\"]")
    hits = [f for f in (ROOT / "trading").rglob("*.py") if pat.search(f.read_text(encoding="utf-8"))]
    assert hits == [], hits
