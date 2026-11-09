"""Entry-blocking kill switch, independent of JARVIS or any language model.

ON = the file KILL_SWITCH.json exists in the runtime folder. An unreadable state counts as ON
(fail closed). Only the owner turns it off (CLI: `python -m trading.operations kill-switch off
--reason "..."`). Every change is appended to kill_switch_history.jsonl.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from trading.operations import paths


@dataclass(frozen=True)
class KillSwitchState:
    on: bool
    reason: str


def state(path: Path | None = None) -> KillSwitchState:
    try:
        p = path or paths.kill_switch_path()
        if not p.exists():
            return KillSwitchState(False, "off")
        try:
            info = json.loads(p.read_text(encoding="utf-8"))
            return KillSwitchState(True, str(info.get("reason", "no reason given")))
        except (OSError, ValueError):
            return KillSwitchState(True, "kill switch file unreadable (fail closed)")
    except Exception as exc:                    # any failure to determine the state blocks entries
        return KillSwitchState(True, f"kill switch state unknown ({type(exc).__name__}); fail closed")


def _history(p: Path, action: str, reason: str, by: str) -> None:
    rec = {"ts_utc": datetime.now(timezone.utc).isoformat(), "action": action, "reason": reason, "by": by}
    with open(p.parent / "kill_switch_history.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def set_on(reason: str, by: str = "owner (CLI)", path: Path | None = None) -> None:
    p = path or paths.kill_switch_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"reason": reason, "by": by, "ts_utc": datetime.now(timezone.utc).isoformat()}),
                 encoding="utf-8")
    _history(p, "on", reason, by)


def set_off(reason: str, by: str = "owner (CLI)", path: Path | None = None) -> None:
    if not reason.strip():
        raise ValueError("a reason is required to turn the kill switch off")
    p = path or paths.kill_switch_path()
    if p.exists():
        p.unlink()
    _history(p, "off", reason, by)
