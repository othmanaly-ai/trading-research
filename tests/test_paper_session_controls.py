"""Paper-session controls, OFFLINE: kill switch, paper-only account checks, session preflight, the planned mechanics
sequence and fresh-process restart recovery, all against the SIMULATED Alpaca API (a model of documented responses).
No network: any non-loopback connection fails the test. The real order-submission guard is never relaxed here."""

import json
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from trading.execution_lab import intended_account
from trading.execution_lab import ledger as L
from trading.execution_lab.fake_broker import FakeBroker
from trading.execution_lab.lab import Clock, Lab, LabConfig
from trading.execution_lab.policy import APPROVED, LAB_TEST_POLICY
from trading.paper_adapter import controls as C
from trading.paper_adapter import drills
from trading.paper_adapter.alpaca_orders import AlpacaPaperOrderAdapter
from trading.paper_adapter.simulated import SIMULATED_ACCOUNT_ID, SimulatedPaperTransport, simulated_only_guard

T0 = datetime(2030, 6, 3, 14, 5, tzinfo=timezone.utc)
SIM_REF = intended_account.account_ref(SIMULATED_ACCOUNT_ID)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("test attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


class Switch:
    def __init__(self, on=False, reason="owner test", broken=False):
        self.on, self.reason, self.broken = on, reason, broken

    def __call__(self):
        if self.broken:
            raise OSError("unreadable")
        return self


def setup(kill=None, ref=SIM_REF, policy=LAB_TEST_POLICY, **tr_kw):
    b = FakeBroker()
    tr = SimulatedPaperTransport(b, **tr_kw)
    a = AlpacaPaperOrderAdapter(tr, guard=simulated_only_guard(tr))
    kill = kill or Switch()
    lab = Lab(L.Ledger(), a, Clock(T0), LabConfig(), policy=policy, entry_controls=C.EntryControls(tr, ref, kill))
    lab.mark("SYN", 100.0)
    return lab, a, tr, b, kill


def posts(tr):
    return [r for r in tr.requests if r["method"] in ("POST", "DELETE")]


# ---------------------------------------------------------------- kill switch

def test_kill_switch_on_blocks_entry_and_nothing_is_sent():
    lab, a, tr, b, _ = setup(kill=Switch(on=True))
    r = lab.request_entry("SYN", 10, 100.0, 0.5)
    assert r["submitted"] is False and any("KILL SWITCH ON" in x for x in r["reasons"])
    assert lab.state()["orders"][r["order_id"]].state == L.BLOCKED and posts(tr) == [] and b.submit_calls == {}


def test_kill_switch_turned_on_after_validation_blocks_at_send_time():
    kill = Switch()
    lab, a, tr, b, _ = setup(kill=kill)
    real = lab.entry_check

    def check_then_flip(*args, **kw):
        out = real(*args, **kw)
        kill.on = True                       # the owner turns the switch on between validation and sending
        return out
    lab.entry_check = check_then_flip
    r = lab.request_entry("SYN", 10, 100.0, 0.5)
    ev = [e for e in lab.ledger.events() if e["order_id"] == r["order_id"]]
    assert r["submitted"] is False and lab.state()["orders"][r["order_id"]].state == L.BLOCKED
    assert [e["kind"] for e in ev][-2:] == ["validated", "blocked"] and "send-time" in ev[-1]["payload"]["stage"]
    assert posts(tr) == [] and "submit_requested" not in [e["kind"] for e in ev]


def test_unreadable_kill_switch_or_failing_controls_fail_closed():
    lab, *_ , tr, b, _ = setup(kill=Switch(broken=True))
    r = lab.request_entry("SYN", 10, 100.0, 0.5)
    assert r["submitted"] is False and any("KILL SWITCH STATE UNKNOWN" in x for x in r["reasons"])
    lab2 = Lab(L.Ledger(), lab.broker, Clock(T0), LabConfig(), policy=LAB_TEST_POLICY,
               entry_controls=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    lab2.mark("SYN", 100.0)
    r2 = lab2.request_entry("SYN", 10, 100.0, 0.5)
    assert r2["submitted"] is False and any("SESSION CONTROLS UNAVAILABLE" in x for x in r2["reasons"])
    assert b.submit_calls == {}


def test_kill_switch_never_blocks_cancel_exit_protection_or_reconciliation():
    kill = Switch()
    lab, a, tr, b, _ = setup(kill=kill)
    rest = lab.request_entry("SYN", 10, 99.0, 0.5)          # resting limit (synthetic)
    fill = lab.request_entry("SYN", 1, 100.0, 0.5)
    b.fill(fill["order_id"], "F1", 1, 100.0)
    lab.poll()
    kill.on = True
    assert lab.cancel(rest["order_id"], "kill switch on")["requested"] is True
    b.confirm_cancel(rest["order_id"], "c-rest")       # (a stop sell next to an open buy would be wash-trade rejected)
    lab.poll()
    assert lab.protect(fill["order_id"])["submitted"] is True          # risk-reducing protective stop still allowed
    stop_cid = f"{fill['order_id']}:stop1"
    assert lab.cancel(stop_cid, "free shares for the exit")["requested"] is True
    b.confirm_cancel(stop_cid, "c-stop")
    lab.poll()
    ex = lab.exit_position("SYN", 1, 100.0, "flatten")
    assert ex["submitted"] is True
    assert lab.reconcile()["ok"] is True
    blocked = lab.request_entry("SYN", 1, 100.0, 0.5)
    assert blocked["submitted"] is False and any("KILL SWITCH ON" in x for x in blocked["reasons"])


# ---------------------------------------------------------------- paper-only account checks

@pytest.mark.parametrize("kw, ref, expect", [
    ({"host": "https://api.alpaca.markets"}, SIM_REF, "NOT PAPER"),
    ({}, "0123456789ab", "WRONG ACCOUNT"),
    ({}, None, "INTENDED ACCOUNT NOT CONFIRMED"),
    ({"account_status": "ACCOUNT_UPDATED"}, SIM_REF, "ACCOUNT NOT ACTIVE"),
    ({"trading_blocked": True}, SIM_REF, "ACCOUNT BLOCKED"),
])
def test_account_checks_block_entries(kw, ref, expect):
    lab, a, tr, b, _ = setup(ref=ref, **kw)
    r = lab.request_entry("SYN", 10, 100.0, 0.5)
    assert r["submitted"] is False and any(expect in x for x in r["reasons"]), r["reasons"]
    assert posts(tr) == []


def test_unreachable_account_blocks_entries():
    lab, a, tr, b, _ = setup()
    b.available = False
    r = lab.request_entry("SYN", 10, 100.0, 0.5)
    assert r["submitted"] is False and any("ACCOUNT UNVERIFIABLE" in x for x in r["reasons"])


def test_intended_account_file_rules(tmp_path):
    p = tmp_path / "intended_paper_account.json"
    assert intended_account.load(p)[0] is None and "does not exist" in intended_account.load(p)[1]
    p.write_text("{not json", encoding="utf-8")
    assert intended_account.load(p)[0] is None
    p.write_text(json.dumps({"schema": 1, "environment": "live", "account_ref": "abc", "confirmed_by": ""}), encoding="utf-8")
    ref, why = intended_account.load(p)
    assert ref is None and "paper" in why and "12 lowercase hex" in why and "confirmed_by" in why
    p.write_text(json.dumps({"schema": 1, "environment": "paper", "account_ref": SIM_REF, "confirmed_by": "owner",
                             "confirmed_utc": "2030-06-01T00:00:00Z"}), encoding="utf-8")
    assert intended_account.load(p)[0] == SIM_REF


def test_project_has_no_intended_account_file_written_for_the_owner():
    assert not intended_account.PATH.exists() or intended_account.load()[0] is not None   # never a half-written file


# ---------------------------------------------------------------- session preflight

def _pf(tr, **kw):
    args = dict(intended=(SIM_REF, "test"), kill_reader=Switch(), acceptance=lambda: (True, "test"),
                policy=LAB_TEST_POLICY, guard=simulated_only_guard(tr))
    args.update(kw)
    return C.session_preflight(tr, **args)


def test_preflight_passes_only_when_every_check_passes():
    tr = SimulatedPaperTransport(FakeBroker())
    pf = _pf(tr)
    assert pf["ok"] is True and all(i["ok"] for i in pf["items"]) and len(pf["items"]) == 9


def test_preflight_defaults_refuse_today():
    """With the real defaults (real guard, the all-unset approved policy, no owner account file) it must refuse."""
    tr = SimulatedPaperTransport(FakeBroker())
    pf = C.session_preflight(tr, intended=(None, "NOT CONFIRMED"), kill_reader=Switch(), acceptance=lambda: (False, "1 of 5"))
    failed = {i["check"] for i in pf["items"] if not i["ok"]}
    assert pf["ok"] is False
    assert {"intended account confirmed by the owner", "Milestone 1 dry run accepted (five consecutive PASS sessions)",
            "execution policy approved for entries", "write permission for this process"} <= failed


@pytest.mark.parametrize("mutate, check", [
    (lambda b, tr: b.manual_trade("SYN", "buy", 3, 100.0), "account flat: no positions and no open orders"),
    (lambda b, tr: b.manual_order("SYN", "buy", 3), "account flat: no positions and no open orders"),
    (lambda b, tr: setattr(tr, "market_open", False), "market open (regular session)"),
    (lambda b, tr: setattr(tr, "host", "https://api.alpaca.markets"), "paper host only"),
])
def test_preflight_individual_failures(mutate, check):
    b = FakeBroker()
    tr = SimulatedPaperTransport(b)
    mutate(b, tr)
    pf = _pf(tr)
    assert pf["ok"] is False and check in {i["check"] for i in pf["items"] if not i["ok"]}


def test_preflight_reads_only():
    tr = SimulatedPaperTransport(FakeBroker())
    _pf(tr)
    assert {r["method"] for r in tr.requests} == {"GET"}


# ---------------------------------------------------------------- the planned mechanics sequence (simulated)

def test_planned_session_sequence_end_to_end_reconciles_flat():
    """Steps 1-4 of docs/PAPER_MECHANICS_SESSION_PLAN.md against the simulated API: resting limit -> cancel request ->
    confirmation; 1-share marketable buy -> fill -> exit -> flat. Broker and ledger agree on orders, position and cash."""
    lab, a, tr, b, _ = setup()
    rest = lab.request_entry("SYN", 1, 90.0, 0.5)                       # step 1: non-marketable resting limit
    assert lab.state()["orders"][rest["order_id"]].state == L.ACCEPTED   # an acknowledgement, not a fill
    assert a.lookup(rest["order_id"])["status"] == "accepted"            # step 2: visible by client order id
    assert lab.cancel(rest["order_id"], "plan step 3")["requested"] is True
    assert lab.state()["orders"][rest["order_id"]].state == L.CANCEL_PENDING   # a request is not a confirmation
    b.confirm_cancel(rest["order_id"], "c1")
    lab.poll()
    assert lab.state()["orders"][rest["order_id"]].state == L.CANCELLED
    buy = lab.request_entry("SYN", 1, 100.0, 0.5)                        # step 4: 1-share marketable limit
    b.fill(buy["order_id"], "E1", 1, 100.0)
    lab.poll()
    lab.poll()                                                           # a repeated poll stores nothing twice
    assert lab.state()["orders"][buy["order_id"]].state == L.FILLED
    ex = lab.exit_position("SYN", 1, 100.0, "plan step 5")
    b.fill(ex["order_id"], "X1", 1, 100.0)
    lab.poll()
    rec = lab.reconcile()
    st = lab.state()
    assert rec["ok"] and rec["discrepancies"] == [] and rec["positions_match"] and abs(rec["broker_cash"] - rec["ledger_cash"]) <= 0.01
    assert (st["positions"].get("SYN") or {}).get("qty", 0) == 0
    assert all(o.state in L.TERMINAL for o in st["orders"].values())
    assert all(v == 1 for v in b.submit_calls.values()) and len(b.submit_calls) == 3


def test_uncertain_submission_is_resolved_by_lookup_never_resubmitted():
    lab, a, tr, b, _ = setup()
    b.script_submit("lost_after_record")                                 # the broker records it; the reply is lost
    r = lab.request_entry("SYN", 1, 100.0, 0.5)
    assert r["submitted"] == "unknown" and lab.state()["orders"][r["order_id"]].state == L.UNKNOWN
    assert lab.retry_submit(r["order_id"])["submitted"] is False
    blocked = lab.request_entry("SYN", 1, 100.0, 0.5)
    assert blocked["submitted"] is False and any("unknown outcome" in x for x in blocked["reasons"])
    lab.reconcile()
    assert lab.state()["orders"][r["order_id"]].state == L.ACCEPTED and b.submit_calls[r["order_id"]] == 1


def test_lost_before_record_stays_unknown_until_owner_review():
    lab, a, tr, b, _ = setup()
    b.script_submit("lost_before_record")                                # the broker never recorded it
    r = lab.request_entry("SYN", 1, 100.0, 0.5)
    lab.reconcile()
    assert lab.state()["orders"][r["order_id"]].state == L.UNKNOWN       # absence is not proof: still UNKNOWN
    assert lab.request_entry("SYN", 1, 100.0, 0.5)["submitted"] is False


def test_manual_position_is_a_discrepancy_not_absorbed():
    lab, a, tr, b, _ = setup()
    b.manual_trade("SYN", "buy", 2, 100.0)
    rec = lab.reconcile()
    assert {d["kind"] for d in rec["discrepancies"]} >= {"position"}
    assert lab.request_entry("SYN", 1, 100.0, 0.5)["submitted"] is False


def test_exit_needs_policy_and_a_ledger_position():
    lab, a, tr, b, _ = setup(policy=APPROVED)
    r = lab.exit_position("SYN", 1, 100.0)
    assert r["submitted"] is False and any("POLICY UNSET" in x for x in r["reasons"])
    lab2, a2, tr2, b2, _ = setup()
    r2 = lab2.exit_position("SYN", 1, 100.0)
    assert r2["submitted"] is False and any("exceeds the unreserved ledger position" in x for x in r2["reasons"])
    assert b.submit_calls == {} and b2.submit_calls == {}


# ---------------------------------------------------------------- fresh-process restart recovery via the adapter

@pytest.mark.parametrize("name", ["after_send_before_ack", "after_submit_record_before_send", "during_partial_fills",
                                  "during_cancel", "after_intent_before_send"])
def test_fresh_process_drills_through_the_paper_adapter(name, tmp_path):
    res = drills.run_drill(name, tmp_path)
    bad = [c for c in res["checks"] if not c["passed"]]
    assert not bad, (bad, res["steps"])
    assert res["port"] == drills.PORT


# ---------------------------------------------------------------- isolation

def test_new_modules_have_no_network_code_and_the_real_guard_is_untouched():
    root = Path(__file__).resolve().parents[1]
    for f in ("trading/paper_adapter/simulated.py", "trading/paper_adapter/controls.py", "trading/paper_adapter/drills.py",
              "trading/execution_lab/intended_account.py"):
        src = (root / f).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import http", "import socket", "from trading.alpaca_client", "import trading.alpaca_client", "ORDER_SUBMISSION_ENABLED"):
            assert bad not in src, (f, bad)
    from trading.safety import require_order_submission_allowed
    with pytest.raises(Exception):
        require_order_submission_allowed()            # still refuses in this process


def test_missing_readers_fail_closed():
    assert any("NOT CONFIGURED" in r for r in C.kill_switch_reasons(None))
    tr = SimulatedPaperTransport(FakeBroker())
    pf = C.session_preflight(tr, intended=(SIM_REF, "t"), policy=LAB_TEST_POLICY, guard=simulated_only_guard(tr))
    failed = {i["check"] for i in pf["items"] if not i["ok"]}
    assert {"kill switch off", "Milestone 1 dry run accepted (five consecutive PASS sessions)"} <= failed
