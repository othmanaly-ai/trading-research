"""Deterministic position sizing and loss limits. The risk check has veto power:
when it returns a block reason, no trade happens, whatever the signal says.

All limits apply to the whole simulated account. Exposure and position counts
include pending (submitted but unfilled) simulated entries.
"""

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade: float = 0.005     # R: fraction of equity lost if the stop is hit
    max_notional: float = 1.0         # L: one position's value / equity (1.0 = no leverage)
    participation: float = 0.01       # max fraction of median 1-minute volume
    daily_loss_limit: float = 0.01    # fraction of session-start equity
    max_drawdown: float = 0.05        # D: fraction below the equity high-water mark
    max_gross_exposure: float = 1.0   # all positions + pending entries / equity
    max_positions: int = 1            # open positions + pending entries
    risk_includes_costs: bool = False  # count modeled entry/exit costs inside R
    # The defaults above are SPEC placeholders. Owner-agreed sets are defined below.
    placeholder: bool = True


# Owner-agreed limits for the historical experiment, 2026-11-03 (SPEC D1 answered).
OWNER_BASELINE_2026_11_03 = RiskLimits(
    risk_per_trade=0.001, max_notional=0.05, participation=0.01, daily_loss_limit=0.005,
    max_drawdown=0.03, max_gross_exposure=0.10, max_positions=2, risk_includes_costs=True,
    placeholder=False,
)


def size_position(limits: RiskLimits, equity: float, price: float, stop_distance: float,
                  median_minute_volume: float, round_trip_cost_per_share: float = 0.0,
                  gross_in_use: float = 0.0, positions_in_use: int = 0) -> tuple[int, str]:
    """Shares (rounded down) and the name of the cap that bound. 0 shares = rejected.

    gross_in_use / positions_in_use cover open positions and pending entries.
    With risk_includes_costs, the loss at the stop includes the modeled round-trip
    cost per share, so R is a ceiling on the all-in planned loss.
    """
    if equity <= 0 or price <= 0 or stop_distance <= 0 or not math.isfinite(stop_distance):
        return 0, "invalid inputs"
    if positions_in_use >= limits.max_positions:
        return 0, "max positions"
    loss_per_share = stop_distance + (round_trip_cost_per_share if limits.risk_includes_costs else 0.0)
    exposure_room = max(0.0, limits.max_gross_exposure * equity - gross_in_use)
    caps = {
        "risk": limits.risk_per_trade * equity / loss_per_share,
        "notional": limits.max_notional * equity / price,
        "gross exposure": exposure_room / price,
        "participation": limits.participation * max(median_minute_volume, 0.0),
    }
    binding = min(caps, key=caps.get)
    return int(math.floor(caps[binding])), binding


@dataclass
class RiskState:
    """Account-level breach tracking. A drawdown breach halts permanently (no reset);
    a daily breach blocks new entries for the rest of that session."""
    limits: RiskLimits
    peak_equity: float
    halted: bool = False
    blocked_day: object = None
    day_start_equity: dict = field(default_factory=dict)

    def start_day(self, day, equity: float) -> None:
        self.day_start_equity.setdefault(day, equity)

    def observe(self, day, mark_equity: float) -> str | None:
        """Update the high-water mark with a mark-to-market equity (realized + unrealized
        after modeled costs) and return a breach reason, if any."""
        self.peak_equity = max(self.peak_equity, mark_equity)
        start = self.day_start_equity.setdefault(day, mark_equity)
        if mark_equity <= self.peak_equity * (1 - self.limits.max_drawdown):
            self.halted = True
            return "risk: drawdown limit breached"
        if mark_equity - start <= -self.limits.daily_loss_limit * start:
            self.blocked_day = day
            return "risk: daily loss limit breached"
        return None

    def block_reason(self, equity: float, day) -> str | None:
        """Checked before any new entry; `equity` is current mark-to-market equity."""
        self.start_day(day, equity)
        if self.halted:
            return "risk: drawdown kill switch active (needs owner review)"
        breach = self.observe(day, equity)
        if breach == "risk: drawdown limit breached":
            return "risk: drawdown kill switch triggered"
        if self.blocked_day == day:
            return "risk: daily loss limit reached"
        return None
