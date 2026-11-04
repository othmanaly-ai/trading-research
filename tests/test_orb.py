"""Experiment 002 tests on SYNTHETIC bars with controlled price paths (not market data)."""

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from trading import orb_experiment as orbx
from trading.backtest import DayData
from trading.costs import BASE, ZERO
from trading.engine import CARRY, PROVISIONAL, UNRESOLVED, checks, first_bad_minute, run_strategy
from trading.risk import OWNER_BASELINE_2026_11_03 as B, RiskLimits
from trading.sessions import sessions_between
from trading.strategies.opening_range_breakout import (
    PRIMARY, AlwaysLongB3, OpeningRangeBreakout, ORBConfig,
)
from trading.validate import bars_to_frame

MIN = pd.Timedelta(minutes=1)
SESSIONS = sessions_between(date(2026, 11, 20), date(2026, 12, 2))
S = {s.date: s for s in SESSIONS}
D1, D2, EARLY = date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 27)


def make(session, closes, volume=1_000_000):
    """Bars from a list of closes: open = previous close, high/low +/-0.01%."""
    bars, prev = [], closes[0]
    for i, c in enumerate(closes):
        o = prev
        t = pd.Timestamp(session.open_utc) + i * MIN
        bars.append({"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": o, "c": c, "h": max(o, c) * 1.0001,
                     "l": min(o, c) * 0.9999, "v": volume, "n": 1, "vw": c})
        prev = c
    return DayData(session, bars_to_frame(bars), official_close=closes[-1])


def path(session, breakout_minute=60, level=101.0, after=None):
    """OR oscillates 99.5..100.5, flat 100 until the breakout minute, then `level` (or `after`)."""
    n = session.regular_minutes
    closes = [99.5 if i % 2 else 100.5 for i in range(30)] + [100.0] * (n - 30)
    if breakout_minute is not None:
        for i in range(breakout_minute, n):
            closes[i] = level if after is None else after(i)
    return closes


def days_for(**overrides):
    d = {s.date: make(s, path(s, breakout_minute=None)) for s in SESSIONS}
    d.update(overrides)
    return d


def run(days, day, strategy=None, costs=BASE, limits=B, exit_mode="c1_open"):
    res = run_strategy(days, SESSIONS, day, day, strategy or OpeningRangeBreakout(PRIMARY), costs, limits,
                       100_000.0, exit_mode)
    return res, res.days[0]


def utc(d, hhmm):
    return pd.Timestamp(f"{d} {hhmm}", tz="America/New_York").tz_convert("UTC")


# ---- signal and entry chronology ----------------------------------------------------

def test_completed_bar_signal_then_next_open_entry_and_c1_open_exit():
    days = days_for(**{str(D1): None})
    days[D1] = make(S[D1], path(S[D1], breakout_minute=60))
    dec = OpeningRangeBreakout().decide(days[D1])
    assert dec.plan.decision_time == utc(D1, "10:31")                    # signal bar 10:30 ends 10:31
    _, r = run(days, D1)
    t = r.trade
    assert t.entry_time == utc(D1, "10:31") and t.entry_price == days[D1].bars.at[utc(D1, "10:31"), "open"]
    assert t.exit_time == utc(D1, "15:59") and t.exit_price == days[D1].bars.at[utc(D1, "15:59"), "open"]
    assert t.exit_reason == "time exit"


def test_intrabar_cross_is_not_a_signal():
    day = make(S[D1], path(S[D1], breakout_minute=None))
    t = utc(D1, "10:30")
    day.bars.loc[t, "high"] = 105.0                                      # crosses H inside the bar
    assert OpeningRangeBreakout().decide(day).reason == "no breakout"


