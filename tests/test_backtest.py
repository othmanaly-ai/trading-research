"""Engine tests on SYNTHETIC fixtures (tests/synthetic.py). Not market evidence."""

from dataclasses import replace
from datetime import date

import pytest

from trading.backtest import StressOptions, run_backtest
from trading.costs import BASE, ZERO, CostModel
from trading.risk import RiskLimits
from trading.sessions import sessions_between
from trading.strategies.intraday_momentum import MINUTE, Params

from tests.synthetic import make_days, replace_day, utc

SESSIONS = sessions_between(date(2026, 9, 1), date(2026, 12, 10))
TARGET = date(2026, 11, 24)        # normal day, close 21:00 UTC
EARLY = date(2026, 11, 27)         # early close, 18:00 UTC


@pytest.fixture
def days():
    return make_days(SESSIONS, seed=1)


def run_day(days, d, params=Params(), costs=BASE, limits=RiskLimits(), **kw):
    result = run_backtest(days, SESSIONS, d, d, params, costs, limits, 100_000.0, **kw)
    return result.days[0]


def test_signal_direction(days):
    replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    assert run_day(days, TARGET).trade.direction == 1
    replace_day(days, SESSIONS, TARGET, morning=-0.01, last30=0.001)
    assert run_day(days, TARGET).trade.direction == -1
    assert run_day(days, TARGET, Params(long_only=True)).skip_reason == "signal: negative, long-only"


