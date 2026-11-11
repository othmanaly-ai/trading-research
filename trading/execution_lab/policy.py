"""Execution policy: every field is UNSET until the owner approves it. Nothing here chooses an owner limit.

Rules:
- A missing required policy BLOCKS the affected risk-increasing operation (a new entry, a protective order whose method
  is unset). It never silently picks a default.
- Risk-reducing operations (cancel, reconcile, emergency stop) always proceed; any follow-up that depends on an unset
  policy (escalation timing, what to do with remaining exposure) is reported as "UNSET: owner decision".
- APPROVED is empty: no approval file exists. LAB_TEST_POLICY holds SYNTHETIC values used only inside the offline
  simulation so its scenarios can run; it is labelled everywhere it is used and is not a proposal.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields

# field -> (owner decision id in docs/EXECUTION_POLICY_DECISIONS.md, plain-language meaning)
DECISIONS = {
    "order_type": ("A2", "entry order type (for example limit)"),
    "time_in_force": ("A2", "how long an entry order may work (day, ioc, fok)"),
    "protection_method": ("A2", "how filled shares get a broker-side stop: bracket or stop_after_fill"),
    "max_unprotected_seconds": ("A3", "longest time filled shares may be without an active stop"),
    "unprotected_exceeded_action": ("A3", "what happens when that time is exceeded"),
    "unknown_escalation_seconds": ("A4", "when an unresolved unknown outcome is escalated to the owner"),
    "cancel_confirm_timeout_seconds": ("A5", "when an unconfirmed cancellation is re-read and escalated"),
    "emergency_exposure_action": ("A6", "what an emergency stop does with remaining exposure"),
    "max_orders_per_session": ("A1", "most entry intents per session"),
    "max_shares_per_order": ("A1", "largest entry order in shares"),
    "max_notional_per_order": ("A1", "largest entry order in dollars"),
}
REQUIRED_FOR = {
    "entry": ["order_type", "time_in_force", "protection_method", "max_unprotected_seconds",
              "unprotected_exceeded_action", "max_orders_per_session", "max_shares_per_order", "max_notional_per_order"],
    "protect": ["protection_method", "max_unprotected_seconds"],
}
# Values the simulation understands. "close_exposure" exists as a choice the owner could make, but no automatic
# liquidation is implemented: choosing it would leave the action NOT IMPLEMENTED and unresolved.
ALLOWED = {
    "order_type": {"limit"},
    "time_in_force": {"day", "ioc", "fok"},
    "protection_method": {"bracket", "stop_after_fill"},
    "unprotected_exceeded_action": {"block_and_alert", "close_exposure"},
    "emergency_exposure_action": {"leave_for_owner", "close_exposure"},
}


@dataclass(frozen=True)
class ExecutionPolicy:
    order_type: str | None = None
    time_in_force: str | None = None
    protection_method: str | None = None
    max_unprotected_seconds: float | None = None
    unprotected_exceeded_action: str | None = None
    unknown_escalation_seconds: float | None = None
    cancel_confirm_timeout_seconds: float | None = None
    emergency_exposure_action: str | None = None
    max_orders_per_session: int | None = None
    max_shares_per_order: int | None = None
    max_notional_per_order: float | None = None
    label: str = "UNSET"

    def missing(self, operation: str) -> list[str]:
        return [f for f in REQUIRED_FOR.get(operation, []) if getattr(self, f) is None]

    def invalid(self) -> list[str]:
        return [f"{k}={getattr(self, k)!r} not one of {sorted(v)}" for k, v in ALLOWED.items()
                if getattr(self, k) is not None and getattr(self, k) not in v]

    def version(self) -> str:
        return "pol-" + hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:10]

    def table(self) -> list[dict]:
        return [{"field": f.name, "decision": DECISIONS[f.name][0], "meaning": DECISIONS[f.name][1],
                 "value": getattr(self, f.name), "status": "UNSET" if getattr(self, f.name) is None else self.label}
                for f in fields(self) if f.name in DECISIONS]


APPROVED = ExecutionPolicy(label="APPROVED")    # nothing approved: every field None

LAB_TEST_POLICY = ExecutionPolicy(
    order_type="limit", time_in_force="day", protection_method="stop_after_fill", max_unprotected_seconds=30,
    unprotected_exceeded_action="block_and_alert", unknown_escalation_seconds=300, cancel_confirm_timeout_seconds=120,
    emergency_exposure_action="leave_for_owner", max_orders_per_session=10, max_shares_per_order=60,
    max_notional_per_order=6_000.0, label="LAB TEST VALUE (synthetic, not approved)")


def describe_missing(fields_missing: list[str]) -> list[str]:
    return [f"POLICY UNSET: {f} ({DECISIONS[f][1]}; owner decision {DECISIONS[f][0]})" for f in fields_missing]
