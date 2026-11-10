"""Market readiness: deterministic checks over real records, a session reliability summary, and a
persistent, deduplicated incident history. No broker code, no credentials (the dashboard uses it).

Statuses: PASS, WARNING, FAIL, UNKNOWN. Missing evidence is UNKNOWN, never PASS. A closed market is an
expected state, not a failure. Each check carries the time it was performed; the latest result per
check is stored in `readiness` (data/monitoring/monitor.sqlite).

Incidents (table `incidents`): worker stopped unexpectedly, heartbeat stale, provider access refused,
storage failure. One open incident per kind (repeats only update last_seen and the observation count).
"Acknowledged" means the owner has seen it; only the condition clearing makes it "resolved"
(recorded as "service recovered").
"""

import json
import os
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading.monitor import store as st

PASS, WARNING, FAIL, UNKNOWN = "PASS", "WARNING", "FAIL", "UNKNOWN"
HEARTBEAT_WARN_S = st.HEARTBEAT_DEAD_S          # 20 s: the existing "not running" rule
MIN_FREE_BYTES = 1_000_000_000                  # same floor as the dry run (docs/DRY_RUN_ACCEPTANCE.md)
CROSS_CHECK_MAX_AGE = timedelta(days=7)
PROCESS_CACHE_S = 30
QUALIFY_TARGET = 5                              # docs/MONITORING.md: 5 consecutive sessions, each FINALIZED
                                                # or INCOMPLETE with a stated reason
SERVER_INFO: dict = {}                          # set by the dashboard server at start-up

SCHEMA = """
CREATE TABLE IF NOT EXISTS readiness (
  check_id TEXT PRIMARY KEY, status TEXT, summary TEXT, detail_json TEXT, checked_utc TEXT, changed_utc TEXT);
CREATE TABLE IF NOT EXISTS incidents (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, state TEXT, opened_utc TEXT, last_seen_utc TEXT,
  observations INTEGER DEFAULT 1, detail TEXT, recovery TEXT, acknowledged_utc TEXT, acknowledged_by TEXT,
  resolved_utc TEXT, resolution TEXT);
CREATE TABLE IF NOT EXISTS readiness_probe (id INTEGER PRIMARY KEY CHECK (id = 1), token TEXT, ts_utc TEXT);
CREATE TABLE IF NOT EXISTS server_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, pid INTEGER, port INTEGER, started_utc TEXT, last_alive_utc TEXT,
  stopped_utc TEXT, exit_reason TEXT, code_version TEXT);
"""


# ---------------------------------------------------------------- city-server lifecycle (evidence for outages)

def server_started(store, pid: int, port: int, code_version: str | None, now: datetime | None = None) -> int:
    ensure_schema(store)
    t = st.iso(now or st.now_utc())
    cur = store.db.execute("INSERT INTO server_runs (pid, port, started_utc, last_alive_utc, code_version) VALUES (?,?,?,?,?)",
                           (pid, port, t, t, code_version))
    store.db.execute("INSERT INTO events (ts_utc, level, kind, message) VALUES (?, 'info', 'server', ?)",
                     (t, f"city server started (pid {pid}, port {port})"))
    store.db.commit()
    return cur.lastrowid


def server_alive(store, run_id: int, now: datetime | None = None) -> None:
    store.db.execute("UPDATE server_runs SET last_alive_utc=? WHERE id=?", (st.iso(now or st.now_utc()), run_id))
    store.db.commit()


def server_stopped(store, run_id: int, reason: str, now: datetime | None = None) -> None:
    t = st.iso(now or st.now_utc())
    store.db.execute("UPDATE server_runs SET stopped_utc=?, last_alive_utc=?, exit_reason=? WHERE id=?", (t, t, reason, run_id))
    store.db.execute("INSERT INTO events (ts_utc, level, kind, message) VALUES (?, 'info', 'server', ?)",
                     (t, f"city server stopped ({reason})"))
    store.db.commit()


def server_runs(store, limit: int = 20) -> list[dict]:
    """Newest first. A row with no stopped_utc whose process is gone ended without a clean stop (unknown cause)."""
    ensure_schema(store)
    return [dict(r) for r in store.db.execute("SELECT * FROM server_runs ORDER BY id DESC LIMIT ?", (limit,))]

