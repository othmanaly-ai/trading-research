"""Entry-permission gate: a pure function. Every failing condition is reported, not just the first.

Entries are allowed only when the reason list is empty. In Milestone 1 the only environment is
DRY_RUN, which always adds a reason, so no input can produce an allowed entry. An unknown
environment name is refused too.
"""

from dataclasses import dataclass, field
from datetime import datetime

from trading.operations import ENVIRONMENT
from trading.operations.approvals import ApprovalResult
from trading.operations.killswitch import KillSwitchState
from trading.operations.schedule import DECISION_WINDOW

DEFINED_ENVIRONMENTS = (ENVIRONMENT,)


@dataclass(frozen=True)
class DataHealth:
    worker_alive: bool
    feed: str | None
    symbols: dict                      # symbol -> {"age_s": float|None, "fresh": bool}
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {"worker_alive": self.worker_alive, "feed": self.feed, "symbols": self.symbols,
                "reasons": list(self.reasons)}


@dataclass(frozen=True)
class GateInputs:
    environment: str
    approval: ApprovalResult
    phase: str
    decision_minute_utc: datetime
    now_utc: datetime
    data: DataHealth | None
    risk_reasons: tuple | None         # None = risk state unavailable
    kill_switch: KillSwitchState
    clock_ok: bool | None              # None = not verified
    records_ok: bool
    reconciliation_ok: bool | None = None   # PAPER only (not defined in Milestone 1)


@dataclass(frozen=True)
class EntryPermission:
    allowed: bool
    reasons: tuple


def evaluate(i: GateInputs) -> EntryPermission:
    r: list[str] = []
    if i.environment == ENVIRONMENT:
        r.append("environment DRY_RUN never permits entries")
    else:
        r.append(f"environment {i.environment!r} is not defined in Milestone 1; refused")
    if not i.approval.ok:
        r.extend(i.approval.reasons or ("no approved strategy",))
    if i.phase != DECISION_WINDOW:
        r.append(f"phase {i.phase}: not a decision window")
    age = (i.now_utc - i.decision_minute_utc).total_seconds()
    if age >= 60 or age < 0:
        r.append("decision time is not the current minute; past decisions are never replayed")
    if i.data is None:
        r.append("data health unavailable")
    else:
        r.extend(i.data.reasons)
    if i.risk_reasons is None:
        r.append("risk state unavailable (no strategy and no account positions are evaluated in DRY_RUN)")
    else:
        r.extend(i.risk_reasons)
    if i.environment != ENVIRONMENT and not i.reconciliation_ok:
        r.append("broker reconciliation not confirmed")
    if i.kill_switch.on:
        r.append(f"kill switch ON: {i.kill_switch.reason}")
    if i.clock_ok is None:
        r.append("clock not verified against the broker")
    elif not i.clock_ok:
        r.append("clock skew beyond tolerance")
    if not i.records_ok:
        r.append("records not writable")
    return EntryPermission(allowed=not r, reasons=tuple(r))
