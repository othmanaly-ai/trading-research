"""Evaluation report built from ledger records (docs/PRODUCT_SPEC.md section 7).

The same function will serve DEMO now and HISTORICAL REPLAY later; the mode is
part of the report and reports from different modes are never combined.
"""

import hashlib
import json
from collections import Counter

from trading.outcomes import (
    AMBIGUOUS, NEITHER, STOP_FIRST, TARGET_FIRST, UNFILLABLE, UNFILLABLE_REASONS,
)

COST_MULTIPLIERS = (0, 1, 2, 3)

MODE_LIMITATIONS = {
    "DEMO_REPLAY": "DEMO mode: synthetic fixture prices. These numbers test the software and "
                   "say nothing about any real market or strategy performance.",
    "HISTORICAL_REPLAY": "HISTORICAL REPLAY: real past prices from stored Alpaca bars, but fills, "
                         "costs and P&L are simulated. A few replayed sessions are an inspection "
                         "sample, not evidence of an edge; use the experiment runner's periods for that.",
}


def evaluate(*, mode: str, trades: list[dict], decisions: list[dict], sessions_evaluated: list[str],
             expected_sessions: int, session_minutes: float, allocation: float,
             max_drawdown: float, target_defined: bool) -> dict:
    """trades: position_closed payloads; decisions: decision payloads (both from the ledger)."""
    net = sum(t["net_pnl"] for t in trades)
    gross = sum(t["gross_pnl"] for t in trades)
    costs = gross - net
    wins = [t["net_pnl"] for t in trades if t["net_pnl"] > 0]
    losses = [t["net_pnl"] for t in trades if t["net_pnl"] <= 0]
    outcomes = Counter(t["outcome"] for t in trades)
    unfillable = sum(1 for d in decisions if d.get("reason") in UNFILLABLE_REASONS)
    skips = Counter(d["reason"] for d in decisions if d["action"] == "skip")
    n = len(trades)

    report = {
        "mode": mode,
        "sample": {
            "trades": n,
            "unique_sessions_traded": len({t["session_date"] for t in trades}),
            "sessions_evaluated": len(sessions_evaluated),
            "expected_sessions": expected_sessions,
            "coverage": len(sessions_evaluated) / expected_sessions if expected_sessions else 0.0,
            "skips": dict(skips),
        },
        "pnl": {
            "net": net, "gross": gross, "modeled_costs": costs,
            "net_return_on_allocation": net / allocation if allocation else 0.0,
            "cost_sensitivity": {f"{k}x": gross - k * costs for k in COST_MULTIPLIERS},
        },
        "risk": {
            "max_drawdown": max_drawdown,
            "time_in_market": sum(t["holding_minutes"] for t in trades) / session_minutes
            if session_minutes else 0.0,
            "avg_notional_to_allocation": (sum(t["shares"] * t["entry_fill"] for t in trades) / n / allocation)
            if n and allocation else 0.0,
        },
        "outcomes": {
            TARGET_FIRST: outcomes.get(TARGET_FIRST, 0) if target_defined else None,
            STOP_FIRST: outcomes.get(STOP_FIRST, 0),
            NEITHER: outcomes.get(NEITHER, 0),
            AMBIGUOUS: outcomes.get(AMBIGUOUS, 0) if target_defined else None,
            UNFILLABLE: unfillable,
            "target_defined": target_defined,
        },
        "trades": {
            "wins": len(wins), "losses": len(losses),
            "avg_gain": sum(wins) / len(wins) if wins else None,
            "avg_loss": sum(losses) / len(losses) if losses else None,
            "avg_holding_minutes": sum(t["holding_minutes"] for t in trades) / n if n else None,
        },
        "limitations": [
            MODE_LIMITATIONS.get(mode, f"Mode {mode}."),
            f"Sample: {n} trade(s) over {len(sessions_evaluated)} session(s). Small samples carry wide uncertainty.",
            "Costs are modeled (spread, slippage, fees), not measured fills.",
            "Outcome frequencies describe this sample only; they are not probabilities of future results.",
            "A target or stop being reached is a price event, separate from profit after costs.",
        ] + ([] if target_defined else
             ["This strategy version defines no profit target, so target-first and ambiguous "
              "outcomes are not applicable."]),
    }
    report["result_hash"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return report