def test_future_bars_cannot_change_decision_or_size():
    days = days_for()
    days[D1] = make(S[D1], path(S[D1], breakout_minute=60))
    plan_before = OpeningRangeBreakout().decide(days[D1]).plan
    _, before = run(days, D1)
    # Anything from the decision time on (including the fill bar) cannot change the decision.
    from_decision = days[D1].bars.index >= utc(D1, "10:31")
    mutated = days[D1].bars.copy()
    for col in ("open", "high", "low", "close"):
        mutated.loc[from_decision, col] *= 1.02
    mutated.loc[from_decision, "volume"] = 5
    assert OpeningRangeBreakout().decide(DayData(S[D1], mutated, 101.0)).plan == plan_before
    # Bars after the entry bar cannot change the executed size or entry.
    after_entry = days[D1].bars.index >= utc(D1, "10:32")
    for col in ("open", "high", "low", "close"):
        days[D1].bars.loc[after_entry, col] *= 1.02
    _, after = run(days, D1)
    assert after.trade.shares == before.trade.shares and after.trade.entry_time == before.trade.entry_time


def test_latest_signal_and_hard_entry_limit():
    days = days_for()
    days[D1] = make(S[D1], path(S[D1], breakout_minute=329))             # 14:59 signal bar
    _, r = run(days, D1)
    assert r.trade.entry_time == utc(D1, "15:00")
    days[D1].bars = days[D1].bars.drop(index=utc(D1, "15:00"))          # no fallback past C - 60
    _, r = run(days, D1)
    assert r.trade is None and r.skip_reason.startswith("entry expired")
    days[D1] = make(S[D1], path(S[D1], breakout_minute=330))             # first close > H at 15:00
    _, r = run(days, D1)
    assert r.skip_reason == "no breakout"


def test_early_close_timestamps():
    days = days_for()
    days[EARLY] = make(S[EARLY], path(S[EARLY], breakout_minute=149))    # 11:59 signal bar
    _, r = run(days, EARLY)
    assert r.trade.entry_time == utc(EARLY, "12:00") and r.trade.exit_time == utc(EARLY, "12:59")
    days[EARLY] = make(S[EARLY], path(S[EARLY], breakout_minute=150))
    assert run(days, EARLY)[1].skip_reason == "no breakout"


# ---- missing bars --------------------------------------------------------------------

def test_incomplete_opening_range():
    day = make(S[D1], path(S[D1], breakout_minute=60))
    day.bars = day.bars.drop(index=utc(D1, "09:45"))
    assert OpeningRangeBreakout().decide(day).reason == "data: incomplete opening range"


def test_failed_check_before_signal_stops_session_and_is_recorded():
    days = days_for()
    days[D1] = make(S[D1], path(S[D1], breakout_minute=70))
    days[D1].bars = days[D1].bars.drop(index=utc(D1, "10:20"))
    res, r = run(days, D1)
    assert r.skip_reason == "data: check failed before signal"
    assert res.session_info[str(D1)] == {"m2_stop": True, "failed_check_minute_utc": str(utc(D1, "10:20"))}


def test_checks_function():
    day = make(S[D1], path(S[D1], breakout_minute=None))
    day.bars = day.bars.drop(index=utc(D1, "11:00"))
    fb = first_bad_minute(day)
    assert checks(day, utc(D1, "11:00"), fb) and not checks(day, utc(D1, "11:01"), fb)


def test_missing_exit_bar_carries_to_next_session_open():
    days = days_for()
    days[D1] = make(S[D1], path(S[D1], breakout_minute=60))
    days[D1].bars = days[D1].bars.drop(index=utc(D1, "15:59"))
    _, r = run(days, D1)
    assert r.trade.flags == [UNRESOLVED, CARRY]
    assert r.trade.exit_time == days[D2].bars.index[0] and r.trade.exit_price == days[D2].bars.iloc[0]["open"]


def test_dataset_boundary_is_provisional():
    days = {D1: make(S[D1], path(S[D1], breakout_minute=60))}
    days[D1].bars = days[D1].bars.drop(index=utc(D1, "15:59"))
    res, r = run(days, D1)
    assert PROVISIONAL in r.trade.flags and res.provisional_trades == [r.trade]


# ---- sizing, acceptance, costs ---------------------------------------------------------