def test_entry_is_one_minute_after_decision_with_costs(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    t = run_day(days, TARGET).trade
    assert t.entry_time == utc("2026-11-24 20:31")          # 15:31 ET
    assert t.entry_price == day.bars.at[t.entry_time, "open"]
    assert t.entry_fill == pytest.approx(t.entry_price * (1 + 1e-4))


def test_time_exit_pnl_matches_formula(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    t = run_day(days, TARGET).trade
    assert t.exit_reason == "time exit"
    assert t.exit_price == day.bars.at[utc("2026-11-24 20:59"), "close"]
    exit_fill = t.exit_price * (1 - 1e-4)
    fee = t.shares * exit_fill * 0.3e-4
    assert t.net_pnl == pytest.approx(t.shares * (exit_fill - t.entry_fill) - fee)
    z = run_day(days, TARGET, costs=ZERO).trade
    assert z.net_pnl == pytest.approx(z.gross_pnl)


def test_stop_fills_at_stop_or_gapped_open(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    t = run_day(days, TARGET).trade
    bar_t = utc("2026-11-24 20:40")
    day.bars.loc[bar_t, "low"] = t.stop_price * 0.999
    hit = run_day(days, TARGET).trade
    assert hit.exit_reason == "stop" and hit.exit_price == pytest.approx(t.stop_price)
    day.bars.loc[bar_t, "open"] = t.stop_price * 0.998
    day.bars.loc[bar_t, "low"] = t.stop_price * 0.997
    gap = run_day(days, TARGET).trade
    assert gap.exit_price == pytest.approx(t.stop_price * 0.998)


def test_stop_touched_in_entry_bar_counts(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    t = run_day(days, TARGET).trade
    day.bars.loc[t.entry_time, "low"] = t.stop_price * 0.999
    assert run_day(days, TARGET).trade.exit_time == t.entry_time + MINUTE


def test_future_bars_cannot_change_decision(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    before = run_day(days, TARGET).trade
    future = day.bars.index >= utc("2026-11-24 20:30")      # decision time
    for col in ("open", "high", "low", "close"):
        day.bars.loc[future, col] *= 0.9
    day.bars.loc[future, "volume"] = 1
    after = run_day(days, TARGET).trade
    assert (after.direction, after.shares, after.r1, after.sigma30) == \
        (before.direction, before.shares, before.r1, before.sigma30)


def test_early_close_shifts_times(days):
    replace_day(days, SESSIONS, EARLY, morning=0.01, last30=0.001)
    t = run_day(days, EARLY).trade
    assert t.entry_time == utc("2026-11-27 17:31")           # 12:31 ET
    assert t.exit_time == utc("2026-11-27 18:00")            # 13:00 ET


def test_missing_signal_bar_skips(days):
    day = days[TARGET]
    day.bars = day.bars.drop(index=utc("2026-11-24 14:59"))  # 09:59 ET
    assert run_day(days, TARGET).skip_reason == "data: missing 09:59 bar"


def test_structural_failure_before_decision_skips(days):
    day = days[TARGET]
    t = utc("2026-11-24 16:00")
    day.bars.loc[t, "high"] = day.bars.at[t, "low"] * 0.99
    assert run_day(days, TARGET).skip_reason == "data: structural check failed"


def test_gap_before_decision_skips(days):
    day = days[TARGET]
    day.bars = day.bars.drop(index=utc("2026-11-24 20:10"))
    assert run_day(days, TARGET).skip_reason == "data: gap before decision"


def test_missing_session_skips(days):
    del days[TARGET]
    assert run_day(days, TARGET).skip_reason == "data: session missing"


def test_warmup_and_first_day():
    days = make_days(SESSIONS, seed=2)
    res = run_backtest(days, SESSIONS, SESSIONS[0].date, SESSIONS[25].date, Params(), BASE,
                       RiskLimits(), 100_000.0)
    assert res.days[0].skip_reason == "data: missing previous close"
    assert all(d.skip_reason == "warmup: insufficient sigma history" for d in res.days[1:20])
    assert res.days[20].trade is not None or res.days[20].skip_reason.startswith("signal")


def test_halt_exits_next_session_open(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    day.bars = day.bars[day.bars.index < utc("2026-11-24 20:40")]
    t = run_day(days, TARGET).trade
    nxt = days[date(2026, 11, 25)]
    assert t.exit_reason == "halt: exit next open"
    assert t.exit_price == nxt.bars.iloc[0]["open"]
    assert t.flags == ["halted; held overnight"]


def test_moc_exit_uses_official_close(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    t = run_day(days, TARGET, Params(exit_mode="moc")).trade
    assert t.exit_price == day.official_close and t.exit_reason == "time exit (MOC)"


def test_kill_switch_blocks_after_drawdown():
    days = make_days(SESSIONS, seed=3)
    costly = CostModel("punitive", half_spread_bp=50, slippage_bp=50, sell_fee_bp=0)
    limits = RiskLimits(max_drawdown=0.001)
    res = run_backtest(days, SESSIONS, date(2026, 10, 1), date(2026, 11, 30), Params(),
                       costly, limits, 100_000.0)
    reasons = [d.skip_reason for d in res.days]
    assert "risk: drawdown kill switch triggered" in reasons
    first = reasons.index("risk: drawdown kill switch triggered")
    assert all(r == "risk: drawdown kill switch active (needs owner review)" for r in reasons[first + 1:])


def test_stress_entry_failures_are_deterministic():
    days = make_days(SESSIONS, seed=4)
    run = lambda: run_backtest(days, SESSIONS, date(2026, 10, 1), date(2026, 11, 30), Params(),
                               BASE, RiskLimits(), 1e5, StressOptions(entry_fail_rate=0.3, seed=7))
    a, b = run(), run()
    fails = [d.skip_reason == "stress: entry order failed" for d in a.days]
    assert any(fails)
    assert fails == [d.skip_reason == "stress: entry order failed" for d in b.days]


def test_fill_fraction_halves_size(days):
    replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    full = run_day(days, TARGET).trade.shares
    half = run_day(days, TARGET, stress=StressOptions(fill_fraction=0.5)).trade.shares
    assert half == int(full * 0.5)


def test_short_pays_sell_fee_on_entry(days):
    replace_day(days, SESSIONS, TARGET, morning=-0.01, last30=-0.001)
    t = run_day(days, TARGET).trade
    exit_fill = t.exit_price * (1 + 1e-4)
    fee = t.shares * t.entry_fill * 0.3e-4
    assert t.direction == -1
    assert t.net_pnl == pytest.approx(-t.shares * (exit_fill - t.entry_fill) - fee)


def test_no_stop_variant_never_stops(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    day.bars.loc[utc("2026-11-24 20:40"), "low"] = 1.0
    t = run_day(days, TARGET, replace(Params(), stop_mult=None)).trade
    assert t.stop_price is None and t.exit_reason == "time exit"
