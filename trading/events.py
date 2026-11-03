"""Structured events consumed by the dashboard (schema version 1).

Every status, chart marker and number the interface shows must come from one of
these events or from the ledger built from them (trading/dashboard/ledger.py).
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field

SCHEMA_VERSION = 1
MODE_DEMO_REPLAY = "DEMO_REPLAY"

# Lower rank sorts first among events that share a timestamp.
EVENT_TYPES = {
    "session_open": 0,
    "feed_status": 1,
    "bar": 2,
    "signal": 3,
    "risk_status": 4,
    "decision": 5,
    "fill": 6,
    "position_closed": 7,
    "session_close": 8,
}


@dataclass(frozen=True)
class Event:
    ts_utc: str                 # ISO 8601, "Z" suffix
    source: str                 # producer, e.g. "demo_replay"
    mode: str                   # e.g. "DEMO_REPLAY"
    type: str
    strategy_id: str | None
    instrument: str | None
    payload: dict = field(default_factory=dict)
    event_id: str = ""

    def __post_init__(self):
        if self.type not in EVENT_TYPES:
            raise ValueError(f"unknown event type {self.type!r}")
        if not self.event_id:
            key = json.dumps([self.source, self.mode, self.type, self.strategy_id,
                              self.instrument, self.ts_utc, self.payload],
                             sort_keys=True, default=str)
            object.__setattr__(self, "event_id", hashlib.sha256(key.encode()).hexdigest()[:16])

    def sort_key(self):
        return (self.ts_utc, EVENT_TYPES[self.type], self.instrument or "", self.strategy_id or "")

    def to_dict(self) -> dict:
        return {"schema": SCHEMA_VERSION, **asdict(self)}
