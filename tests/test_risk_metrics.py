import numpy as np
import pandas as pd
import pytest

from trading.costs import BASE, SEVERE, STRESS
from trading.metrics import max_drawdown, percentile_of, random_direction_returns
from trading.risk import OWNER_BASELINE_2026_11_03, RiskLimits, RiskState, size_position


def test_risk_cap_binds():
    assert size_position(RiskLimits(), 100_000, 100.0, 1.0, 1e6) == (500, "risk")


def test_notional_cap_binds():
    assert size_position(RiskLimits(), 100_000, 100.0, 0.01, 1e6) == (1000, "notional")


def test_participation_cap_binds():
    assert size_position(RiskLimits(), 100_000, 100.0, 1.0, 1000) == (10, "participation")


@pytest.mark.parametrize("args", [(0, 100, 1, 1e6), (1e5, 100, 0, 1e6), (1e5, 100, float("nan"), 1e6)])
def test_invalid_sizing_inputs_give_zero(args):
    assert size_position(RiskLimits(), *args)[0] == 0


def test_daily_loss_limit():
    state = RiskState(RiskLimits(), peak_equity=100_000)
    assert state.block_reason(100_000, "d1") is None            # session start equity recorded
    assert state.block_reason(99_000, "d1") == "risk: daily loss limit reached"
    assert state.block_reason(99_000, "d2") is None              # daily block lasts one session


B = OWNER_BASELINE_2026_11_03


def test_owner_baseline_values():
    assert (B.risk_per_trade, B.max_notional, B.daily_loss_limit, B.max_drawdown,
            B.max_gross_exposure, B.max_positions) == (0.001, 0.05, 0.005, 0.03, 0.10, 2)
    assert B.risk_includes_costs and not B.placeholder


def test_risk_cap_includes_round_trip_costs():
    # $100k, R = 0.1% = $100; stop $1.00 away; round-trip cost $0.25/share.
    loose = RiskLimits(risk_per_trade=0.001, max_notional=10, max_gross_exposure=10)
    with_costs = RiskLimits(risk_per_trade=0.001, max_notional=10, max_gross_exposure=10, risk_includes_costs=True)
    assert size_position(loose, 100_000, 100, 1.0, 1e9, 0.25) == (100, "risk")
    assert size_position(with_costs, 100_000, 100, 1.0, 1e9, 0.25) == (80, "risk")    # 100 / 1.25


def test_baseline_notional_cap_binds_and_rounds_down():
    # 5% of $100k = $5,000 at $193.65 -> 25.8 shares -> 25.
    assert size_position(B, 100_000, 193.65, 0.10, 1e9, 0.04) == (25, "notional")


def test_gross_exposure_includes_pending_and_open():
    # $7,000 already used (open + pending) of the $10,000 gross cap: room for $3,000.
    assert size_position(B, 100_000, 100, 0.10, 1e9, 0.0, gross_in_use=7_000) == (30, "gross exposure")
    assert size_position(B, 100_000, 100, 0.10, 1e9, 0.0, gross_in_use=10_000)[0] == 0


def test_max_positions_counts_pending():
    assert size_position(B, 100_000, 100, 0.10, 1e9, positions_in_use=2) == (0, "max positions")
    assert size_position(B, 100_000, 100, 0.10, 1e9, positions_in_use=1)[0] > 0


def test_entry_that_cannot_fit_is_rejected():
    # A $6,000 share price exceeds the $5,000 notional cap: zero shares, rejected.
    assert size_position(B, 100_000, 6_000, 10.0, 1e9)[0] == 0


def test_drawdown_uses_high_water_mark_and_never_resets():
    state = RiskState(B, peak_equity=100_000)
    state.start_day("d1", 100_000)
    assert state.observe("d1", 102_000) is None                  # new high-water mark
    assert state.observe("d1", 98_900) == "risk: drawdown limit breached"   # below 102,000 x 0.97 = 98,940
    assert state.block_reason(110_000, "d9") == "risk: drawdown kill switch active (needs owner review)"


def test_daily_losses_accumulate_across_trades_and_marks():
    """No single extreme move is needed: two moderate losses in one session breach $500."""
    state = RiskState(B, peak_equity=100_000)
    state.start_day("d1", 100_000)
    assert state.observe("d1", 99_700) is None            # trade 1 realized -$300
    assert state.observe("d1", 99_600) is None            # open trade 2 marked -$100 more
    assert state.observe("d1", 99_450) == "risk: daily loss limit breached"   # cumulative -$550
    assert state.block_reason(99_450, "d1") == "risk: daily loss limit reached"


def test_daily_breach_uses_session_start_equity():
    state = RiskState(B, peak_equity=100_000)
    state.start_day("d1", 100_000)
    assert state.observe("d1", 99_501) is None
    assert state.observe("d1", 99_500) == "risk: daily loss limit breached"     # 0.5% of 100,000
    assert state.block_reason(99_600, "d1") == "risk: daily loss limit reached"


def test_cost_levels_ordered_and_round_trip():
    assert BASE.per_side_bp < STRESS.per_side_bp < SEVERE.per_side_bp
    assert 2 * BASE.per_side_bp == pytest.approx(2.0)
    assert BASE.fill_price(100, 1) == pytest.approx(100.01)
    assert BASE.fill_price(100, -1) == pytest.approx(99.99)


def test_max_drawdown():
    assert max_drawdown(pd.Series([100, 120, 90, 130.0])) == pytest.approx(0.25)


def test_random_baseline_centered_and_percentile():
    dist = random_direction_returns(np.full(200, 0.001), np.full(200, -0.001), n_runs=4000, seed=1)
    assert abs(np.median(dist)) < 0.01
    assert percentile_of(dist.max() + 1, dist) == 100.0
