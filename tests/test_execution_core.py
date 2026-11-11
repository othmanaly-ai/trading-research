"""Execution core rules beyond the scenarios (LOCAL EXECUTION SIMULATION; fake broker; synthetic data; no network)."""

import socket
from dataclasses import replace

import pytest

from trading.execution_lab import ledger as L
from trading.execution_lab import scenarios as S
from trading.execution_lab.fake_broker import FakeBroker
from trading.execution_lab.intents import IntentSource, source_refusal
from trading.execution_lab.lab import Clock, Lab, LabConfig
from trading.execution_lab.policy import APPROVED, LAB_TEST_POLICY, REQUIRED_FOR


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network access attempted")
    monkeypatch.setattr(socket.socket, "connect", refuse)


def lab(policy=LAB_TEST_POLICY):
    x = Lab(L.Ledger(), FakeBroker(), Clock(S.T0), LabConfig(), policy=policy)
    x.mark("SYN", 100.0)
    return x


def test_nothing_is_approved_and_every_entry_field_blocks_when_unset():
    assert all(getattr(APPROVED, f) is None for f in REQUIRED_FOR["entry"])
    for f in REQUIRED_FOR["entry"]:
        x = lab(replace(LAB_TEST_POLICY, **{f: None}))
        r = x.request_entry("SYN", 10, 100.0, 0.5)
        assert not r["submitted"] and any(f in s and s.startswith("POLICY UNSET") for s in r["reasons"]), f
        assert not x.broker.submit_calls


def test_invalid_policy_value_blocks():
    r = lab(replace(LAB_TEST_POLICY, time_in_force="gtc")).request_entry("SYN", 10, 100.0, 0.5)
    assert not r["submitted"] and any(s.startswith("POLICY INVALID") for s in r["reasons"])


def test_unset_unprotected_limit_blocks_entries_once_shares_are_unprotected():
    x = lab(replace(LAB_TEST_POLICY, max_unprotected_seconds=None))
    a = x.request_entry("SYN", 10, 100.0, 0.5)["order_id"]   # blocked: field required for entry
    assert x.state()["orders"][a].state == L.BLOCKED


def test_strategy_intents_need_the_approved_registry(tmp_path):
    assert "NO APPROVED ACTIVE STRATEGY" in source_refusal(IntentSource("strategy", "s", "v1"))
    reg = tmp_path / "approved.json"
    reg.write_text('{"approved": [{"strategy_id": "s", "version": "v1"}]}')
    assert source_refusal(IntentSource("strategy", "s", "v1"), reg) is None
    assert "not in the approved registry" in source_refusal(IntentSource("strategy", "s", "v2"), reg)


def test_emergency_stop_never_cancels_protective_stops():
    x = lab()
    a = x.request_entry("SYN", 20, 100.0, 0.5)["order_id"]
    x.broker.fill(a, "E1", 20, 100.0); x.poll()
    assert x.protect(a)["submitted"] is True
    rep = x.emergency_stop("drill")
    stops = [o for o in x.state()["orders"].values() if o.purpose == "protect"]
    assert stops and all(o.state == L.ACCEPTED for o in stops) and not any(":stop" in r["order_id"] for r in rep["cancellations"])
    assert rep["overall"] == "INCOMPLETE" and rep["unprotected_shares"] == 0


def test_emergency_exposure_action_unset_is_reported_not_chosen():
    x = lab(replace(LAB_TEST_POLICY, emergency_exposure_action=None))
    a = x.request_entry("SYN", 20, 100.0, 0.5)["order_id"]
    x.broker.fill(a, "E2", 20, 100.0); x.poll()
    rep = x.emergency_stop("drill")
    step = next(s for s in rep["steps"] if s["step"] == "Reduce or close exposure")
    assert step["status"].startswith("UNSET") and rep["overall"] == "INCOMPLETE"


def test_escalation_timing_follows_policy_and_unset_is_an_owner_decision():
    for pol, expect in ((LAB_TEST_POLICY, "ESCALATE TO OWNER"), (replace(LAB_TEST_POLICY, unknown_escalation_seconds=None), "UNSET")):
        x = lab(pol)
        x.broker.script_submit("lost_before_record")
        x.request_entry("SYN", 10, 100.0, 0.5)
        x.clock.advance(400)
        assert any(expect in a["action"] for a in x.attention()), x.attention()


def test_protective_order_cannot_be_placed_while_the_entry_can_still_fill():
    x = lab()
    a = x.request_entry("SYN", 40, 100.0, 0.5)["order_id"]
    x.broker.fill(a, "W1", 10, 100.0); x.poll()
    assert x.protect(a)["submitted"] is False                         # local rule
    r = x.broker.submit(f"{a}:manual-stop", "SYN", "sell", 10, {"type": "stop", "stop_price": 99.5})
    assert r["status"] == "rejected" and "wash trade" in r["reason"]   # simulated broker rule (documented behaviour)


