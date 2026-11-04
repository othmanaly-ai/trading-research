"""Start and supervise the monitoring worker from the dashboard, without importing broker code
or loading credentials in the dashboard process. The worker is a separate process
(`python -m trading.monitor run`) that loads its own credentials.

Behaviour of the controls (also shown in the city):
- Start: desired state -> running. If no live worker (no heartbeat for 20 s), one worker process is
  launched. The OS lock guarantees at most one worker even if two launches race.
- Pause: desired state -> paused. The worker stays alive but makes no API calls.
- Stop: desired state -> stopped. The worker exits within about a second and releases its lock.
- Restart recovery: the dashboard's supervisor checks every 15 s; if the desired state is
  running but no worker is alive (crash, reboot of the dashboard, killed process), it launches one.
  Launches are limited to one per 20 s and 6 per hour, and every launch is recorded.
"""

import os
import subprocess
import sys
import threading
from datetime import timedelta

from trading.monitor import store as st

MIN_SPAWN_GAP = timedelta(seconds=20)
MAX_SPAWNS_PER_HOUR = 6
SUPERVISE_EVERY_S = 15
STRIP_FROM_CHILD = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


def _popen(cmd, cwd, env, log_path):
    log = open(log_path, "ab")
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000          # CREATE_NO_WINDOW
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    log.close()
    return proc.pid


SPAWN = _popen          # replaced in tests


def launch(store: st.MonitorStore, by: str, now=None) -> tuple[bool, str]:
    now = now or st.now_utc()
    recent = store.spawns_since(now - timedelta(hours=1))
    if recent and now - st.parse(recent[-1]["ts_utc"]) < MIN_SPAWN_GAP:
        return False, "a worker was launched less than 20 s ago; waiting for its heartbeat"
    if len(recent) >= MAX_SPAWNS_PER_HOUR:
        msg = f"launch limit reached ({MAX_SPAWNS_PER_HOUR} per hour); not launching. See the worker log."
        store.event("error", "supervisor", msg, now)
        return False, msg
    env = {k: v for k, v in os.environ.items() if k not in STRIP_FROM_CHILD}   # inherited, never read here
    st.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    pid = SPAWN([sys.executable, "-m", "trading.monitor", "run"], str(st.PROJECT_ROOT), env, st.LOG_PATH)
    store.record_spawn(by, pid, "launched", now)
    store.event("info", "supervisor", f"launched worker process pid {pid} ({by})", now)
    return True, f"worker process launched (pid {pid})"


def start(store: st.MonitorStore, by: str, now=None) -> str:
    store.set_desired("running", by, now)
    s = store.status(now)
    if s["worker"]["alive"]:
        return f"worker already running (pid {s['worker']['pid']}); desired state set to running"
    return launch(store, by, now)[1]


class Supervisor(threading.Thread):
    """Runs inside the dashboard server: restart recovery without duplicate workers."""

    def __init__(self, stop_event: threading.Event, interval: float = SUPERVISE_EVERY_S):
        super().__init__(daemon=True, name="monitor-supervisor")
        self.stop_event, self.interval = stop_event, interval

    def check_once(self) -> str | None:
        store = st.MonitorStore()
        try:
            if store.desired() != "running":
                return None
            if store.status()["worker"]["alive"]:
                return None
            return launch(store, "supervisor (restart recovery)")[1]
        finally:
            store.close()

    def run(self):
        while True:
            try:
                self.check_once()
            except Exception as exc:                 # never kill the dashboard over supervision
                try:
                    s = st.MonitorStore()
                    s.event("error", "supervisor", f"{type(exc).__name__}: {exc}")
                    s.close()
                except Exception:
                    pass
            if self.stop_event.wait(self.interval):
                return