RECOVERY = {
    "worker_stopped_unexpectedly": (
        "The monitoring worker ended without a stop request (crash, app closed, sleep or restart). While the city "
        "server runs with desired state 'running', its supervisor relaunches the worker within about 15-20 s (at "
        "most 6 launches per hour). If it does not come back: Market monitor > Start, or "
        "`.venv\\Scripts\\python -m trading.monitor start`. Details: data/monitoring/worker.log."),
    "heartbeat_stale": (
        "The worker process exists but has not written a heartbeat. It may be frozen, or the computer was asleep. "
        "Wait a minute; if it persists, use Market monitor > Stop, then Start."),
    "access_refused": (
        "Alpaca refused a request (HTTP 401/403). Check that your paper keys are set in your Windows environment or "
        "in .env (never paste them in chat). The free plan refuses recent SIP data by design. The worker retries "
        "later and never switches feed by itself."),
    "storage_failure": (
        "The monitoring database could not be read or written. Check free disk space, close programs that may lock "
        "data/monitoring/monitor.sqlite, and check OneDrive sync (the project folder is inside OneDrive)."),
}

_proc_cache: dict = {"t": 0.0, "pids": None}
_pending_incidents: list = []                   # storage incidents seen while the database was unwritable


def ensure_schema(store) -> None:
    store.db.executescript(SCHEMA)
    store.db.commit()


# ---------------------------------------------------------------- system facts (injectable)

def group_worker_trees(rows: list[tuple[int, int]]) -> list[list[int]]:
    """(pid, parent pid) rows of matching processes -> one list per worker. A venv's python.exe is a
    launcher that starts the real interpreter as a child with the same command line, so a parent and
    child that both match are ONE worker, not a duplicate."""
    pids = {p for p, _ in rows}
    parent = dict(rows)
    trees: dict[int, list[int]] = {}
    for p in sorted(pids):
        root = p
        while parent.get(root) in pids:
            root = parent[root]
        trees.setdefault(root, []).append(p)
    return [sorted(v) for _, v in sorted(trees.items())]


def worker_processes() -> list[list[int]] | None:
    """Worker process trees (each a list of PIDs: launcher and interpreter); None if undeterminable."""
    return process_trees("-m trading.monitor run")


def runner_processes() -> list[list[int]] | None:
    """Dry-run runner process trees; None if undeterminable."""
    return process_trees("-m trading.operations run")


def process_trees(pattern: str) -> list[list[int]] | None:
    if os.name != "nt":
        return None
    cache = _proc_cache.setdefault("by", {})
    hit = cache.get(pattern)
    if hit and time.monotonic() - hit[0] < PROCESS_CACHE_S:
        return hit[1]
    cmd = ("Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
           f"Where-Object {{ $_.CommandLine -like '*{pattern}*' }} | "
           "ForEach-Object { \"$($_.ProcessId) $($_.ParentProcessId)\" }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True,
                             text=True, timeout=15, creationflags=0x08000000)
        if out.returncode != 0:
            return None
        rows = [tuple(int(x) for x in ln.split()) for ln in out.stdout.splitlines() if len(ln.split()) == 2]
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    trees = group_worker_trees(rows)
    cache[pattern] = (time.monotonic(), trees)
    return trees


RUNNER_STATUS_STALE_S = 60       # the runner refreshes its status every 15 s (heartbeat)
RUNNER_STARTUP_LIMIT_S = 120     # start-up (loading code, lock, records) normally takes a few seconds