# ---------------------------------------------------------------- regressions for defects confirmed 2026-11-11

def test_live_order_missing_at_the_broker_is_a_discrepancy_not_completion():
    x = lab()
    a = x.request_entry("SYN", 10, 100.0, 0.5)["order_id"]
    x.broker.forget(a)                                   # SIMULATION: the broker has no record of it
    rec = x.reconcile()
    assert not rec["ok"] and [d["kind"] for d in rec["discrepancies"]] == ["order_missing_at_broker"]
    assert x.state()["orders"][a].state == L.ACCEPTED    # not assumed cancelled
    assert not x.entry_check("SYN", 1, 100.0, 0.5, 5)["allowed"]


def test_a_cancel_requested_again_by_a_fresh_broker_client_is_recorded_not_dropped():
    x = lab()
    a = x.request_entry("SYN", 10, 100.0, 0.5)["order_id"]
    x.cancel(a, "first")
    x.broker.cancel_calls = {}                           # a fresh adapter starts with empty in-memory counters
    x.cancel(a, "second, after a restart")
    reqs = [e for e in x.ledger.events() if e["kind"] == "cancel_requested" and e["order_id"] == a]
    assert len(reqs) == 2 and not x.ledger.duplicates()


def test_orphaned_intent_from_a_crash_during_the_checks_expires_on_reconciliation():
    x = lab()
    x._evt("intent_created", {"symbol": "SYN", "side": "buy", "qty": 10, "ref_price": 100.0, "stop_distance": 0.5,
                              "purpose": "entry", "client_order_id": "orphan"}, "orphan", "intent:orphan")
    y = Lab(x.ledger, x.broker, x.clock, LabConfig(), restart=True, policy=LAB_TEST_POLICY)
    assert y.state()["orders"]["orphan"].state == L.CREATED
    y.reconcile()
    o = y.state()["orders"]["orphan"]
    assert o.state == L.BLOCKED and "never validated" in o.reasons[0] and not y.broker.submit_calls


def test_ledger_cash_equals_broker_cash_after_a_round_trip_with_fees():
    x = lab()
    a = x.request_entry("SYN", 20, 100.0, 0.5)["order_id"]
    x.broker.fill(a, "R1", 20, 100.05); x.poll()
    stop = x.protect(a)["order_id"]
    x.broker.fill(stop, "R2", 20, 99.50); x.poll()
    st = x.state()
    assert not st["positions"] and st["fees"] > 0                        # sell fee charged on the exit
    rec = x.reconcile()
    assert rec["ok"] and abs(rec["broker_cash"] - st["cash"]) < 0.01, rec


def test_never_sent_only_with_durable_proof_and_uncertain_outcomes_stay_unresolved():
    # (1) proof: intent with no submission record and no broker event -> closed as never sent
    x = lab()
    x._evt("intent_created", {"symbol": "SYN", "side": "buy", "qty": 5, "ref_price": 100.0, "stop_distance": 0.5,
                              "purpose": "entry", "client_order_id": "p1"}, "p1", "intent:p1")
    x._evt("validated", {"check": {}}, "p1", "validated:p1")
    # (2) contradiction: shown as not sent, but a submission record exists (SYNTHETIC inconsistent ledger)
    x._evt("intent_created", {"symbol": "SYN", "side": "buy", "qty": 5, "ref_price": 100.0, "stop_distance": 0.5,
                              "purpose": "entry", "client_order_id": "p2"}, "p2", "intent:p2")
    x._evt("submit_requested", {"symbol": "SYN", "side": "buy", "qty": 5, "spec": None}, "p2", "submit:p2")
    # (3) uncertain: submission recorded, broker has no record -> UNKNOWN, never "never sent"
    x.broker.script_submit("lost_before_record")
    p3 = x.request_entry("SYN", 5, 100.0, 0.5)["order_id"]
    y = Lab(x.ledger, x.broker, x.clock, LabConfig(), restart=True, policy=LAB_TEST_POLICY)
    rec = y.reconcile()
    st = y.state()["orders"]
    assert st["p1"].state == L.BLOCKED and "no submission record" in [e for e in y.ledger.events()
                                                                      if e["kind"] == "intent_expired_unsent"][0]["payload"]["proof"]
    assert st["p2"].state != L.BLOCKED and any(d["kind"] == "unsent_intent_with_submission_evidence" and d["order_id"] == "p2"
                                               for d in rec["discrepancies"])
    assert st[p3].state == L.UNKNOWN and not rec["ok"]
    assert not y.entry_check("SYN", 1, 100.0, 0.5, 5)["allowed"]           # uncertainty blocks entries
