import numpy as np
import pandas as pd
import pytest

from trading.costs import BASE, SEVERE, STRESS
from trading.metrics import max_drawdown, percentile_of, random_direction_returns
from trading.risk import RiskLimits, RiskState, size_position


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
    assert state.block_reason(100_000, "d1") is None
    assert state.block_reason(100_000, "d1", day_pnl=-1_000) == "risk: daily loss limit reached"


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