def runner_check(now: datetime, procs=None, runtime_dir=None, plan_for=None) -> dict:
    """Is the dry-run runner healthy? A stalled or missing runner during the session is FAIL, never 'ready'."""
    from trading.operations import paths, progress
    from trading.operations import schedule as osc
    label = "Dry-run runner (operations)"
    plan = (plan_for or osc.plan_for)(osc.et_date(now))
    try:
        rd = runtime_dir or paths.runtime_dir()
    except paths.RuntimeDirRefused as exc:
        return _c("runner", label, FAIL, f"runtime folder refused: {exc}", now)
    status, startup = progress.read(rd / progress.STATUS_NAME), progress.read(rd / progress.STARTUP_NAME)
    trees = (procs or runner_processes)()
    pids = [p for t in (trees or []) for p in t]
    age = lambda d: None if not d or not d.get("ts_utc") else (now - datetime.fromisoformat(d["ts_utc"])).total_seconds()
    detail = {"process_trees": trees, "runner_status": status, "runner_startup": startup}
    if not plan.trading_day:
        return _c("runner", label, PASS, "no session today; the dry run is not required", now, **detail)
    if now >= plan.report_utc:
        done = status and status.get("session_date") == str(plan.date) and status.get("stage") == "exited" \
            and status.get("exit_reason") == "completed"
        return _c("runner", label, PASS if done else WARNING,
                  "today's dry run completed and wrote its report" if done
                  else "today's dry run did not complete (see Operations); not required again until the next session",
                  now, **detail)
    if trees is None:
        return _c("runner", label, UNKNOWN, "process list unavailable", now, **detail)
    if not trees:
        if now < plan.preopen_utc:
            return _c("runner", label, WARNING, "not started yet: start it before 09:25 ET", now, **detail)
        return _c("runner", label, FAIL, "no dry-run runner is running during today's session window", now, **detail)
    if len(trees) > 1:
        return _c("runner", label, FAIL, f"{len(trees)} runner processes found ({trees}); expected one", now, **detail)
    fresh = status and status.get("pid") in pids and status.get("stage") == "running" \
        and age(status) is not None and age(status) <= RUNNER_STATUS_STALE_S
    if fresh:
        return _c("runner", label, PASS, f"running (pid {status['pid']}, phase {status.get('phase')}, status "
                  f"{int(age(status))} s old, {status.get('decisions_this_run', 0)} decision(s) this run)", now, **detail)
    if startup and startup.get("pid") in pids and startup.get("stage") == "starting" \
            and (age(startup) or 0) <= RUNNER_STARTUP_LIMIT_S:
        return _c("runner", label, WARNING, f"starting: {startup.get('step')}", now, **detail)
    where = (f"last start-up step '{startup.get('step')}' ({int(age(startup) or 0)} s ago)"
             if startup and startup.get("pid") in pids else "no start-up step recorded by this process")
    return _c("runner", label, FAIL, f"STALLED: runner process {trees[0]} is alive but has not reported for over "
              f"{RUNNER_STATUS_STALE_S} s; {where}. Stack traces, if any: runner_faults.log", now, **detail)


def pid_alive(pid: int | None) -> bool | None:
    """True/False via the Windows process table (never sends a signal); None if unknown."""
    if not pid:
        return None
    if os.name != "nt":
        return None
    import ctypes
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, int(pid))          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        return bool(ok) and code.value == 259           # STILL_ACTIVE
    finally:
        k.CloseHandle(h)


def git_version() -> str | None:
    from trading.monitor.worker import code_version
    v = code_version()
    return None if v == "unknown" else v


def operations_cross_check() -> dict | None:
    """Latest broker clock/calendar cross-check recorded by the dry run (read-only), if any."""
    try:
        from trading.operations import paths
        db = paths.db_path()
        if not db.exists():
            return None
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=2)
        try:
            r = con.execute("SELECT ts_utc, ok, detail_json FROM checks WHERE name='calendar_agreement' "
                            "ORDER BY id DESC LIMIT 1").fetchone()
        finally:
            con.close()
        return {"ts_utc": r[0], "ok": bool(r[1]), "detail": json.loads(r[2])} if r else None
    except Exception:
        return None


# ---------------------------------------------------------------- checks

def _c(cid, label, status, summary, now, **detail):
    return {"id": cid, "label": label, "status": status, "summary": summary, "checked_utc": st.iso(now), "detail": detail}


