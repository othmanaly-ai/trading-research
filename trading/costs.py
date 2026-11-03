"""Transaction cost model. All rates are in basis points (1 bp = 0.01%)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    name: str
    half_spread_bp: float
    slippage_bp: float
    # SEC Section 31 + FINRA TAF on the sell side. Rates change over time:
    # look up the current values before trusting results (SPEC section 10).
    sell_fee_bp: float
    commission_per_order: float = 0.0

    @property
    def per_side_bp(self) -> float:
        return self.half_spread_bp + self.slippage_bp

    def fill_price(self, price: float, side: int) -> float:
        """side +1 = buy (pays more), -1 = sell (receives less)."""
        return price * (1 + side * self.per_side_bp / 1e4)

    def sell_fee(self, sell_notional: float) -> float:
        return sell_notional * self.sell_fee_bp / 1e4


# Spread and slippage guesses from SPEC section 10; replace with measured
# SPY quotes once data access works. Sell fee is a conservative placeholder.
BASE = CostModel("base", half_spread_bp=0.5, slippage_bp=0.5, sell_fee_bp=0.3)
STRESS = CostModel("stress", half_spread_bp=1.0, slippage_bp=2.0, sell_fee_bp=0.6)
SEVERE = CostModel("severe", half_spread_bp=2.0, slippage_bp=2.5, sell_fee_bp=0.6)
ZERO = CostModel("zero", half_spread_bp=0.0, slippage_bp=0.0, sell_fee_bp=0.0)

COST_LEVELS = (BASE, STRESS, SEVERE)
