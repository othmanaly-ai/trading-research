"""SYNTHETIC: the dry-run runner and the session classification, on a fake clock with a fake broker
and fake monitoring data. No network, no real keys, no market data, no orders (none exist)."""

import json
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from trading.alpaca_client import AlpacaAccessError
from trading.operations import data_health, gate, report, runner
from trading.operations import schedule as sc
from trading.operations.store import OpsStore

ROOT = Path(__file__).resolve().parents[1]
EARLY = date(2026, 11, 27)          # early close 13:00 ET: 205 decision minutes (keeps the simulation short)


class FakeClock:
    def __init__(self, start: datetime, jumps=None, interrupt_at=None):
        self.t, self.m = start, 0.0
        self.jumps = dict(jumps or {})                 # at/after this time: jump forward by timedelta (sleep)
        self.interrupt_at = interrupt_at

    def now(self):
        return self.t

    def mono(self):
        return self.m

    def sleep(self, s):
        self.t += timedelta(seconds=s)
        self.m += s
        for at, by in list(self.jumps.items()):
            if self.t >= at:
                self.t += by
                self.m += by.total_seconds()
                del self.jumps[at]
        if self.interrupt_at and self.t >= self.interrupt_at:
            self.interrupt_at = None
            raise KeyboardInterrupt


class FakeBroker:
    def __init__(self, clock, plan, fail_clock_after=None):
        self.clock, self.plan, self.fail_after = clock, plan, fail_clock_after

    def get_clock(self):
        now = self.clock.now()
        self.clock.broker_calls = getattr(self.clock, "broker_calls", 0) + 1
        if self.fail_after and now >= self.fail_after:
            raise AlpacaAccessError(503, "SYNTHETIC outage", "https://paper-api.alpaca.markets/v2/clock")
        is_open = self.plan.open_utc <= now < self.plan.close_utc
        return {"timestamp": now.isoformat(), "is_open": is_open, "next_open": self.plan.open_utc.isoformat(),
                "next_close": self.plan.close_utc.isoformat()}

    def get_account(self):
        return {"status": "ACTIVE", "trading_blocked": False, "account_blocked": False, "cash": "SYNTHETIC"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADING_OPS_DIR", str(tmp_path / "ops"))
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "false")
    state = {"alive": True, "git": {"commit": "SYNTHETIC0000", "operations_code_committed": True, "uncommitted_paths": []}}
    monkeypatch.setattr(runner, "committed_code_state", lambda: state["git"])
    monkeypatch.setattr(data_health, "read", lambda now, db: gate.DataHealth(
        state["alive"], "iex", {"SPY": {"age_s": 70.0, "fresh": True}}, (data_health.SUITABILITY_REASON,)))
    return tmp_path, state


def simulate(tmp_path, start_et: str, d=EARLY, jumps=None, interrupt_at=None, fail_clock_after=None, store=None):
    plan = sc.plan_for(d)
    start = datetime.fromisoformat(f"{d}T{start_et}").replace(tzinfo=sc.ET).astimezone(timezone.utc)
    clk = FakeClock(start, jumps, interrupt_at)
    store = store or OpsStore(tmp_path / "ops" / "operations.sqlite")
    r = runner.Runner(store, client_factory=lambda: FakeBroker(clk, plan, fail_clock_after), now_fn=clk.now,
                      sleep=clk.sleep, mono=clk.mono, reports_dir=tmp_path / "reports", echo=lambda *a: None)
    code = r.run()
    return code, store, plan, clk


def et(d, hhmm):
    return datetime.fromisoformat(f"{d}T{hhmm}").replace(tzinfo=sc.ET).astimezone(timezone.utc)


def test_on_time_full_session_passes_and_never_allows_entry(env):
    tmp, _ = env
    code, store, plan, clk = simulate(tmp, "08:30:00")
    assert code == 0
    rep = report.classify(store, EARLY, clk.now())
    assert rep["classification"] == "PASS", rep["reasons"]
    dec = rep["decisions"]
    assert dec == {**dec, "expected": 205, "recorded": 205, "missing": 0, "allowed": 0, "denied": 205}
    assert dec["reason_tallies"]["environment DRY_RUN never permits entries"] == 205
    assert dec["reason_tallies"]["no approved strategy"] == 205
    assert len(rep["clock_checks"]) >= 7 and all(c["ok"] for c in rep["clock_checks"])
    assert store.latest_report(str(EARLY))["classification"] == "PASS"
    assert json.loads((tmp / "reports" / f"{EARLY}.json").read_text())["classification"] == "PASS"
    rows = store.decisions_for(str(EARLY))
    assert all(0 <= (datetime.fromisoformat(r["decided_utc"]) - datetime.fromisoformat(r["minute_utc"])).total_seconds() < 60
               for r in rows)


def test_report_records_the_committed_code_version(env):
    tmp, state = env
    code, store, plan, clk = simulate(tmp, "08:30:00")
    rep = report.classify(store, EARLY, clk.now())
    assert rep["code_version"] == {"commits": ["SYNTHETIC0000"], "operations_code_committed": True,
                                   "fingerprints": [runner.code_fingerprint()]}
    assert store.runs_for(str(EARLY))[0]["code_version"] == "SYNTHETIC000"


