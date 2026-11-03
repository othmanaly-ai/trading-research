import pytest

from trading.safety import OrderSubmissionDisabled, require_order_submission_allowed


@pytest.mark.parametrize("env", [
    {},
    {"ORDER_SUBMISSION_ENABLED": "false"},
    {"ORDER_SUBMISSION_ENABLED": "yes"},
    {"TRADING_MODE": "live", "ORDER_SUBMISSION_ENABLED": "true"},
])
def test_blocked(env, monkeypatch):
    monkeypatch.delenv("TRADING_MODE", raising=False)
    monkeypatch.delenv("ORDER_SUBMISSION_ENABLED", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(OrderSubmissionDisabled):
        require_order_submission_allowed()
