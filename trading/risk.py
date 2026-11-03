"""Deterministic position sizing and loss limits. The risk check has veto power:
when it returns a block reason, no trade happens, whatever the signal says."""

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade: float = 0.005     # R: fraction of equity lost if the stop is hit
    max_notional: float = 1.0         # L: position value / equity (1.0 = no leverage)
    participation: float = 0.01       # max fraction of median 1-minute volume
    daily_loss_limit: float = 0.01    # fraction of start-of-day equity
    max_drawdown: float = 0.05        # D: kill switch, fraction below peak equity
    # The values above are SPEC placeholders until the owner answers D1.
    placeholder: bool = True


def size_position(limits: RiskLimits, equity: float, price: float,
                  stop_distance: float, median_minute_volume: float) -> tuple[int, str]:
    """Shares and the name of the cap that bound. 0 shares means no trade."""
    if equity <= 0 or price <= 0 or stop_distance <= 0 or not math.isfinite(stop_distance):
        return 0, "invalid inputs"
    caps = {
        "risk": limits.risk_per_trade * equity / stop_distance,
        "notional": limits.max_notional * equity / price,
        "participation": limits.participation * max(median_minute_volume, 0.0),
    }
    binding = min(caps, key=caps.get)
    return int(math.floor(caps[binding])), binding


@dataclass
class RiskState:
    limits: RiskLimits
    peak_equity: float
    halted: bool = False
    day_start_equity: dict = field(default_factory=dict)

    def block_reason(self, equity: float, day, day_pnl: float = 0.0) -> str | None:
        self.peak_equity = max(self.peak_equity, equity)
        if self.halted:
            return "risk: drawdown kill switch active (needs owner review)"
        if equity <= self.peak_equity * (1 - self.limits.max_drawdown):
            self.halted = True
            return "risk: drawdown kill switch triggered"
        start = self.day_start_equity.setdefault(day, equity)
        if day_pnl <= -self.limits.daily_loss_limit * start:
            return "risk: daily loss limit reached"
        return None
