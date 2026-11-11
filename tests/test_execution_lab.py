"""LOCAL EXECUTION SIMULATION (trading/execution_lab). SYNTHETIC instrument, prices and clock; in-memory fake broker.
These tests also prove isolation: no network, no broker client, no project data stores, no acceptance-critical files."""

import ast
import socket
import sqlite3
import tempfile
from pathlib import Path

import pytest

from trading.execution_lab import ledger as L
from trading.execution_lab import scenarios as S
from trading.execution_lab.fake_broker import FakeBroker
from trading.execution_lab.lab import Clock, Lab, LabConfig

ROOT = Path(__file__).resolve().parents[1]
LAB_DIR = ROOT / "trading" / "execution_lab"


@pytest.fixture(autouse=True)
def no_network_and_no_project_files(monkeypatch):
    """Any socket connection fails the test; every SQLite file opened must be in memory or in the temp folder."""
    real_connect, real_create = socket.socket.connect, socket.create_connection

    def loopback_only(addr):
        host = addr[0] if isinstance(addr, tuple) else str(addr)
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise AssertionError(f"execution lab attempted a network connection to {addr}")

    def connect(self, addr):
        loopback_only(addr)
        return real_connect(self, addr)

    def create(addr, *a, **k):
        loopback_only(addr)
        return real_create(addr, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", create)
    real = sqlite3.connect
    tmp = Path(tempfile.gettempdir()).resolve()

    def guarded(db, *a, **k):
        s = str(db)
        assert s == ":memory:" or s.startswith("file:") is False and tmp in Path(s).resolve().parents, s
        return real(db, *a, **k)
    monkeypatch.setattr(L.sqlite3, "connect", guarded)


@pytest.mark.parametrize("sid", [s for s, _, _ in S.SCENARIOS])
def test_scenario_expectations_and_invariants(sid):
    r = S.run(sid)
    bad = [c for c in r["expectations"] + r["invariants"] if not c["passed"]]
    assert not bad, bad
    assert r["synthetic"] and r["seed"] == 0 and r["config_version"].startswith("lab-")


def test_scenarios_are_reproducible():
    a, b = S.run("s07"), S.run("s07")
    assert [(e["event_id"], e["kind"], e["payload"]) for e in a["events"]] == [(e["event_id"], e["kind"], e["payload"]) for e in b["events"]]
    assert a["snapshots"] == b["snapshots"]


def _lab():
    return Lab(L.Ledger(), FakeBroker(), Clock(S.T0), LabConfig())


def test_duplicate_fill_events_never_duplicate_fills():
    lab = _lab(); lab.mark("SYN", 100.0)
    cid = lab.request_entry("SYN", 10, 100.0, 0.5)["order_id"]
    u = lab.broker.fill(cid, "X1", 4, 100.0)
    for _ in range(3):
        lab.broker.push(u)
    lab.poll()
    o = lab.state()["orders"][cid]
    assert o.filled_qty == 4 and o.remaining_qty == 6 and lab.state()["positions"]["SYN"]["qty"] == 4
    assert len(lab.ledger.duplicates()) == 3


def test_ledger_is_append_only():
    led = L.Ledger()
    led.append("a", "t", "mark", "local", {"symbol": "SYN", "price": 1})
    with pytest.raises(sqlite3.DatabaseError):
        led.db.execute("UPDATE events SET kind='x'")
    with pytest.raises(sqlite3.DatabaseError):
        led.db.execute("DELETE FROM events")


def test_invalid_transition_is_flagged_not_applied():
    ev = [{"seq": 1, "event_id": "1", "ts_utc": "t", "kind": "intent_created", "order_id": "o", "source": "local",
           "config_version": "c", "payload": {"symbol": "SYN", "side": "buy", "qty": 5, "ref_price": 1.0, "purpose": "entry"}},
          {"seq": 2, "event_id": "2", "ts_utc": "t", "kind": "broker_ack", "order_id": "o", "source": "broker",
           "config_version": "c", "payload": {"broker_order_id": "B"}}]
    o = L.derive(ev, 100.0)["orders"]["o"]
    assert o.state == L.CREATED and o.anomalies             # an ack for a never-submitted order is an anomaly
    assert not L.can_transition(L.UNKNOWN, L.SUBMISSION_PENDING) and not L.can_transition(L.CANCEL_PENDING, L.ACCEPTED)


def test_unknown_outcome_blocks_resubmission_and_is_never_a_rejection():
    lab = _lab(); lab.mark("SYN", 100.0)
    lab.broker.script_submit("lost_before_record")
    cid = lab.request_entry("SYN", 10, 100.0, 0.5)["order_id"]
    for _ in range(3):
        assert lab.retry_submit(cid)["submitted"] is False
    lab.reconcile(); lab.reconcile()
    o = lab.state()["orders"][cid]
    assert o.state == L.UNKNOWN and lab.broker.submit_calls[cid] == 1 and lab.state()["pending_exposure"] == 1000.0


def test_restart_preserves_outstanding_obligations(tmp_path):
    p = tempfile.mktemp(suffix=".sqlite")
    try:
        clock = Clock(S.T0); b = FakeBroker()
        lab = Lab(L.Ledger(p), b, clock, LabConfig()); lab.mark("SYN", 100.0)
        cid = lab.request_entry("SYN", 10, 100.0, 0.5)["order_id"]; lab.cancel(cid, "x")
        lab.ledger.close()
        lab2 = Lab(L.Ledger(p), b, clock, LabConfig(), restart=True)
        st = lab2.state()
        assert st["orders"][cid].state == L.CANCEL_PENDING and st["flags"]["reconciliation_required"]
        assert st["pending_exposure"] == 1000.0
        lab2.ledger.close()
    finally:
        Path(p).unlink(missing_ok=True)


def test_emergency_stop_can_complete_only_when_everything_is_resolved():
    lab = _lab(); lab.mark("SYN", 100.0)
    cid = lab.request_entry("SYN", 10, 100.0, 0.5)["order_id"]        # accepted, unfilled
    rep = lab.emergency_stop("drill")
    assert rep["overall"] == "INCOMPLETE"
    lab.broker.confirm_cancel(cid, "c1"); lab.poll()
    assert lab.stop_report()["overall"] == "INCOMPLETE"                  # not yet reconciled
    lab.reconcile()
    rep = lab.stop_report()
    assert rep["overall"] == "COMPLETE" and not rep["unresolved"] and rep["remaining_exposure"] == 0


def test_stop_reports_incomplete_while_any_exposure_or_order_remains():
    for sid in ("s11", "s12"):
        r = S.run(sid)
        assert r["emergency_stop"]["overall"] == "INCOMPLETE" and r["emergency_stop"]["unresolved"]


def test_pending_orders_count_toward_exposure_used_by_the_risk_gate():
    lab = _lab(); lab.mark("SYN", 100.0)
    lab.request_entry("SYN", 50, 100.0, 0.5)                             # 5% pending (owner baseline notional cap)
    chk = lab.entry_check("SYN", 60, 100.0, 0.5, 5)
    assert chk["gross_exposure_in_use"] == 5000.0 and not chk["allowed"] and chk["allowed_shares"] == 50


def test_reuses_the_approved_risk_and_cost_definitions():
    from trading import costs, risk
    cfg = LabConfig()
    assert cfg.limits is risk.OWNER_BASELINE_2026_11_03 and cfg.limits.placeholder is False
    assert cfg.costs is costs.BASE


def test_lab_has_no_network_broker_client_or_credential_code():
    forbidden_mods = ("trading.alpaca_client", "requests", "urllib", "http", "socket", "trading.operations",
                      "trading.monitor", "trading.safety", "anthropic")
    for f in LAB_DIR.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(src)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for m in mods:
                assert not m.startswith(forbidden_mods), (f.name, m)
        for word in (".env", "APCA_", "paper-api", "api.alpaca", "data.alpaca", "ORDER_SUBMISSION_ENABLED"):
            assert word not in src, (f.name, word)


def test_acceptance_critical_files_do_not_reference_the_lab():
    for rel in ["trading/sessions.py", "trading/safety.py", "trading/alpaca_client.py", *[
            str(p.relative_to(ROOT)) for p in (ROOT / "trading" / "operations").glob("*.py")]]:
        assert "execution_lab" not in (ROOT / rel).read_text(encoding="utf-8"), rel


def test_api_serves_the_same_records_and_writes_nothing(tmp_path, monkeypatch):
    """The city endpoint (read-only preview) returns exactly what the scenario runner derives."""
    import json
    import threading
    import urllib.request
    from trading.dashboard import server
    from trading.monitor import store as mst
    monkeypatch.setattr(server, "READ_ONLY_PREVIEW", False)
    monkeypatch.setattr(mst, "READ_ONLY_VIEW", False)
    monkeypatch.setenv("TRADING_OPS_DIR", str(tmp_path / "ops"))
    httpd, _c, stop = server.create_server(server.DEFAULT_CONFIG, 0, 3600, read_only=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_address[1]}/api/execution-lab?scenario=s11", timeout=60) as r:
            api = json.loads(r.read())
    finally:
        stop.set(); httpd.shutdown(); httpd.server_close()
    direct = S.run("s11")
    assert api["mode"] == "LOCAL_EXECUTION_SIMULATION" and api["selected"]["id"] == "s11"
    assert api["selected"]["orders"] == json.loads(json.dumps(direct["orders"]))
    assert api["selected"]["emergency_stop"]["overall"] == "INCOMPLETE" and len(api["scenarios"]) == 12
    assert all(s["passed"] for s in api["scenarios"]) and api["policy_gaps"]
