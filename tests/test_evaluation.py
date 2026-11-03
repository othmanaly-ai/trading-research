"""Outcome classification, evaluation reports, spec versioning, and consistency
between the city (ledger snapshot) and detailed reports. SYNTHETIC data only."""

from datetime import date

import pandas as pd
import pytest

from trading.backtest import run_backtest
from trading.costs import BASE
from trading.dashboard.demo_replay import DEFAULT_CONFIG, build_demo, load_config
from trading.dashboard.ledger import Ledger
from trading.dashboard.server import research_status
from trading.evaluation import evaluate
from trading.outcomes import AMBIGUOUS, NEITHER, STOP_FIRST, TARGET_FIRST, classify_trade
from trading.risk import RiskLimits
from trading.sessions import sessions_between
from trading.strategies.intraday_momentum import MINUTE, Params
from trading.strategies.registry import PROJECT_ROOT, spec_hash, spec_info

from tests.synthetic import make_days, replace_day, utc

T0 = utc("2026-11-24 20:31")


def bars(rows):
    """rows: (high, low) per minute starting at T0."""
    idx = [T0 + k * MINUTE for k in range(len(rows))]
    return pd.DataFrame({"high": [h for h, _ in rows], "low": [l for _, l in rows]}, index=idx)


END = T0 + 10 * MINUTE


@pytest.mark.parametrize("rows, direction, stop, target, expected", [
    ([(101, 99), (102, 98.4)], 1, 98.5, 103, STOP_FIRST),
    ([(103.5, 99), (101, 98)], 1, 98.5, 103, TARGET_FIRST),
    ([(101, 99), (103.2, 98.1)], 1, 98.5, 103, AMBIGUOUS),     # both in one bar
    ([(101, 99), (102, 99)], 1, 98.5, 103, NEITHER),
    ([(101, 99), (101.6, 99)], -1, 101.5, 97, STOP_FIRST),      # short: stop above
    ([(101, 96.8), (102, 99)], -1, 101.5, 97, TARGET_FIRST),
    ([(101, 99), (102, 98.4)], 1, 98.5, None, STOP_FIRST),     # no target defined
    ([(101, 99), (102, 98.4)], 1, None, None, NEITHER),
])
def test_classification_rules(rows, direction, stop, target, expected):
    assert classify_trade(bars(rows), T0, END, direction, stop, target) == expected


def test_bars_after_exit_are_ignored():
    rows = [(101, 99), (101, 99), (101, 90)]
    assert classify_trade(bars(rows), T0, T0 + 2 * MINUTE, 1, 98.5, None) == NEITHER


def test_classifier_agrees_with_engine_stop_exits():
    sessions = sessions_between(date(2026, 9, 1), date(2026, 12, 10))
    days = make_days(sessions, seed=1)
    d = date(2026, 11, 24)
    day = replace_day(days, sessions, d, morning=0.01, last30=0.001)
    run = lambda: run_backtest(days, sessions, d, d, Params(), BASE, RiskLimits(), 1e5).trades[0]
    t = run()
    assert classify_trade(day.bars, t.entry_time, t.exit_time, t.direction, t.stop_price, None) == NEITHER
    day.bars.loc[utc("2026-11-24 20:40"), "low"] = t.stop_price * 0.999
    t = run()
    assert t.exit_reason == "stop"
    assert classify_trade(day.bars, t.entry_time, t.exit_time, t.direction, t.stop_price, None) == STOP_FIRST


def trade(net, gross, outcome="neither", session="2026-11-24"):
    return {"net_pnl": net, "gross_pnl": gross, "outcome": outcome, "session_date": session,
            "holding_minutes": 29.0, "shares": 10, "entry_fill": 100.0}


def report(trades, decisions=(), target_defined=False):
    return evaluate(mode="DEMO_REPLAY", trades=list(trades), decisions=list(decisions),
                    sessions_evaluated=["2026-11-24", "2026-11-25"], expected_sessions=2,
                    session_minutes=780, allocation=25_000, max_drawdown=0.01,
                    target_defined=target_defined)


def test_cost_accounting_and_sensitivity():
    r = report([trade(8.0, 10.0), trade(-6.0, -5.0, session="2026-11-25")])
    p = r["pnl"]
    assert p["gross"] == pytest.approx(5.0) and p["net"] == pytest.approx(2.0)
    assert p["modeled_costs"] == pytest.approx(3.0)
    assert p["cost_sensitivity"] == pytest.approx({"0x": 5.0, "1x": 2.0, "2x": -1.0, "3x": -4.0})
    assert r["sample"]["unique_sessions_traded"] == 2
    assert r["trades"]["avg_gain"] == 8.0 and r["trades"]["avg_loss"] == -6.0


def test_target_classes_not_applicable_without_target():
    r = report([trade(1, 1)])
    assert r["outcomes"]["target_first"] is None and r["outcomes"]["ambiguous"] is None
    assert any("no profit target" in x for x in r["limitations"])
    r = report([trade(1, 1, "ambiguous")], target_defined=True)
    assert r["outcomes"]["ambiguous"] == 1 and r["outcomes"]["target_first"] == 0


