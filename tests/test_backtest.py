"""Engine tests on SYNTHETIC fixtures (tests/synthetic.py). Not market evidence."""

from dataclasses import replace
from datetime import date

import pytest

from trading.backtest import StressOptions, _net_if_closed, run_backtest
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


def test_halt_or_missing_bars_carry_to_next_session_open(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    day.bars = day.bars[day.bars.index < utc("2026-11-24 20:40")]
    t = run_day(days, TARGET, Params(long_only=True)).trade
    nxt = days[date(2026, 11, 25)]
    assert t.exit_reason == "time exit (involuntary overnight carry)"
    assert t.exit_time == nxt.bars.index[0] and t.exit_price == nxt.bars.iloc[0]["open"]
    assert t.flags == ["unresolved: halt or missing data", "involuntary overnight carry"]
    assert t.carry_mark_price == day.bars["close"].iloc[-1]       # last real in-session price


def test_missing_scheduled_exit_bar_is_not_invented(days):
    """Only the 15:59 bar is missing: no fill is made from the 15:58 close."""
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    day.bars = day.bars.drop(index=utc("2026-11-24 20:59"))
    t = run_day(days, TARGET, Params(long_only=True)).trade
    assert "involuntary overnight carry" in t.flags
    assert t.exit_time == days[date(2026, 11, 25)].bars.index[0]


def test_breach_on_scheduled_exit_bar_uses_time_exit(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    params = replace(Params(long_only=True), stop_mult=None)
    last = utc("2026-11-24 20:59")
    p = day.bars.at[last, "open"]
    day.bars.loc[last, ["low", "close"]] = [p * 0.5, p * 0.6]
    t = run_day(days, TARGET, params, limits=RiskLimits(daily_loss_limit=0.001)).trade
    assert t.exit_reason == "time exit" and t.exit_price == pytest.approx(p * 0.6)
    assert t.flags == ["risk: daily loss limit breached at scheduled exit bar"]


def test_carry_exit_counts_against_next_session_limits():
    days = make_days(SESSIONS, seed=6)
    d1, d2 = date(2026, 11, 24), date(2026, 11, 25)
    day = replace_day(days, SESSIONS, d1, morning=0.01, last30=0.001)
    day.bars = day.bars[day.bars.index < utc("2026-11-24 20:40")]      # carried overnight
    nxt = days[d2]
    first = nxt.bars.index[0]
    nxt.bars.loc[first, ["open", "low"]] = [nxt.bars.at[first, "open"] * 0.5] * 2   # big gap down
    limits = RiskLimits(max_notional=0.05, daily_loss_limit=0.005, max_drawdown=0.5)
    res = run_backtest(days, SESSIONS, d1, d2, Params(long_only=True), BASE, limits, 100_000.0)
    carry = res.days[0].trade
    assert "involuntary overnight carry" in carry.flags and carry.net_pnl < -500
    assert res.days[1].skip_reason == "risk: daily loss limit reached"   # day 2 blocked by the carry loss


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
    # The first trade breaches intraday (punitive costs), exits at the next bar's open,
    # and every later session is blocked: no automatic reset.
    first = next(k for k, d in enumerate(res.days) if d.trade)
    assert res.days[first].trade.exit_reason == "risk: drawdown limit breached"
    assert res.days[first].trade.exit_time == res.days[first].trade.entry_time + MINUTE
    assert all(d.skip_reason == "risk: drawdown kill switch active (needs owner review)"
               for d in res.days[first + 1:])


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


def test_daily_loss_limit_uses_unrealized_and_exits_next_bar(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=-0.004)   # long, then falls
    params = replace(Params(), stop_mult=None)          # no stop: only the loss limit can act
    tight = RiskLimits(daily_loss_limit=0.0002)         # $20 on $100k
    t = run_day(days, TARGET, params, limits=tight).trade
    assert t.exit_reason == "risk: daily loss limit breached"
    # The first completed bar whose mark (net of modeled exit costs) breached the limit.
    bars = day.bars[(day.bars.index >= t.entry_time) & (day.bars.index < utc("2026-11-24 21:00"))]
    breach = next(ts for ts, b in bars.iterrows()
                  if _net_if_closed(BASE, 1, t.shares, t.entry_price, b["close"]) <= -20)
    assert t.exit_time == breach + MINUTE                    # next bar, not the breach bar itself
    assert t.exit_price == day.bars.at[breach + MINUTE, "open"]
    loose = run_day(days, TARGET, params, limits=RiskLimits(daily_loss_limit=0.5)).trade
    assert loose.exit_reason == "time exit"


def test_stop_takes_priority_over_loss_limit_in_same_bar(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    t = run_day(days, TARGET).trade
    bar_t = utc("2026-11-24 20:40")
    day.bars.loc[bar_t, "low"] = t.stop_price * 0.99
    day.bars.loc[bar_t, "close"] = t.stop_price * 0.995
    # Earlier bars rise, so only the 20:40 bar breaches both the stop and a $10 loss limit.
    hit = run_day(days, TARGET, limits=RiskLimits(daily_loss_limit=0.0001)).trade
    assert hit.exit_reason == "stop" and hit.exit_price == pytest.approx(t.stop_price)
    assert hit.exit_time == bar_t + MINUTE


def test_positions_never_held_past_close_except_halt(days):
    res = run_backtest(days, SESSIONS, SESSIONS[25].date, SESSIONS[-2].date, Params(), BASE,
                       RiskLimits(), 100_000.0)
    for tr in res.trades:
        close = next(s.close_utc for s in SESSIONS if s.date == tr.date)
        assert tr.exit_time <= close or "involuntary overnight carry" in tr.flags


def test_accounting_identity_over_a_run(days):
    res = run_backtest(days, SESSIONS, SESSIONS[25].date, SESSIONS[-2].date, Params(), BASE,
                       RiskLimits(), 100_000.0)
    assert res.end_equity == pytest.approx(res.start_equity + sum(t.net_pnl for t in res.trades))
    for tr in res.trades:
        sell_notional = tr.shares * (tr.exit_fill if tr.direction > 0 else tr.entry_fill)
        expected = tr.direction * tr.shares * (tr.exit_fill - tr.entry_fill) - BASE.sell_fee(sell_notional)
        assert tr.net_pnl == pytest.approx(expected)
        assert tr.notional <= RiskLimits().max_notional * tr.equity_before * 1.01   # notional cap (fill vs decision price)


def test_owner_baseline_sizing_in_engine(days):
    from trading.risk import OWNER_BASELINE_2026_11_03 as B
    replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    t = run_day(days, TARGET, limits=B).trade
    decision_price = days[TARGET].bars.at[utc("2026-11-24 20:29"), "close"]
    round_trip = decision_price * (2 * BASE.per_side_bp + BASE.sell_fee_bp) / 1e4
    stop_dist = 2 * t.sigma30 * decision_price
    assert t.shares * (stop_dist + round_trip) <= 0.001 * 100_000 + 1e-9      # all-in planned loss <= $100
    assert t.shares * decision_price <= 0.05 * 100_000 + 1e-9                 # notional <= $5,000
    assert t.shares * decision_price <= 0.10 * 100_000                        # gross exposure <= $10,000


def test_gap_through_daily_limit_exits_at_next_open_with_real_loss(days):
    from trading.risk import OWNER_BASELINE_2026_11_03 as B
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    params = replace(Params(), stop_mult=None)
    t0 = run_day(days, TARGET, params, limits=B).trade
    crash, nxt = utc("2026-11-24 20:40"), utc("2026-11-24 20:41")
    p = t0.entry_price
    day.bars.loc[crash, ["open", "high", "low", "close"]] = [p, p, p * 0.80, p * 0.82]
    day.bars.loc[nxt, ["open", "high", "low", "close"]] = [p * 0.75, p * 0.76, p * 0.74, p * 0.75]
    t = run_day(days, TARGET, params, limits=B).trade
    assert t.exit_reason == "risk: daily loss limit breached"
    assert t.exit_time == nxt and t.exit_price == pytest.approx(p * 0.75)    # next open, after the gap
    assert t.net_pnl < -0.005 * 100_000                  # realized loss is worse than the $500 threshold


def test_equity_counts_each_cost_exactly_once(days):
    """Equity = start + realized + net liquidation P&L; costs appear once, at the fills."""
    res = run_backtest(days, SESSIONS, SESSIONS[25].date, SESSIONS[-2].date, Params(long_only=True),
                       BASE, RiskLimits(), 100_000.0)
    k = BASE.per_side_bp / 1e4
    for t in res.trades:
        sell_ref = t.exit_price if t.direction > 0 else t.entry_price
        cost = t.shares * (t.entry_price * k + t.exit_price * k) \
            + t.shares * sell_ref * (1 - k if t.direction > 0 else 1 + k) * BASE.sell_fee_bp / 1e4
        assert t.gross_pnl - t.net_pnl == pytest.approx(cost)
        # A mark at the exit price equals the realized result: nothing double-counted at the close.
        assert _net_if_closed(BASE, t.direction, t.shares, t.entry_price, t.exit_price) == pytest.approx(t.net_pnl)
    assert res.end_equity == pytest.approx(100_000.0 + sum(t.net_pnl for t in res.trades))


def test_no_stop_variant_never_stops(days):
    day = replace_day(days, SESSIONS, TARGET, morning=0.01, last30=0.001)
    day.bars.loc[utc("2026-11-24 20:40"), "low"] = 1.0
    t = run_day(days, TARGET, replace(Params(), stop_mult=None)).trade
    assert t.stop_price is None and t.exit_reason == "time exit"
