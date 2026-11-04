"""Background market-data worker (its own process; only this process loads Alpaca credentials).

  python -m trading.monitor run [--symbols SPY,QQQ,IWM] [--feed iex|sip] [--poll 60]

Behaviour
- One worker at a time: an OS file lock (data/monitoring/worker.lock) is held for the process
  lifetime and released automatically if the process dies. A second worker exits immediately.
- Exchange calendar (XNYS): polls only during the regular session; one catch-up poll after the
  close; idle (no API calls) on weekends, holidays and outside hours.
- Bounded polling: one multi-symbol GET per poll (default every 60 s) - far below Alpaca's
  free-plan limit of 200 requests per minute.
- The in-progress minute is never requested (it would be a partial bar). For SIP the latest
  15 minutes are not requested (free-plan delay). The feed is never switched on an error.
- Failures: connection errors and 5xx/429 back off 5, 10, 20, 40, 80, 160, then 300 s (cap);
  401/403 (access refused) waits 600 s; missing credentials waits 300 s. Each failure is recorded.
- Duplicates: bars are keyed by (symbol, feed, bar start); repeats are ignored and counted.
- Reserved periods: never requests or stores bars dated on or before the reserved-period end.
- Control: the desired state in the store (running / paused / stopped) is checked every second.
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading.monitor import store as st

BACKOFF = (5, 10, 20, 40, 80, 160, 300)
ACCESS_REFUSED_WAIT = 600
NO_CREDENTIALS_WAIT = 300
CATCHUP_WINDOW = timedelta(hours=2)


class SingleInstanceLock:
    def __init__(self, path: Path):
        self.path, self.fh = path, None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self.fh = fh
        return True

    def release(self) -> None:
        if not self.fh:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
        finally:
            self.fh.close()
            self.fh = None


class _StopRequested(Exception):
    pass


def default_client_factory(sleep):
    from trading.alpaca_client import ReadOnlyAlpacaClient, load_credentials
    return ReadOnlyAlpacaClient(*load_credentials(), timeout=20, sleep=sleep)


def code_version() -> str:
    """Git commit of the running code (+dirty if the working tree has uncommitted changes)."""
    import subprocess
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=st.PROJECT_ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=st.PROJECT_ROOT,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return (head or "unknown") + ("+dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _floor_minute(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0)


class Worker:
    def __init__(self, store: st.MonitorStore, symbols=st.DEFAULT_SYMBOLS, feed: str = "iex",
                 poll_seconds: int = st.POLL_SECONDS, client_factory=default_client_factory,
                 clock=st.now_utc, lock_path: Path | None = None, pid: int | None = None, version: str | None = None):
        if feed not in st.FEEDS:
            raise ValueError(f"feed must be one of {list(st.FEEDS)}")
        self.store, self.symbols, self.feed, self.poll_seconds = store, list(symbols), feed, poll_seconds
        self.client_factory, self.clock = client_factory, clock
        self.lock = SingleInstanceLock(lock_path or st.LOCK_PATH)
        self.pid = pid or os.getpid()
        self.version = version
        self.run_id: int | None = None
        self.client = None
        self.next_poll: datetime | None = None
        self.backoff_until: datetime | None = None
        self.failures = 0
        self.catchup_done: set = set()
        self.state = None
        self.stopping = False
        from trading.monitor.quality import QualityChecker
        # Delayed-SIP vs IEX data-quality comparison (only meaningful when the live feed is IEX).
        self.quality = QualityChecker(store, self.symbols, clock) if feed == "iex" else None

    # ---- lifecycle -------------------------------------------------------------------
    def start(self) -> bool:
        if not self.lock.acquire():
            self.store.event("warning", "duplicate",
                             f"worker pid {self.pid} not started: another worker holds the lock", self.clock())
            return False
        now = self.clock()
        cfg = {"symbols": self.symbols, "feed": self.feed, "poll_seconds": self.poll_seconds, "timeframe": "1Min",
               "adjustment": "raw", "feed_label": st.FEEDS[self.feed]["label"]}
        import json
        self.version = self.version or code_version()
        cfg["code_version"] = self.version
        self.run_id = self.store.start_run(self.pid, self.version, cfg, now)
        self.store.update_worker(pid=self.pid, state="starting", detail="worker started", started_utc=st.iso(now),
                                 heartbeat_utc=st.iso(now), stopped_utc=None, exit_reason=None,
                                 config_json=json.dumps(cfg), consecutive_failures=0, backoff_until_utc=None,
                                 next_poll_utc=None)
        self.store.event("info", "lifecycle", f"worker pid {self.pid} started ({self.feed}, {','.join(self.symbols)})", now)
        return True

    def shutdown(self, reason: str) -> None:
        now = self.clock()
        self.store.update_worker(state="stopped", detail=reason, stopped_utc=st.iso(now), exit_reason=reason,
                                 heartbeat_utc=st.iso(now), next_poll_utc=None)
        if self.run_id:
            self.store.end_run(self.run_id, now, reason)
        self.store.event("info", "lifecycle", f"worker pid {self.pid} stopped: {reason}", now)
        self.lock.release()

    def run(self, sleep=time.sleep) -> int:
        if not self.start():
            return 1
        reason = "stop requested"
        try:
            while not self.stopping:
                sleep(self.step())
        except KeyboardInterrupt:
            reason = "interrupted (Ctrl+C)"
        except Exception as exc:                       # recorded; the lock is released below
            reason = f"crashed: {type(exc).__name__}: {exc}"
            self.store.event("error", "crash", reason, self.clock())
        finally:
            self.shutdown(reason)
        return 0

    # ---- one iteration -----------------------------------------------------------------
    def _set(self, state: str, detail: str, **extra) -> None:
        if state != self.state:
            self.store.event("info", "state", f"{state}: {detail}", self.clock())
        self.state = state
        self.store.update_worker(state=state, detail=detail, heartbeat_utc=st.iso(self.clock()), **extra)

    def step(self) -> float:
        now = self.clock()
        self.store.update_worker(heartbeat_utc=st.iso(now))
        if self.run_id:
            self.store.touch_run(self.run_id, now)
        desired = self.store.desired()
        if desired == "stopped":
            self.stopping = True
            return 0
        if desired == "paused":
            self._set("paused", "paused by request: no data is fetched; Start resumes")
            return 1
        if self.backoff_until and now < self.backoff_until:
            return 1
        if st.session_date_et(now) <= st.RESERVED_END:
            self._set("refused", f"today is inside the reserved research periods (through {st.RESERVED_END}); "
                                 "monitoring is not allowed to fetch these dates")
            return 60
        if self.quality is not None:
            self._quality(now)
            if self.stopping:
                return 0
        mk = st.market_state(now)
        if mk["open"] and self.quality is not None:
            self.quality.mark_monitored(mk["session"], now)
        if mk["open"]:
            if self.next_poll is None or now >= self.next_poll:
                self._poll(mk["session"], now)
            elif self.state not in ("running",):
                self._set("running", "market open; waiting for the next poll")
            return 1
        last = mk["last_session"]
        if (last and last.date == st.session_date_et(now) and last.date not in self.catchup_done
                and now - last.close_utc <= CATCHUP_WINDOW):
            self._poll(last, now, catchup=True)
            return 1
        self._set("market_closed", f"market closed ({mk['reason']}); next open {st.iso(mk['next_open'])}; "
                                   "no API calls while closed", next_poll_utc=st.iso(mk["next_open"]))
        return 1

    def _quality(self, now: datetime) -> None:
        """One bounded step of the delayed-SIP comparison; its failures never stop live polling."""
        from trading.alpaca_client import MissingCredentials
        try:
            if self.client is None:
                self.client = self.client_factory(self._sleep_with_heartbeat)
            self.quality.step(self.client, now)
        except _StopRequested:
            self.stopping = True
        except MissingCredentials:
            return                                     # the live path records this error
        except Exception as exc:                       # recorded, never fatal to the worker
            self.store.event("error", "quality-error", f"{type(exc).__name__}: {exc}")

    def _sleep_with_heartbeat(self, seconds: float) -> None:
        """Used by the client for its bounded 429 waits: keeps the heartbeat and honours Stop."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.store.update_worker(heartbeat_utc=st.iso(self.clock()))
            if self.store.desired() == "stopped":
                raise _StopRequested()
            time.sleep(min(1.0, max(0.0, end - time.monotonic())))

    def _window(self, session, now: datetime):
        if self.feed == "sip":
            end = _floor_minute(now - timedelta(minutes=15)) - timedelta(seconds=1)
        else:
            end = _floor_minute(now) - timedelta(seconds=1)       # never the in-progress minute
        end = min(end, session.close_utc - timedelta(seconds=1))
        starts = []
        for sym in self.symbols:
            last = self.store.last_bar(sym, self.feed)
            if last and last["session_date"] == session.date.isoformat():
                starts.append(st.parse(last["t_utc"]) + timedelta(minutes=1))
            else:
                starts.append(session.open_utc)
        return min(starts), end

    def _poll(self, session, now: datetime, catchup: bool = False) -> None:
        start, end = self._window(session, now)
        if st.session_date_et(start) <= st.RESERVED_END:     # defence in depth
            self._set("refused", "request window touches the reserved research periods; not requested")
            return
        if start > end:
            self.next_poll = now + timedelta(seconds=self.poll_seconds)
            if catchup:
                self.catchup_done.add(session.date)
            self._set("running", "nothing new to request yet", next_poll_utc=st.iso(self.next_poll))
            return
        from trading.alpaca_client import AlpacaAccessError, MissingCredentials
        import requests
        try:
            if self.client is None:
                self.client = self.client_factory(self._sleep_with_heartbeat)
            resp = self.client.get_bars_multi(self.symbols, "1Min", st.iso(start), st.iso(end), self.feed, "raw")
        except _StopRequested:
            self.stopping = True
            return
        except MissingCredentials as exc:
            return self._fail("error", f"Alpaca credentials missing: {exc}", NO_CREDENTIALS_WAIT)
        except AlpacaAccessError as exc:
            if exc.status_code in (401, 403):
                return self._fail("error", f"access refused (HTTP {exc.status_code}) for feed {self.feed}: {exc}. "
                                           "The feed is not switched automatically.", ACCESS_REFUSED_WAIT)
            if exc.status_code == 429 or exc.status_code >= 500:
                return self._fail("disconnected", f"provider error HTTP {exc.status_code}: {exc}")
            return self._fail("error", f"request rejected HTTP {exc.status_code}: {exc}", ACCESS_REFUSED_WAIT)
        except (requests.RequestException, OSError) as exc:
            return self._fail("disconnected", f"connection failed: {type(exc).__name__}: {exc}")
        received = self.clock()
        totals = {"new": 0, "duplicates": 0, "reserved_discarded": 0}
        for sym in self.symbols:
            res = self.store.insert_bars(sym, self.feed, resp["bars"].get(sym, []), received)
            for k in totals:
                totals[k] += res[k]
        self.failures, self.backoff_until = 0, None
        self.next_poll = received + timedelta(seconds=self.poll_seconds)
        if catchup:
            self.catchup_done.add(session.date)
        self.store.bump(polls=1, requests=resp.get("pages", 1), bars_inserted=totals["new"],
                        duplicates_ignored=totals["duplicates"], reserved_discarded=totals["reserved_discarded"])
        what = "catch-up after the close" if catchup else "poll"
        self._set("running", f"{what} at {st.iso(received)}: {totals['new']} new bar(s), "
                             f"{totals['duplicates']} duplicate(s) ignored",
                  last_poll_utc=st.iso(received), last_success_utc=st.iso(received),
                  next_poll_utc=st.iso(self.next_poll), consecutive_failures=0, backoff_until_utc=None)

    def _fail(self, state: str, message: str, wait: float | None = None) -> None:
        now = self.clock()
        self.failures += 1
        delay = wait if wait is not None else BACKOFF[min(self.failures - 1, len(BACKOFF) - 1)]
        self.backoff_until = now + timedelta(seconds=delay)
        if state == "disconnected":
            self.client = None                         # reconnect with a fresh session next time
        self.store.event("error", state, message, now)
        self._set(state, f"{message} (retry in {int(delay)} s; failure {self.failures})",
                  last_poll_utc=st.iso(now), consecutive_failures=self.failures,
                  backoff_until_utc=st.iso(self.backoff_until), next_poll_utc=st.iso(self.backoff_until))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m trading.monitor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the worker in this process (normally started by the dashboard)")
    r.add_argument("--symbols", default=",".join(st.DEFAULT_SYMBOLS))
    r.add_argument("--feed", choices=list(st.FEEDS), default="iex")
    r.add_argument("--poll", type=int, default=st.POLL_SECONDS)
    for name in ("start", "pause", "stop", "status"):
        sub.add_parser(name)
    args = ap.parse_args(argv)
    store = st.MonitorStore()
    try:
        if args.cmd == "run":
            if args.poll < 15:
                print("poll interval below 15 s is not allowed")
                return 2
            w = Worker(store, symbols=[s.strip().upper() for s in args.symbols.split(",") if s.strip()],
                       feed=args.feed, poll_seconds=args.poll)
            return w.run()
        if args.cmd == "status":
            import json
            print(json.dumps(store.status(), indent=2, default=str))
            return 0
        from trading.monitor import control
        if args.cmd == "start":
            print(control.start(store, by="command line"))
        elif args.cmd == "pause":
            store.set_desired("paused", "command line")
            print("paused: the worker keeps running but fetches nothing")
        else:
            store.set_desired("stopped", "command line")
            print("stop requested: the worker exits within about a second")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