def evaluate(store, now: datetime | None = None, *, procs=worker_processes, alive_fn=pid_alive, head=git_version,
             disk_path: Path | None = None, cross_check=operations_cross_check, server_info: dict | None = None,
             runner: dict | None = None) -> list[dict]:
    now = now or st.now_utc()
    out = []
    info = SERVER_INFO if server_info is None else server_info
    if info.get("pid"):
        out.append(_c("server", "Server responding", PASS, f"answering (pid {info['pid']}, up since "
                      f"{info.get('started_utc')})", now, **info))
    else:
        out.append(_c("server", "Server responding", UNKNOWN, "not evaluated inside the city server", now))

    # Database first: everything else reads it.
    db_ok = True
    try:
        ensure_schema(store)
        token = f"{now.timestamp()}-{os.getpid()}"
        store.db.execute("INSERT OR REPLACE INTO readiness_probe (id, token, ts_utc) VALUES (1, ?, ?)", (token, st.iso(now)))
        store.db.commit()
        back = store.db.execute("SELECT token FROM readiness_probe WHERE id=1").fetchone()[0]
        db_ok = back == token
        out.append(_c("database", "Monitoring database readable and writable", PASS if db_ok else FAIL,
                      "write and read-back succeeded" if db_ok else "read-back did not match the write", now))
    except sqlite3.Error as exc:
        db_ok = False
        out.append(_c("database", "Monitoring database readable and writable", FAIL,
                      f"{type(exc).__name__}: {str(exc)[:160]}", now))
    if not db_ok:
        for cid, label in (("worker_count", "Exactly one intended monitoring worker"), ("heartbeat", "Worker heartbeat"),
                           ("desired_vs_actual", "Desired vs actual worker state"),
                           ("calendar", "Exchange calendar and next session"), ("latest_data", "Latest data request"),
                           ("failures", "Backoff, refusals, unresolved failures"),
                           ("unfinished_sessions", "Unfinished sessions and pending rechecks"),
                           ("code_version", "Code version of the running service")):
            out.append(_c(cid, label, UNKNOWN, "monitoring database unavailable", now))
        out.append(_disk(disk_path or st.MONITOR_DIR, now))
        return out

    s = store.status(now)
    w, desired, mk = s["worker"], s["desired"], s["market"]
    hb_age = w.get("heartbeat_age_s")

    trees = procs()
    if trees is None:
        out.append(_c("worker_count", "Exactly one intended monitoring worker", UNKNOWN,
                      "process list unavailable", now, recorded_pid=w.get("pid")))
    else:
        intended = 1 if desired in ("running", "paused") else 0
        if len(trees) > 1:
            st_, summ = FAIL, f"{len(trees)} separate worker processes found ({trees}); expected one"
        elif len(trees) == 1 and intended == 1:
            st_ = PASS if w.get("pid") in trees[0] else WARNING
            summ = (f"one worker (pids {trees[0]}: venv launcher and interpreter)" if len(trees[0]) > 1 and st_ == PASS
                    else f"one worker (pid {trees[0][0]})" if st_ == PASS
                    else f"one worker process tree {trees[0]} but the record names pid {w.get('pid')}")
        elif len(trees) == 0 and intended == 0:
            st_, summ = WARNING, "no worker: monitoring is stopped by request (Start it before the open)"
        elif len(trees) == 0:
            st_, summ = FAIL, f"no worker process, but the desired state is {desired}"
        else:
            st_, summ = WARNING, f"a worker process {trees[0]} runs although the desired state is {desired}"
        out.append(_c("worker_count", "Exactly one intended monitoring worker", st_, summ, now,
                      process_trees=trees, recorded_pid=w.get("pid"), desired=desired))

    if w.get("heartbeat_utc") is None:
        out.append(_c("heartbeat", "Worker heartbeat", UNKNOWN, "no heartbeat ever recorded", now))
    elif w["state"] == "stopped":
        out.append(_c("heartbeat", "Worker heartbeat", WARNING if desired != "running" else FAIL,
                      f"worker stopped ({w.get('exit_reason') or w.get('detail')}); last heartbeat {hb_age} s ago", now,
                      heartbeat_utc=w["heartbeat_utc"]))
    else:
        st_ = PASS if hb_age <= HEARTBEAT_WARN_S else FAIL
        out.append(_c("heartbeat", "Worker heartbeat", st_, f"last heartbeat {hb_age} s ago (limit {HEARTBEAT_WARN_S} s)",
                      now, heartbeat_utc=w["heartbeat_utc"]))

    eff = w["effective_state"]
    if desired == "running":
        ok_states = ("running", "market_closed", "starting")
        st_ = PASS if eff in ok_states else WARNING if eff in ("disconnected", "error", "refused") else FAIL
        summ = f"desired running, actual {eff}"
    elif desired == "paused":
        st_, summ = (WARNING, "paused by request: no data is collected") if eff == "paused" else (FAIL, f"desired paused, actual {eff}")
    else:
        st_, summ = (WARNING, "stopped by request: no data is collected") if eff in ("stopped", "not running") \
            else (FAIL, f"desired stopped, actual {eff}")
    out.append(_c("desired_vs_actual", "Desired vs actual worker state", st_, summ, now, desired=desired, actual=eff,
                  detail=w.get("detail")))

    cal = st.market_state(now)
    nxt = cal["next_open"]
    xc = cross_check()
    cal_detail = {"open": cal["open"], "reason": cal["reason"], "next_open_utc": st.iso(nxt),
                  "session_close_utc": st.iso(cal["session"].close_utc) if cal["open"] else None,
                  "early_close": bool(cal["session"].early_close) if cal["open"] else
                  (bool(_next_session(now).early_close) if _next_session(now) else None), "broker_cross_check": xc}
    if not cal["open"] and nxt is None:
        out.append(_c("calendar", "Exchange calendar and next session", FAIL, "calendar returned no upcoming session", now,
                      **cal_detail))
    else:
        when = (f"open now; closes {_et(cal['session'].close_utc)} ET" if cal["open"]
                else f"{cal['reason']}; next open {_et(nxt)} ET")
        if xc is None:
            st_, note = WARNING, "; not cross-checked against the broker clock yet (run the dry-run preflight)"
        elif not xc["ok"]:
            st_, note = FAIL, f"; the last broker cross-check ({xc['ts_utc']}) disagreed"
        elif now - st.parse(xc["ts_utc"]) > CROSS_CHECK_MAX_AGE:
            st_, note = WARNING, f"; last broker cross-check {xc['ts_utc']} is older than 7 days"
        else:
            st_, note = PASS, f"; broker cross-check agreed at {xc['ts_utc']}"
        out.append(_c("calendar", "Exchange calendar and next session", st_, when + note, now, **cal_detail))

    feed = s["config"]["feed"]
    bars = {r["symbol"]: {"last_bar_start_utc": r["last_bar_start_utc"], "freshness": r["freshness"]} for r in s["symbols"]}
    last_ok = w.get("last_success_utc")
    if not last_ok or not any(b["last_bar_start_utc"] for b in bars.values()):
        out.append(_c("latest_data", "Latest data request", UNKNOWN, "no successful request or stored bar recorded", now,
                      feed=feed, bars=bars))
    elif mk["open"]:
        fresh = [s_ for s_, b in bars.items() if b["freshness"] == "FRESH"]
        st_ = PASS if len(fresh) == len(bars) else WARNING if fresh else FAIL
        out.append(_c("latest_data", "Latest data request", st_, f"{feed}: {len(fresh)} of {len(bars)} symbols FRESH; "
                      f"last success {last_ok}", now, feed=feed, bars=bars, last_success_utc=last_ok))
    else:
        last_sess = cal["last_session"]
        newest = max(b["last_bar_start_utc"] for b in bars.values() if b["last_bar_start_utc"])
        in_last = last_sess is not None and st.session_date_et(st.parse(newest)) == last_sess.date
        out.append(_c("latest_data", "Latest data request", PASS if in_last else WARNING,
                      f"market closed (expected); {feed} newest bar {newest}"
                      + ("" if in_last else f", not from the last session ({last_sess.date if last_sess else '?'})"),
                      now, feed=feed, bars=bars, last_success_utc=last_ok))

    from trading.monitor import quality as q
    q.ensure_schema(store)
    qh = dict(store.db.execute("SELECT * FROM q_health WHERE id=1").fetchone())
    refused = "access refused" in (w.get("detail") or "") or qh.get("state") == "access_failure"
    backoff = w.get("backoff_until_utc") and st.parse(w["backoff_until_utc"]) > now
    open_inc = [i for i in incidents(store) if i["state"] != "resolved"]
    if w.get("heartbeat_utc") is None:
        st_, summ = UNKNOWN, "the worker has never run"
    elif refused:
        st_, summ = FAIL, "provider access refused (see incidents)"
    elif backoff or (w.get("consecutive_failures") or 0) > 0 or qh.get("state") == "error" or open_inc:
        st_ = WARNING
        summ = (f"{w.get('consecutive_failures') or 0} consecutive worker failure(s)"
                + (f", backing off until {w['backoff_until_utc']}" if backoff else "")
                + (f"; comparison state {qh['state']}" if qh.get("state") == "error" else "")
                + (f"; {len(open_inc)} unresolved incident(s)" if open_inc else ""))
    else:
        st_, summ = PASS, "no backoff, no refusal, no unresolved incident"
    out.append(_c("failures", "Backoff, refusals, unresolved failures", st_, summ, now,
                  consecutive_failures=w.get("consecutive_failures"), backoff_until_utc=w.get("backoff_until_utc"),
                  comparison_health={k: qh.get(k) for k in ("state", "detail", "backoff_until_utc")},
                  unresolved_incidents=len(open_inc)))

    rel = reliability_summary(store, now)
    pending = [r for r in rel["sessions"] if r["state"] in ("provisional", "in_progress")]
    if not rel["sessions"]:
        out.append(_c("unfinished_sessions", "Unfinished sessions and pending rechecks", UNKNOWN,
                      "no monitored session recorded", now))
    elif any(r["state"] == "provisional" for r in pending):
        out.append(_c("unfinished_sessions", "Unfinished sessions and pending rechecks", WARNING,
                      "pending after-close recheck: " + ", ".join(r["session_date"] for r in pending if r["state"] == "provisional")
                      + " (completes when the worker runs; within the 5-session lookback)", now,
                      pending=[r["session_date"] for r in pending]))
    else:
        out.append(_c("unfinished_sessions", "Unfinished sessions and pending rechecks", PASS,
                      "none pending" + (" (current session in progress)" if pending else ""), now))

    head_v = head()
    worker_v = (w.get("config") or {}).get("code_version")
    server_v = info.get("code_version")
    if not head_v or not worker_v:
        out.append(_c("code_version", "Code version of the running service", UNKNOWN,
                      "the running worker's version or the repository version is not available", now,
                      repository=head_v, worker=worker_v, server=server_v))
    else:
        base = lambda v: (v or "").split("+")[0]
        same = base(worker_v) == base(head_v) and (not server_v or base(server_v) == base(head_v))
        dirty = any("+dirty" in (v or "") for v in (worker_v, server_v, head_v))
        st_ = PASS if same and not dirty else WARNING
        summ = (f"worker {worker_v}, server {server_v or 'n/a'}, repository {head_v}"
                + ("" if same else "; a running process uses older code (it changes only after a restart)")
                + ("; uncommitted changes exist, so the exact running code is not verifiable" if dirty else ""))
        out.append(_c("code_version", "Code version of the running service", st_, summ, now,
                      repository=head_v, worker=worker_v, server=server_v))

    out.append(_disk(disk_path or st.MONITOR_DIR, now))
    try:
        out.append(runner_check(now, **(runner or {})))
    except Exception as exc:                      # never let this check break the panel
        out.append(_c("runner", "Dry-run runner (operations)", UNKNOWN, f"could not evaluate: {type(exc).__name__}", now))
    return out


