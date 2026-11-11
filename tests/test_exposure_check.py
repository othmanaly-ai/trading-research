"""SYNTHETIC: the dry run's "no exposure" check must rest on broker evidence (read-only GETs), never on a local
assertion or a heartbeat. Fake clients and isolated stores only; no network, no keys, no orders (none exist)."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from trading.alpaca_client import AlpacaAccessError, ReadOnlyAlpacaClient
from trading.operations import broker_checks as bc
from trading.operations import report, runner
from trading.operations import schedule as sc
from trading.operations.store import OpsStore
from tests.test_operations_runner import EARLY, FakeBroker, FakeClock, env  # noqa: F401  (env is a fixture)

T = datetime(2026, 11, 27, 17, 55, tzinfo=timezone.utc)


class Fake:
    """Read-only fake with scripted answers (SYNTHETIC). It has no write methods at all."""
    def __init__(self, positions=(), orders=(), host="https://paper-api.alpaca.markets", ref="0123456789ab", fail=None):
        as_list = lambda x: list(x) if isinstance(x, tuple) else x          # defaults -> []; malformed values kept as given
        self.positions, self.orders, self.host, self.ref, self.fail = as_list(positions), as_list(orders), host, ref, fail

    def _maybe_fail(self, what):
        if self.fail == what:
            raise AlpacaAccessError(503, "SYNTHETIC outage", "https://paper-api.alpaca.markets/v2/x")

    def get_account_identity(self):
        self._maybe_fail("identity")
        return {"environment_host": self.host, "account_ref": self.ref}

    def get_positions(self):
        self._maybe_fail("positions")
        return self.positions

    def get_open_orders(self, limit=500):
        self._maybe_fail("orders")
        return self.orders


def now_fixed():
    return T


def check(client, expected=None, now_fn=now_fixed):
    return bc.exposure_check(client, now_fn, expected)


# ---------------------------------------------------------------- the check itself

def test_empty_account_is_verified_none_with_time_and_identity():
    ok, d = check(Fake())
    assert ok and d["status"] == "VERIFIED_NONE" and d["verified"] is True and bc.verified_none(d)
    assert d["observed_from_utc"] and d["observed_to_utc"] and d["environment_host"].startswith("https://paper-api")
    assert d["account_ref"] == "0123456789ab"


def test_open_position_is_exposure_found_and_nothing_is_closed():
    f = Fake(positions=[{"symbol": "SPY", "qty": "3", "side": "long"}])
    ok, d = check(f)
    assert not ok and d["status"] == "EXPOSURE_FOUND" and d["positions"][0]["symbol"] == "SPY"
    assert "Nothing was closed or cancelled" in d["reason"]
    assert not [m for m in dir(f) if m.startswith(("submit", "cancel", "close", "replace"))]


@pytest.mark.parametrize("status", ["new", "accepted", "partially_filled", "pending_new", "pending_cancel"])
def test_outstanding_or_partially_filled_order_is_exposure(status):
    ok, d = check(Fake(orders=[{"symbol": "QQQ", "side": "buy", "qty": "5", "filled_qty": "2", "status": status, "type": "limit"}]))
    assert not ok and d["status"] == "EXPOSURE_FOUND" and len(d["open_orders"]) == 1


@pytest.mark.parametrize("what", ["identity", "positions", "orders"])
def test_broker_unavailable_is_unverifiable(what):
    ok, d = check(Fake(fail=what))
    assert not ok and d["status"] == "UNVERIFIABLE" and d["verified"] is False and "unavailable" in d["reason"]


@pytest.mark.parametrize("fake, why", [
    (Fake(positions={"symbol": "SPY"}), "positions response malformed"),
    (Fake(positions=[{"symbol": "SPY"}]), "positions response malformed"),                 # no qty
    (Fake(positions=[{"symbol": "SPY", "qty": "abc"}]), "quantity unreadable"),
    (Fake(orders=None), "open-orders response malformed"),
    (Fake(orders=[{"symbol": "SPY"}]), "open-orders response malformed"),                 # no status
    (Fake(orders=[{"symbol": "SPY", "status": "new"}] * 500), "incomplete"),
])
def test_incomplete_or_malformed_responses_are_unverifiable(fake, why):
    ok, d = check(fake)
    assert not ok and d["status"] == "UNVERIFIABLE" and why in d["reason"]


@pytest.mark.parametrize("fake, expected, why", [
    (Fake(host="https://api.alpaca.markets"), None, "wrong environment"),
    (Fake(ref=None), None, "account unverifiable"),
    (Fake(ref="not-a-ref"), None, "account unverifiable"),
    (Fake(ref="fedcba987654"), "0123456789ab", "account differs"),
])
def test_wrong_account_or_environment_is_unverifiable(fake, expected, why):
    ok, d = check(fake, expected)
    assert not ok and d["status"] == "UNVERIFIABLE" and why in d["reason"]


def test_slow_evidence_is_stale():
    times = iter([T, T + timedelta(seconds=45)])
    ok, d = check(Fake(), now_fn=lambda: next(times))
    assert not ok and "stale" in d["reason"]


# ---------------------------------------------------------------- the read-only client methods

class FakeResp:
    def __init__(self, body, code=200):
        self.status_code, self._b, self.text = code, body, json.dumps(body)

    def json(self):
        return self._b


class FakeHttp:
    def __init__(self, bodies):
        self.bodies, self.calls = list(bodies), []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        return FakeResp(self.bodies.pop(0))


def test_client_methods_are_paper_gets_and_never_return_identifiers():
    http = FakeHttp([{"id": "acct-uuid", "account_number": "PA0000", "status": "ACTIVE"},
                     [{"symbol": "SPY", "qty": "1", "side": "long", "cost_basis": "x", "asset_id": "y"}],
                     [{"id": "ord", "client_order_id": "c", "symbol": "SPY", "side": "buy", "qty": "1", "filled_qty": "0",
                       "status": "new", "type": "limit"}]])
    c = ReadOnlyAlpacaClient("k", "s", http=http)
    ident, pos, orders = c.get_account_identity(), c.get_positions(), c.get_open_orders()
    assert [x["url"] for x in http.calls] == ["https://paper-api.alpaca.markets/v2/account",
                                              "https://paper-api.alpaca.markets/v2/positions",
                                              "https://paper-api.alpaca.markets/v2/orders"]
    assert http.calls[2]["params"]["status"] == "open"
    assert "acct-uuid" not in json.dumps(ident) and "PA0000" not in json.dumps(ident) and len(ident["account_ref"]) == 12
    assert "asset_id" not in pos[0] and "id" not in orders[0] and "client_order_id" not in orders[0]


def test_client_rejects_non_list_bodies():
    c = ReadOnlyAlpacaClient("k", "s", http=FakeHttp([{"message": "not a list"}]))
    with pytest.raises(ValueError):
        c.get_positions()


# ---------------------------------------------------------------- the runner and the classification

def run_session(tmp_path, broker_factory, start_et="08:30:00"):
    plan = sc.plan_for(EARLY)
    start = datetime.fromisoformat(f"{EARLY}T{start_et}").replace(tzinfo=sc.ET).astimezone(timezone.utc)
    clk = FakeClock(start)
    store = OpsStore(tmp_path / "ops" / "operations.sqlite")
    r = runner.Runner(store, client_factory=lambda: broker_factory(clk, plan), now_fn=clk.now, sleep=clk.sleep,
                      mono=clk.mono, reports_dir=tmp_path / "reports", echo=lambda *a: None)
    r.run()
    return report.classify(store, EARLY, clk.now()), store


def test_empty_account_session_passes_with_closing_evidence(env):
    tmp, _ = env
    rep, store = run_session(tmp, lambda clk, plan: FakeBroker(clk, plan))
    assert rep["classification"] == "PASS", rep["reasons"]
    closing = [e for e in rep["exposure_evidence"] if e["stage"] == "closing"]
    assert closing and closing[-1]["status"] == "VERIFIED_NONE"


def test_position_found_fails_the_session_and_blocks_acceptance(env, monkeypatch):
    tmp, _ = env

    class Held(FakeBroker):
        positions = [{"symbol": "SPY", "qty": "2", "side": "long"}]
    rep, store = run_session(tmp, lambda clk, plan: Held(clk, plan))
    assert rep["classification"] == "FAIL" and any(r.startswith("F9") for r in rep["reasons"]), rep["reasons"]
    assert report.acceptance(store, datetime(2026, 11, 28, tzinfo=timezone.utc))["current_streak"] == 0


def test_partially_filled_order_found_at_closing_fails(env):
    tmp, _ = env

    class LateOrder(FakeBroker):
        def get_open_orders(self, limit=500):
            if self.clock.now() >= self.plan.closing_utc:
                return [{"symbol": "IWM", "side": "buy", "qty": "4", "filled_qty": "1", "status": "partially_filled", "type": "limit"}]
            return []
    rep, _ = run_session(tmp, lambda clk, plan: LateOrder(clk, plan))
    assert rep["classification"] == "FAIL" and any("F9" in r for r in rep["reasons"])


def test_broker_unavailable_at_closing_is_never_a_pass(env):
    tmp, _ = env

    class DownAtClose(FakeBroker):
        def get_positions(self):
            if self.clock.now() >= self.plan.closing_utc:
                raise AlpacaAccessError(503, "SYNTHETIC outage", "https://paper-api.alpaca.markets/v2/positions")
            return []
    rep, _ = run_session(tmp, lambda clk, plan: DownAtClose(clk, plan))
    assert rep["classification"] == "INCOMPLETE" and any(r.startswith("I6") for r in rep["reasons"]), rep["reasons"]


def test_missing_credentials_at_closing_is_never_a_pass(env):
    tmp, _ = env

    def factory(clk, plan):
        if clk.now() >= plan.closing_utc:
            from trading.alpaca_client import MissingCredentials
            raise MissingCredentials("SYNTHETIC: keys not available")
        return FakeBroker(clk, plan)
    rep, _ = run_session(tmp, factory)
    assert rep["classification"] == "INCOMPLETE" and any("broker client unavailable" in r for r in rep["reasons"])


def test_account_switch_during_session_is_unverifiable(env):
    tmp, _ = env

    class Switched(FakeBroker):
        def get_account_identity(self):
            ref = "fedcba987654" if self.clock.now() >= self.plan.closing_utc else "0123456789ab"
            return {"environment_host": "https://paper-api.alpaca.markets", "account_ref": ref}
    rep, _ = run_session(tmp, lambda clk, plan: Switched(clk, plan))
    assert rep["classification"] == "INCOMPLETE" and any("account" in r and r.startswith("I6") for r in rep["reasons"])


def test_local_assertion_and_fresh_heartbeat_cannot_substitute_for_broker_evidence(env):
    """The old behaviour (a closing record saying ok without asking the broker) must not pass, however healthy the
    process looked."""
    tmp, _ = env
    rep, store = run_session(tmp, lambda clk, plan: FakeBroker(clk, plan))
    assert rep["classification"] == "PASS"
    run_id = store.runs_for(str(EARLY))[0]["run_id"]
    plan = sc.plan_for(EARLY)
    store.add_check(run_id, str(EARLY), (plan.closing_utc + timedelta(seconds=30)).isoformat(), "closing", "exposure_none",
                    True, False, {"note": "DRY_RUN holds no positions and contains no order code"})
    store.heartbeat(run_id, (plan.closing_utc + timedelta(seconds=31)).isoformat())
    rep = report.classify(store, EARLY, plan.report_utc + timedelta(hours=1))
    assert rep["classification"] == "INCOMPLETE" and any("local assertion is not evidence" in r for r in rep["reasons"])


def test_sessions_before_the_correction_keep_their_original_rules(tmp_path):
    """Records from before 2026-11-11 are classified exactly as before (never relabelled)."""
    assert report.EXPOSURE_EVIDENCE_FROM.isoformat() == "2026-11-11"
    store = OpsStore(tmp_path / "ops.sqlite")
    d = sc.plan_for(datetime(2026, 11, 10).date())
    store.begin_run("old", "session", "2026-11-10", "DRY_RUN", 1, d.preopen_utc.isoformat(), "ON_TIME", "fp", "v", {})
    store.add_check("old", "2026-11-10", d.closing_utc.isoformat(), "closing", "exposure_none", True, False,
                    {"note": "DRY_RUN holds no positions and contains no order code"})
    rep = report.classify(store, d.date, d.report_utc + timedelta(hours=1))
    assert not any(r.startswith(("I6", "F9")) for r in rep["reasons"])
    assert isinstance(rep["exposure_evidence"], str) and "not required" in rep["exposure_evidence"]