def test_uncommitted_operations_code_cannot_pass(env):
    tmp, state = env
    state["git"] = {"commit": "SYNTHETIC0000", "operations_code_committed": False,
                    "uncommitted_paths": ["trading/operations/gate.py"]}
    code, store, plan, clk = simulate(tmp, "08:30:00")
    rep = report.classify(store, EARLY, clk.now())
    assert rep["classification"] == "INCOMPLETE" and any(r.startswith("I5") for r in rep["reasons"])
    assert store.runs_for(str(EARLY))[0]["code_version"].endswith("+uncommitted-operations-code")


def test_committed_code_state_shape():
    s = runner.committed_code_state()
    assert set(s) == {"commit", "operations_code_committed", "uncommitted_paths"}


def test_late_start_is_incomplete_and_missed_minutes_are_not_replayed(env):
    tmp, _ = env
    code, store, plan, clk = simulate(tmp, "10:05:30")
    rep = report.classify(store, EARLY, clk.now())
    assert rep["classification"] == "INCOMPLETE"
    assert any(r.startswith("I2") for r in rep["reasons"]) and any(r.startswith("I3") for r in rep["reasons"])
    first = min(r["minute_utc"] for r in store.decisions_for(str(EARLY)))
    assert first == et(EARLY, "10:05:00").isoformat()            # nothing before the start
    assert rep["decisions"]["missing"] == 35


def test_machine_sleep_leaves_missing_minutes_and_heartbeat_gap(env):
    tmp, _ = env
    code, store, plan, clk = simulate(tmp, "08:30:00", jumps={et(EARLY, "11:00:10"): timedelta(minutes=10)})
    rep = report.classify(store, EARLY, clk.now())
    assert rep["classification"] == "INTERRUPTED"
    text = " ".join(rep["reasons"])
    assert "N1 9 of 205" in text and "N2" in text                  # 11:01-11:09 slept through
    minutes = {r["minute_utc"] for r in store.decisions_for(str(EARLY))}
    assert et(EARLY, "11:05:00").isoformat() not in minutes         # skipped minutes stay missing
    assert any(e["kind"] == "time_gap" for e in store.events_for(str(EARLY)))


def test_unsafe_configuration_refuses_and_is_a_fail(env, monkeypatch):
    tmp, _ = env
    monkeypatch.setenv("ORDER_SUBMISSION_ENABLED", "true")
    code, store, plan, clk = simulate(tmp, "08:30:00")
    assert code == 3 and store.decisions_for(str(EARLY)) == []
    rep = report.classify(store, EARLY, plan.report_utc + timedelta(minutes=1))
    assert rep["classification"] == "FAIL" and rep["reasons"][0].startswith("F3")


def test_operator_stop_is_interrupted(env):
    tmp, _ = env
    code, store, plan, clk = simulate(tmp, "08:30:00", interrupt_at=et(EARLY, "11:30:00"))
    assert code == 130
    rep = report.classify(store, EARLY, plan.report_utc + timedelta(minutes=1))
    assert rep["classification"] == "INTERRUPTED" and any(r.startswith("N3") for r in rep["reasons"])


def test_restart_same_day_never_duplicates_a_decision(env):
    tmp, _ = env
    code, store, plan, clk = simulate(tmp, "08:30:00", interrupt_at=et(EARLY, "11:00:20"))
    simulate(tmp, "11:00:40", store=store)                          # same minute 11:00: already recorded
    rows = store.decisions_for(str(EARLY))
    assert len(rows) == len({r["minute_utc"] for r in rows}) == 205
    rep = report.classify(store, EARLY, plan.report_utc + timedelta(minutes=1))
    assert rep["classification"] == "PASS", rep["reasons"]           # continuous evidence, two runs


def test_broker_outage_at_final_check_and_in_session(env):
    tmp, _ = env
    code, store, plan, clk = simulate(tmp, "08:30:00", fail_clock_after=et(EARLY, "09:20:00"))
    rep = report.classify(store, EARLY, clk.now())
    assert rep["classification"] == "INTERRUPTED"
    text = " ".join(rep["reasons"])
    assert "N4" in text and "broker_clock_skew" in text and "N5" in text
    reasons = json.loads(store.decisions_for(str(EARLY))[-1]["reasons_json"])
    assert "clock not verified against the broker" in reasons and "clock skew beyond tolerance" not in reasons
    assert clk.broker_calls <= 12                                   # outage: retried every 30 min, never in a tight loop


def test_worker_down_most_of_session_is_interrupted(env, monkeypatch):
    tmp, state = env
    state["alive"] = False
    code, store, plan, clk = simulate(tmp, "08:30:00")
    rep = report.classify(store, EARLY, clk.now())
    assert rep["classification"] == "INTERRUPTED" and any(r.startswith("N6") for r in rep["reasons"])