def _disk(path: Path, now):
    try:
        free = shutil.disk_usage(path).free
        return _c("disk", "Available disk space", PASS if free >= MIN_FREE_BYTES else FAIL,
                  f"{free / 1e9:.1f} GB free (minimum {MIN_FREE_BYTES / 1e9:.0f} GB)", now, free_bytes=free, path=str(path))
    except OSError as exc:
        return _c("disk", "Available disk space", UNKNOWN, f"could not read disk usage: {exc}", now)


def _next_session(now):
    from trading.sessions import sessions_between
    today = now.astimezone(timezone.utc).date()
    for s_ in sessions_between(today, today + timedelta(days=10)):
        if s_.open_utc > now:
            return s_
    return None


def _et(t):
    return t.astimezone(st._tz()).strftime("%a %Y-%m-%d %H:%M") if t else "unknown"


# ---------------------------------------------------------------- reliability (existing criterion only)

def _agg(fn, values):
    """fn(values), or None (unknown) when there are no values or any value is unavailable. Unknown
    evidence stays unknown: it is never turned into zero or into complete coverage."""
    vals = list(values)
    if not vals or any(v is None for v in vals):
        return None
    return fn(vals)

def reliability_summary(store, now: datetime | None = None) -> dict:
    """Per monitored session, from the stored evidence reports. Qualification uses ONLY the existing written
    criterion (docs/MONITORING.md): FINALIZED, or INCOMPLETE with a stated reason, for 5 consecutive scheduled
    sessions. No capture-quality threshold exists; none is invented here."""
    from trading.monitor import reliability as rl
    from trading.sessions import sessions_between
    now = now or st.now_utc()
    rows = rl.sessions_overview(store, now, limit=60)
    by_date = {r["session_date"]: r for r in rows}
    out = []
    if by_date:
        first = min(by_date)
        last_done = st.market_state(now)["last_session"]
        end = last_done.date if last_done else None
        sched = sessions_between(datetime.fromisoformat(first).date(), end) if end else []
        cur = st.market_state(now)
        dates = [s_.date.isoformat() for s_ in sched]
        if cur["open"] and cur["session"].date.isoformat() not in dates:
            dates.append(cur["session"].date.isoformat())
        for d in dates:
            r = by_date.get(d)
            if r is None:
                out.append({"session_date": d, "state": "not_monitored", "qualifies": False,
                            "why": "the live monitor did not run during this scheduled session (no evidence)"})
                continue
            rep = rl.stored_or_current(store, d, now)
            ev = rep.get("evidence", {})
            sipc, iexr = ev.get("sip_comparison") or {}, ev.get("iex_revisions") or {}
            anomalies = _agg(sum, [(v.get("categories") or {}).get(rl.CATEGORY_LABELS[k])
                                   for v in sipc.values() for k in ("unresolved_anomaly", "structural_defect")])
            revisions = _agg(sum, [v.get(k) for v in iexr.values() for k in ("live_differs_from_refetch", "later_iex_revisions")]
                             + [v.get("sip_revisions") for v in sipc.values()]) if (sipc and iexr) else None
            sched_min, compared = r["scheduled_minutes"], r["compared_min"]
            outstanding = None if sched_min is None or compared is None else max(0, sched_min - compared)
            state = r["state"]
            if state == "finalized":
                q_, why = True, "FINALIZED: compared through the close and re-observed after the close"
            elif state == "incomplete":
                q_ = bool(r.get("detail"))
                why = f"INCOMPLETE with stated reason: {r['detail']}" if q_ else "INCOMPLETE without a stated reason"
            elif state == "provisional":
                q_, why = False, "PROVISIONAL: comparison or after-close re-observation still pending"
            else:
                q_, why = False, "IN PROGRESS: the session has not finished"
            lb = r["live_by_symbol"]
            out.append({"session_date": d, "state": state, "qualifies": q_, "why": why, "early_close": r["early_close"],
                        "scheduled_minutes": sched_min,
                        # Per-symbol counts can be unavailable (None), e.g. "missing" while a session is in
                        # progress. Any unavailable value, or no symbols at all, makes the aggregate unknown (None).
                        "live_on_time_min": _agg(min, [v.get("on_time") for v in lb.values()]),
                        "live_late_recovery_min": _agg(max, [v.get("late_catch_up") for v in lb.values()]),
                        "live_missing_max": _agg(max, [v.get("missing") for v in lb.values()]),
                        "downtime_minutes": r["downtime_minutes"], "unplanned_downtime_minutes": r["unplanned_downtime_minutes"],
                        "restarts": ev.get("operations", {}).get("restarts_during_session"),
                        "request_failures": r["request_failures"], "access_refusals": r["access_refusals"],
                        "comparisons_outstanding_min": outstanding, "anomalies": anomalies, "revisions": revisions,
                        "report_versions": r["report_versions"]})
    streak = best = 0
    for r in out:
        if r["state"] == "in_progress":
            continue
        streak = streak + 1 if r["qualifies"] else 0
        best = max(best, streak)
    return {"name": "Report completion",
            "criterion": f"{QUALIFY_TARGET} consecutive scheduled sessions, each FINALIZED or INCOMPLETE with a stated "
                         "reason (docs/MONITORING.md checklist; historical rule, unchanged). This counts completed "
                         "evidence reports, not live-capture reliability.",
            "reliability_gate": "PROPOSED, not active: docs/RELIABILITY_GATE_PROPOSAL.md (awaiting owner approval)",
            "target": QUALIFY_TARGET, "current_consecutive": streak, "best_consecutive": best,
            "qualifying_total": sum(1 for r in out if r["qualifies"]),
            "gap": ("This criterion counts a session as qualifying even with large live-capture gaps or downtime. No "
                    "capture-quality threshold (for example minimum on-time share or maximum unplanned downtime) is "
                    "defined; none is applied until the owner sets one."),
            "sessions": out}