def test_unfillable_counted_from_decisions():
    decisions = [{"action": "skip", "reason": "data: no entry price"},
                 {"action": "skip", "reason": "signal: zero"}]
    r = report([], decisions)
    assert r["outcomes"]["unfillable"] == 1
    assert r["sample"]["skips"] == {"data: no entry price": 1, "signal: zero": 1}


def test_result_hash_is_reproducible_and_sensitive():
    a, b = report([trade(1, 2)]), report([trade(1, 2)])
    assert a["result_hash"] == b["result_hash"]
    assert report([trade(1, 3)])["result_hash"] != a["result_hash"]


@pytest.fixture(scope="module")
def demo_ledger():
    demo = build_demo(load_config(DEFAULT_CONFIG))
    ledger = Ledger(demo.meta)
    for e in demo.events:
        ledger.apply(e.to_dict())
    return demo, ledger


def test_reports_match_city(demo_ledger):
    _, ledger = demo_ledger
    snap = ledger.snapshot()
    for s in snap["strategies"]:
        r = ledger.evaluation(s["id"])
        assert r["pnl"]["net"] == pytest.approx(s["realized_pnl"], abs=1e-9)
        assert r["sample"]["trades"] == s["trades"]
        assert r["risk"]["max_drawdown"] == s["max_drawdown"]
        assert r["trades"]["wins"] == s["wins"] and r["trades"]["losses"] == s["losses"]
        assert r["mode"] == snap["mode"] == "DEMO_REPLAY"


def test_repeat_build_reproduces_reports(demo_ledger):
    demo, ledger = demo_ledger
    again = build_demo(load_config(DEFAULT_CONFIG))
    other = Ledger(again.meta)
    for e in again.events:
        other.apply(e.to_dict())
    for sid in demo.backtests:
        assert ledger.evaluation(sid)["result_hash"] == other.evaluation(sid)["result_hash"]


def test_engine_outcomes_match_exit_reasons(demo_ledger):
    _, ledger = demo_ledger
    for sid in ledger.strategies:
        for t in ledger.records[sid]["trades"]:
            assert (t["outcome"] == STOP_FIRST) == (t["exit_reason"] == "stop")


def test_event_stream_only_uses_information_available_at_each_time(demo_ledger):
    """Recompute each signal and entry from bar events that had arrived by then."""
    demo, _ = demo_ledger
    seen = {}            # instrument -> {bar start: payload}, from bar events received so far
    last_close = {}      # instrument -> close of the last bar of the previous session
    sessions = {s["date"]: s for s in demo.meta["sessions"]}
    checked_signals = checked_fills = 0
    for e in demo.events:
        if e.type == "session_open":
            for ins, bars_ in seen.items():
                if bars_:
                    last_close[ins] = bars_[max(bars_)]["c"]
            seen = {ins: {} for ins in seen}
        if e.type == "bar":
            seen.setdefault(e.instrument, {})[e.payload["t"]] = e.payload
            assert e.ts_utc == (pd.Timestamp(e.payload["t"]) + MINUTE).strftime("%Y-%m-%dT%H:%M:%SZ")
        if e.type == "signal" and e.payload["r1"] is not None and e.instrument in last_close:
            day = e.ts_utc[:10]
            p10_start = (pd.Timestamp(sessions[day]["open_utc"]) + 29 * MINUTE).strftime("%Y-%m-%dT%H:%M:%SZ")
            p10 = seen[e.instrument][p10_start]["c"]          # KeyError would mean a future bar was needed
            assert e.payload["r1"] == pytest.approx(p10 / last_close[e.instrument] - 1, abs=1e-6)
            checked_signals += 1
        if e.type == "fill" and e.payload["leg"] == "entry":
            assert e.ts_utc not in seen[e.instrument]           # the fill bar has not finished yet
            checked_fills += 1
    assert checked_signals > 0 and checked_fills > 0


def test_spec_version_and_hash():
    info = spec_info("intraday_momentum", Params())
    assert info["spec_version"] == "1.1"
    assert info["spec_sha256"] == spec_hash(PROJECT_ROOT / info["spec_path"])
    assert info["target_defined"] is False


def test_research_status_is_honest():
    r = research_status()
    assert r["modes"]["DEMO"]["available"] is True
    for m in ("HISTORICAL_REPLAY", "SIMULATION", "PAPER_ACCOUNT"):
        assert r["modes"][m]["available"] is False and r["modes"][m]["reason"]
    assert [p["expected_sessions"] for p in r["historical_periods"]] == [1511, 625, 587]
    assert all(p["sessions_with_verified_data"] == 0 for p in r["historical_periods"])
    assert "not been received" in r["skills_note"]
    assert not any(x["implementation"] == "ai_agent" for x in r["responsibilities"])