def test_holiday_does_nothing(env):
    tmp, _ = env
    code, store, plan, clk = simulate(tmp, "08:30:00", d=date(2026, 11, 26))
    assert code == 0 and store.decisions_for("2026-11-26") == []
    assert report.classify(store, date(2026, 11, 26), clk.now())["classification"] == "NO_SESSION"


def test_not_run_pending_and_injected_violations(tmp_path):
    store = OpsStore(tmp_path / "ops.sqlite")
    after = sc.plan_for(EARLY).report_utc + timedelta(minutes=1)
    assert report.classify(store, EARLY, after)["reasons"][0].startswith("I1 NOT RUN")
    assert report.classify(store, EARLY, after - timedelta(hours=2))["classification"] == "PENDING"
    plan = sc.plan_for(EARLY)
    store.begin_run("r1", "session", str(EARLY), "DRY_RUN", 1, (plan.preopen_utc).isoformat(), "ON_TIME", "fp", "v", {})
    m = plan.open_utc
    store.add_decision(str(EARLY), m.isoformat(), "r1", (m + timedelta(seconds=5)).isoformat(), "DECISION_WINDOW", True, [], {})
    m2 = m + timedelta(minutes=1)
    store.add_decision(str(EARLY), m2.isoformat(), "r1", (m2 + timedelta(seconds=75)).isoformat(), "DECISION_WINDOW", False, ["x"], {})
    rep = report.classify(store, EARLY, after)
    assert rep["classification"] == "FAIL"
    assert any(r.startswith("F1") for r in rep["reasons"]) and any(r.startswith("F2") for r in rep["reasons"])


def test_acceptance_needs_five_consecutive_passes_with_one_fingerprint(tmp_path, monkeypatch):
    store = OpsStore(tmp_path / "ops.sqlite")
    store.begin_run("r0", "session", "2026-11-10", "DRY_RUN", 1, "2026-11-10T13:00:00+00:00", "ON_TIME", "A", "v", {})
    seq = {"2026-11-10": "PASS", "2026-11-11": "INCOMPLETE", "2026-11-12": "PASS", "2026-11-13": "PASS",
           "2026-11-16": "PASS", "2026-11-17": "PASS", "2026-11-18": "PASS"}
    fps = {d: ["A"] for d in seq}
    monkeypatch.setattr(report, "classify", lambda s, d, now: {"classification": seq.get(str(d), "PENDING"),
                                                                "code_fingerprints": fps.get(str(d), []), "reasons": []})
    now = datetime(2026, 11, 18, 23, 0, tzinfo=timezone.utc)
    a = report.acceptance(store, now)
    assert a["accepted"] and a["accepted_on"] == "2026-11-18" and a["current_streak"] == 5
    fps["2026-11-16"] = ["B"]                                         # code changed mid-streak: count restarts
    b = report.acceptance(store, now)
    assert not b["accepted"] and b["current_streak"] == 2


def test_data_health_reads_monitor_store(tmp_path):
    db = tmp_path / "monitor.sqlite"
    con = sqlite3.connect(db)
    con.executescript("CREATE TABLE worker (id INTEGER, state TEXT, heartbeat_utc TEXT, config_json TEXT);"
                      "CREATE TABLE bars (symbol TEXT, feed TEXT, t_utc TEXT);")
    now = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)
    con.execute("INSERT INTO worker VALUES (1, 'polling', ?, ?)", ((now - timedelta(seconds=5)).isoformat(),
                                                                   json.dumps({"feed": "iex", "symbols": ["SPY", "QQQ"]})))
    con.execute("INSERT INTO bars VALUES ('SPY', 'iex', ?)", ((now - timedelta(minutes=2)).isoformat(),))
    con.execute("INSERT INTO bars VALUES ('QQQ', 'iex', ?)", ((now - timedelta(minutes=10)).isoformat(),))
    con.commit()
    con.close()
    h = data_health.read(now, db)
    assert h.worker_alive and h.feed == "iex" and h.symbols["SPY"]["fresh"] and not h.symbols["QQQ"]["fresh"]
    assert any("QQQ iex" in r for r in h.reasons) and h.reasons[-1] == data_health.SUITABILITY_REASON
    assert not data_health.read(now, tmp_path / "missing.sqlite").worker_alive


def test_snapshot_reports_state_from_records_only(env):
    from trading.operations import snapshot
    tmp, _ = env
    empty = snapshot.collect(datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc))
    assert empty["available"] is False and empty["approved_strategy"] == "approved: NONE"
    assert empty["order_gate"]["enabled"] is False and "not applicable" in empty["broker_reconciliation"]
    code, store, plan, clk = simulate(tmp, "08:30:00")
    s = snapshot.collect(clk.now())
    assert s["available"] and s["runner"]["exit_reason"] == "completed" and not s["runner"]["alive"]
    assert s["recent_reports"][0]["classification"] == "PASS" and s["acceptance"]["current_streak"] == 1


def test_dashboard_side_modules_load_no_broker_code():
    code = ("import sys; import trading.operations.report, trading.operations.store, trading.operations.killswitch,"
            " trading.operations.snapshot;"
            "print(any(m in sys.modules for m in ('trading.alpaca_client', 'requests')))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert out.stdout.strip() == "False", out.stderr
