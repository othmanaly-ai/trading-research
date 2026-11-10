"""Runner progress files in the runtime folder, so a stalled or failed runner is visible from outside.

- runner_startup.json: the latest start-up attempt (any process, before the single-runner lock). Each
  step is written before it starts, so a hang shows the step it never finished.
- runner_status.json: written only by the process holding the single-runner lock: its stage, phase and
  a timestamp refreshed every heartbeat (15 s). A stale timestamp while the process exists = stalled.
- runner_faults.log: Python stack traces written by a watchdog when start-up or one loop iteration takes
  too long (faulthandler), so the place where a hang happened is recorded.
Light imports only (this module is loaded before anything heavy).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

STARTUP_NAME, STATUS_NAME, FAULTS_NAME, LOG_NAME = ("runner_startup.json", "runner_status.json",
                                                    "runner_faults.log", "runner.log")


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, default=str), encoding="utf-8")
    os.replace(tmp, path)


def record(path: Path, stage: str, **extra) -> None:
    try:
        _write(path, {"pid": os.getpid(), "stage": stage, "ts_utc": datetime.now(timezone.utc).isoformat(), **extra})
    except OSError:
        pass                       # progress reporting must never stop the runner


def read(path: Path) -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