# ---------------------------------------------------------------- incidents

def incidents(store, limit: int = 50) -> list[dict]:
    ensure_schema(store)
    return [dict(r) for r in store.db.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,))]


def _conditions(store, checks: list[dict], now, alive_fn) -> dict:
    by = {c["id"]: c for c in checks}
    cond = {k: None for k in RECOVERY}
    if by["database"]["status"] == FAIL:
        cond["storage_failure"] = by["database"]["summary"]
        return cond
    s = store.status(now)
    w, desired = s["worker"], s["desired"]
    if desired == "running" and w.get("heartbeat_utc") and not w["alive"] and w["state"] != "stopped":
        alive = alive_fn(w.get("pid"))
        if alive is False:
            cond["worker_stopped_unexpectedly"] = (f"worker pid {w.get('pid')} is gone without a stop request; last "
                                                   f"heartbeat {w.get('heartbeat_utc')}")
        else:
            cond["heartbeat_stale"] = (f"no heartbeat for {w.get('heartbeat_age_s')} s (pid {w.get('pid')} "
                                       f"{'still exists' if alive else 'state unknown'})")
    if by["failures"]["status"] == FAIL:
        cond["access_refused"] = (w.get("detail") or "access refused")[:300]
    return cond


def record(store, checks: list[dict], now: datetime | None = None, alive_fn=pid_alive) -> None:
    """Store the latest result per check and open/update/resolve incidents. Safe to call repeatedly."""
    now = now or st.now_utc()
    try:
        ensure_schema(store)
        cond = _conditions(store, checks, now, alive_fn)
    except sqlite3.Error as exc:
        _pending_incidents.append({"kind": "storage_failure", "opened_utc": st.iso(now),
                                   "detail": f"{type(exc).__name__}: {str(exc)[:200]}"})
        return
    if cond["storage_failure"]:
        _pending_incidents.append({"kind": "storage_failure", "opened_utc": st.iso(now), "detail": cond["storage_failure"]})
        return
    try:
        for c in checks:
            prev = store.db.execute("SELECT status, changed_utc FROM readiness WHERE check_id=?", (c["id"],)).fetchone()
            changed = c["checked_utc"] if (prev is None or prev[0] != c["status"]) else prev[1]
            store.db.execute("INSERT OR REPLACE INTO readiness VALUES (?,?,?,?,?,?)",
                             (c["id"], c["status"], c["summary"], json.dumps(c["detail"], default=str), c["checked_utc"], changed))
        for p in _pending_incidents:                  # storage problems seen while the database was failing
            if not store.db.execute("SELECT 1 FROM incidents WHERE kind='storage_failure' AND opened_utc=?",
                                    (p["opened_utc"],)).fetchone():
                store.db.execute("INSERT INTO incidents (kind, state, opened_utc, last_seen_utc, detail, recovery) "
                                 "VALUES ('storage_failure', 'open', ?, ?, ?, ?)",
                                 (p["opened_utc"], p["opened_utc"], p["detail"], RECOVERY["storage_failure"]))
        _pending_incidents.clear()
        for kind, active in cond.items():
            row = store.db.execute("SELECT id FROM incidents WHERE kind=? AND state != 'resolved' ORDER BY id DESC LIMIT 1",
                                   (kind,)).fetchone()
            if active and row is None:
                store.db.execute("INSERT INTO incidents (kind, state, opened_utc, last_seen_utc, detail, recovery) "
                                 "VALUES (?, 'open', ?, ?, ?, ?)", (kind, st.iso(now), st.iso(now), active, RECOVERY[kind]))
                store.db.execute("INSERT INTO events (ts_utc, level, kind, message) VALUES (?, 'error', 'incident', ?)",
                                 (st.iso(now), f"incident opened: {kind}: {active}"[:500]))
            elif active:
                store.db.execute("UPDATE incidents SET last_seen_utc=?, observations=observations+1, detail=? WHERE id=?",
                                 (st.iso(now), active, row[0]))
            elif row is not None:
                store.db.execute("UPDATE incidents SET state='resolved', resolved_utc=?, resolution=? WHERE id=?",
                                 (st.iso(now), "condition cleared: service recovered", row[0]))
                store.db.execute("INSERT INTO events (ts_utc, level, kind, message) VALUES (?, 'info', 'incident', ?)",
                                 (st.iso(now), f"service recovered: {kind} resolved"))
        store.db.commit()
    except sqlite3.Error as exc:
        _pending_incidents.append({"kind": "storage_failure", "opened_utc": st.iso(now),
                                   "detail": f"{type(exc).__name__}: {str(exc)[:200]}"})