def test_sizing_uses_most_restrictive_cap_and_costs():
    days = days_for()
    days[D1] = make(S[D1], path(S[D1], breakout_minute=60))
    _, r = run(days, D1)
    t = r.trade
    assert t.shares == int(0.05 * 100_000 // 101.0) and t.binding_cap == "notional"
    k = BASE.per_side_bp / 1e4
    ef, xf = t.entry_price * (1 + k), t.exit_price * (1 - k)
    assert t.net_pnl == pytest.approx(t.shares * (xf - ef) - t.shares * xf * BASE.sell_fee_bp / 1e4)
    assert run(days, D1, costs=ZERO)[1].trade.net_pnl == pytest.approx(r.trade.gross_pnl)


def test_gap_beyond_executable_limit_is_rejected():
    days = days_for()
    days[D1] = make(S[D1], path(S[D1], breakout_minute=60))
    days[D1].bars.loc[utc(D1, "10:31"), ["open", "high"]] = [130.0, 130.1]     # gap far above limit
    _, r = run(days, D1)
    assert r.trade is None and r.skip_reason == "risk: gap beyond executable limit"


def test_invalid_stop_at_entry():
    days = days_for()
    days[D1] = make(S[D1], path(S[D1], breakout_minute=60))
    days[D1].bars.loc[utc(D1, "10:31"), ["open", "low"]] = [90.0, 89.9]
    assert run(days, D1)[1].skip_reason == "invalid stop at entry"


def test_stop_active_through_c2_only_and_c1_close_unused():
    days = days_for()
    days[D1] = make(S[D1], path(S[D1], breakout_minute=60))
    days[D1].bars.loc[utc(D1, "15:59"), ["low", "close"]] = [50.0, 51.0]       # C-1 bar: ignored
    _, r = run(days, D1)
    assert r.trade.exit_reason == "time exit" and r.trade.exit_price == days[D1].bars.at[utc(D1, "15:59"), "open"]
    days[D1].bars.loc[utc(D1, "15:58"), "low"] = 90.0                          # C-2 bar: stop
    assert run(days, D1)[1].trade.exit_reason == "stop"


# ---- intraday drawdown, halts, delayed liquidation ------------------------------------

def test_intraday_drawdown_measured_on_marks():
    days = days_for()
    closes = path(S[D1], breakout_minute=60)
    for i in range(120, 130):
        closes[i] = 100.6                                                     # dip above L, then recover
    days[D1] = make(S[D1], closes)
    res, r = run(days, D1)
    assert r.trade.exit_reason == "time exit"
    assert res.max_drawdown_intraday > 0 and res.max_drawdown_intraday > (100_000 - res.end_equity) / 100_000


def test_drawdown_halt_exits_next_open_and_final_equity_after_liquidation():
    days = days_for()
    days[D1] = make(S[D1], path(S[D1], breakout_minute=60, after=lambda i: 101.0 if i < 200 else 100.7))
    tight = RiskLimits(**{**B.__dict__, "max_drawdown": 0.00001})
    res = run_strategy(days, SESSIONS, D1, D2, OpeningRangeBreakout(), BASE, tight, 100_000.0)
    t = res.days[0].trade
    assert res.halted and t.exit_reason == "risk: drawdown limit breached"
    assert res.days[1].skip_reason.startswith("risk: drawdown kill switch")
    assert res.end_equity == pytest.approx(100_000.0 + t.net_pnl)              # after the actual exit


def test_halt_with_trapped_position_counts_gap_loss():
    days = days_for()
    days[D1] = make(S[D1], path(S[D1], breakout_minute=60))
    days[D1].bars = days[D1].bars[days[D1].bars.index < utc(D1, "15:00")]     # no bars after 14:59
    nxt = days[D2]
    nxt.bars.loc[nxt.bars.index[0], ["open", "low"]] = [80.0, 79.9]           # gap down at next open
    res = run_strategy(days, SESSIONS, D1, D2, OpeningRangeBreakout(), BASE, B, 100_000.0)
    t = res.days[0].trade
    assert CARRY in t.flags and t.exit_price == 80.0 and t.net_pnl < -900
    assert res.end_equity == pytest.approx(100_000.0 + t.net_pnl)
    assert res.days[1].skip_reason == "risk: daily loss limit reached"         # carry loss hits day 2


# ---- comparators and normalization -------------------------------------------------------

def test_b3_entry_sizing_and_acceptance():
    days = days_for()
    days[D1] = make(S[D1], path(S[D1], breakout_minute=None))
    _, r = run(days, D1, AlwaysLongB3())
    assert r.trade.entry_time == utc(D1, "10:01")
    assert r.trade.shares == int(0.05 * 100_000 // days[D1].bars.at[utc(D1, "10:00"), "close"])
    days[D1].bars.loc[utc(D1, "10:01"), ["open", "high"]] = [140.0, 140.1]
    assert run(days, D1, AlwaysLongB3())[1].skip_reason == "risk: gap beyond executable limit"


def test_diagnostic_dollar_normalization():
    day = make(S[D1], path(S[D1], breakout_minute=60))
    d = orbx.diagnostic_trades(day, None, 99.5 * 0.9999, BASE, 31, 330)
    m = 31                                                                   # entry at 10:01 open
    op = day.bars["open"].to_numpy()
    k = BASE.per_side_bp / 1e4
    ef, xf = op[m] * (1 + k), op[389] * (1 - k)
    expect = 5000 / ef * (xf - ef) - 5000 / ef * xf * BASE.sell_fee_bp / 1e4
    assert d["pnl"][0] == pytest.approx(expect)


def test_b1_b2_reproducible_unmatched_and_identical_treatment():
    days = {s.date: make(s, path(s, breakout_minute=60 + 10 * k)) for k, s in enumerate(SESSIONS)}
    start, end = SESSIONS[1].date, SESSIONS[-2].date
    a = orbx.diagnostics(days, SESSIONS, start, end, strategy_entries=4, seeds=(1, 2), n_runs=300)
    b = orbx.diagnostics(days, SESSIONS, start, end, strategy_entries=4, seeds=(1, 2), n_runs=300)
    assert a == b
    assert "account return = total net dollar P&L / $100,000" in a["normalization"]
    assert a["strategy"]["account_return"] == pytest.approx(a["strategy"]["total_pnl"] / 100_000)
    assert 0 <= a["B1"]["1"]["strategy_percentile"] <= 100
    assert a["B1"]["1"]["mean_unmatched"] >= 0 and "conditional" in a["B2"]["1"]["note"]


# ---- lock and variant policy -------------------------------------------------------------

def test_lock_refuses_changed_definition_and_dirty_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(orbx, "_git_commit", lambda: "abc123+dirty")
    with pytest.raises(orbx.Refused, match="commit"):
        orbx.write_lock(tmp_path / "L.json")
    monkeypatch.setattr(orbx, "_git_commit", lambda: "abc123")
    lock = orbx.write_lock(tmp_path / "L.json")
    assert lock["tested_code_commit"] == "abc123" and orbx.check_lock(tmp_path / "L.json")
    tampered = json.loads((tmp_path / "L.json").read_text())
    tampered["fingerprint"]["budget"]["development"] = 10
    (tmp_path / "L.json").write_text(json.dumps(tampered))
    with pytest.raises(orbx.Refused, match="changed"):
        orbx.check_lock(tmp_path / "L.json")


def test_only_four_configurations_and_held_out_refused(capsys):
    assert [c.name for c in orbx.CONFIGURATIONS] == ["primary", "range_15", "range_45", "midpoint_stop"]
    assert orbx.fingerprint()["budget"] == {"development": 4, "validation": 1, "final": 1}
    assert orbx.main(["--run", "validation"]) == 2 and orbx.main(["--run", "final"]) == 2
    assert "not permitted" in capsys.readouterr().out
