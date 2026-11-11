"""The interface through which a LATER, owner-approved strategy could hand versioned intents to the execution core.

No strategy is implemented or evaluated here. The approved-strategy registry (config/approved_strategies.json) is
read, never written; it is empty by owner decision, so every strategy-sourced intent is refused with
"NO APPROVED ACTIVE STRATEGY". The offline simulation uses SYNTHETIC test intents, labelled as such, which are not a
strategy and carry no signal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[2] / "config" / "approved_strategies.json"
NO_STRATEGY = "NO APPROVED ACTIVE STRATEGY"


@dataclass(frozen=True)
class IntentSource:
    kind: str                 # "strategy" (needs approval) | "lab_synthetic" (simulation only)
    strategy_id: str
    version: str
    note: str = ""


LAB_SYNTHETIC = IntentSource("lab_synthetic", "lab-synthetic", "v1",
                             "SYNTHETIC test intent for the offline simulation; not a strategy, no signal")


@dataclass(frozen=True)
class StrategyIntent:
    """What an approved strategy would supply. Sizing stays with the execution core (risk.size_position)."""
    source: IntentSource
    session: str
    sequence: int
    symbol: str
    side: str                 # "buy" only until a short policy exists
    qty: int
    ref_price: float
    stop_distance: float
    reason_ref: str           # pointer to the strategy's recorded decision evidence


def approved_strategies(path: Path = REGISTRY) -> list[dict]:
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("approved") or [])
    except (OSError, ValueError):
        return []


def source_refusal(source: IntentSource, path: Path = REGISTRY) -> str | None:
    """Why this intent source may not create orders, or None."""
    if source.kind == "lab_synthetic":
        return None          # simulation-only intents; the fake broker is the only possible destination in the lab
    if source.kind != "strategy":
        return f"unknown intent source kind {source.kind!r}"
    approved = approved_strategies(path)
    if not approved:
        return f"{NO_STRATEGY} (approved-strategy registry is empty)"
    if not any(a.get("strategy_id") == source.strategy_id and a.get("version") == source.version for a in approved):
        return f"strategy {source.strategy_id} {source.version} is not in the approved registry"
    return None