def acknowledge(store, incident_id: int, by: str, now: datetime | None = None) -> str:
    ensure_schema(store)
    row = store.db.execute("SELECT state FROM incidents WHERE id=?", (incident_id,)).fetchone()
    if row is None:
        raise KeyError("unknown incident")
    if row[0] != "open":
        return f"incident {incident_id} is {row[0]}; nothing changed"
    store.db.execute("UPDATE incidents SET state='acknowledged', acknowledged_utc=?, acknowledged_by=? WHERE id=?",
                     (st.iso(now or st.now_utc()), by, incident_id))
    store.db.commit()
    return f"incident {incident_id} acknowledged (it stays unresolved until the condition clears)"


def snapshot(store, now: datetime | None = None, **kw) -> dict:
    """What the readiness panel shows: evaluated now, recorded, then read back from the records."""
    now = now or st.now_utc()
    ensure_schema(store)
    checks = evaluate(store, now, **{k: v for k, v in kw.items() if k != "alive_fn"})
    record(store, checks, now, alive_fn=kw.get("alive_fn", pid_alive))
    try:
        stored = {r["check_id"]: dict(r) for r in store.db.execute("SELECT * FROM readiness")}
        incs = incidents(store)
        rel = reliability_summary(store, now)
    except sqlite3.Error:
        stored, incs, rel = {}, [], None
    for c in checks:
        c["changed_utc"] = (stored.get(c["id"]) or {}).get("changed_utc")
        c["recorded"] = c["id"] in stored and stored[c["id"]]["checked_utc"] == c["checked_utc"]
    counts = {k: sum(1 for c in checks if c["status"] == k) for k in (PASS, WARNING, FAIL, UNKNOWN)}
    overall = FAIL if counts[FAIL] else UNKNOWN if counts[UNKNOWN] else WARNING if counts[WARNING] else PASS
    return {"label": "MARKET READINESS · real records · deterministic checks · no orders exist",
            "evaluated_utc": st.iso(now), "overall": overall, "counts": counts, "checks": checks,
            "reliability": rel, "incidents": incs, "pending_storage_incidents": list(_pending_incidents),
            "operating_note": ("Monitoring runs only while this computer is on and the city server is running. "
                               "There is no Windows startup task and no always-on service.")}
