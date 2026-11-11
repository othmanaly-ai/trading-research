"""DRY_RUN session runner: one process per trading day, started manually (owner decision 2026-11-09).

It follows the XNYS session clock, runs the pre-open checks, records one entry-permission decision per
minute (always denied in DRY_RUN, with every reason), checks the broker clock every 30 minutes,
verifies at the closing phase, by read-only broker evidence (positions and open orders), that the paper
account holds no exposure, and writes the after-close report. It contains no order code. Past decisions are never replayed: a minute the runner was not awake for stays missing.
Ctrl+C stops it cleanly (the session is then INTERRUPTED).
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from trading.operations import ENVIRONMENT, approvals, checks, data_health, gate, killswitch, paths, report
from trading.operations import schedule as sc

# The monitoring store's own path constant: read for health (worker alive, freshness) only, never for signals.
from trading.monitor.store import DB_PATH as MONITOR_DB  # noqa: E402
HEARTBEAT_S = 15
CLOCK_CHECK_EVERY_S = report.CLOCK_CHECK_EVERY_S
CLOCK_VALID_S = CLOCK_CHECK_EVERY_S + 300
JUMP_S = 30
FINGERPRINT_FILES = ("trading/sessions.py", "trading/safety.py", "trading/alpaca_client.py",
                     "config/approved_strategies.json")


def code_fingerprint(root: Path = paths.PROJECT_ROOT) -> str:
    h = hashlib.sha256()
    files = sorted((root / "trading" / "operations").glob("*.py")) + [root / f for f in FINGERPRINT_FILES]
    for f in files:
        h.update(f.relative_to(root).as_posix().encode())
        h.update(f.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:16]


def committed_code_state(root: Path = paths.PROJECT_ROOT) -> dict:
    """The git commit the run uses, and whether the operations code is exactly that commit's.

    Only the fingerprinted operations files are compared (unrelated uncommitted work elsewhere in
    the tree does not matter). Untracked or modified files there mean the evidence is not tied to a
    commit (INCOMPLETE I5)."""
    scope = ["trading/operations", *FINGERPRINT_FILES]
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
        st = subprocess.run(["git", "status", "--porcelain", "--", *scope], cwd=root, capture_output=True, text=True)
        changed = [ln[3:] for ln in st.stdout.splitlines() if ln.strip() and "__pycache__" not in ln]
        ok = bool(head) and st.returncode == 0 and not changed
        return {"commit": head or None, "operations_code_committed": ok, "uncommitted_paths": changed[:20]}
    except OSError as exc:
        return {"commit": None, "operations_code_committed": False, "uncommitted_paths": [f"git unavailable: {exc}"]}


def code_version(state: dict) -> str:
    c = (state.get("commit") or "unknown")[:12]
    return c if state.get("operations_code_committed") else c + "+uncommitted-operations-code"


def default_client_factory():
    from trading.alpaca_client import ReadOnlyAlpacaClient, load_credentials
    key, secret = load_credentials()
    return ReadOnlyAlpacaClient(key, secret)


class Runner:
    def __init__(self, store, client_factory=default_client_factory, monitor_db: Path = MONITOR_DB,
                 approvals_path: Path = approvals.APPROVALS_PATH, now_fn=None, sleep=time.sleep, mono=time.monotonic,
                 environment: str = ENVIRONMENT, reports_dir: Path | None = None, echo=print,
                 status_path: Path | None = None, on_tick=None):
        self.store, self.client_factory, self.monitor_db = store, client_factory, monitor_db
        self.approvals_path, self.environment = approvals_path, environment
        self.now = now_fn or (lambda: datetime.now(timezone.utc))
        self.sleep, self.mono, self.echo = sleep, mono, echo
        self.status_path, self.on_tick = status_path, on_tick or (lambda: None)
        self.decisions = 0
        self.reports_dir = reports_dir
        self.run_id = self.d = None
        self.last_clock = None              # (measured_at, ok): only real measurements
        self.last_clock_attempt = None      # when the last broker check was attempted (schedules the next)
        self.records_ok = True

    # ---------------------------------------------------------------- helpers
    def _event(self, level, kind, msg):
        self.store.event(self.run_id, self.d, self.now().isoformat(), level, kind, msg)
        if level in ("info", "warn", "error"):
            self.echo(f"[{self.now().astimezone(sc.ET):%H:%M:%S} ET] {level.upper()} {msg}")

    def _record_checks(self, stage, items):
        ts = self.now().isoformat()
        for name, ok, dep, detail in items:
            self.store.add_check(self.run_id, self.d, ts, stage, name, ok, dep, detail)
        bad = [n for n, ok, _, _ in items if not ok]
        self._event("info" if not bad else "warn", "checks", f"{stage} checks: {len(items) - len(bad)} ok"
                    + (f", FAILED: {', '.join(bad)}" if bad else ""))
        return bad

    def _preflight(self, stage, plan):
        self.last_clock_attempt = self.now()
        items = checks.local_checks(self.store, self.approvals_path, self.monitor_db, self.now())
        bitems, clock = checks.broker_checks(self.client_factory, plan, self.now, self._session_account_ref())
        if clock is not None:
            self.last_clock = (self.now(), clock["ok"])
        return self._record_checks(stage, items + bitems)

    def _session_account_ref(self):
        """The account reference first observed by broker evidence this session (None if none yet)."""
        for c in self.store.checks_for(self.d):
            if c["name"] == "exposure_none":
                ref = json.loads(c["detail_json"] or "{}").get("account_ref")
                if ref:
                    return ref
        return None

    def _closing_exposure(self):
        """Broker evidence that the account holds no positions and no open orders. Never assumed."""
        from trading.operations import broker_checks as bc
        try:
            client = self.client_factory()
        except Exception as exc:                       # missing credentials or anything else: unverifiable
            return False, {"verified": False, "status": bc.UNVERIFIABLE, "observed_from_utc": self.now().isoformat(),
                           "reason": f"broker client unavailable: {type(exc).__name__}"}
        return bc.exposure_check(client, self.now, self._session_account_ref())

    def _periodic(self, plan):
        self.last_clock_attempt = self.now()           # schedules the next attempt even if this one fails
        bitems, clock = checks.broker_checks(self.client_factory, plan, self.now)
        keep = [i for i in bitems if i[0] in ("credentials_present", "broker_clock_skew", "calendar_agreement")]
        if not any(i[0] == "broker_clock_skew" for i in keep):
            keep.append(("broker_clock_skew", False, True, {"error": "not performed (credentials unavailable)"}))
        if clock is not None:                          # only a measurement updates the verified state
            self.last_clock = (self.now(), clock["ok"])
        self._record_checks("periodic", keep)

    def _decide(self, plan, minute, now):
        appr = approvals.load_approval(self.approvals_path)
        ksw = killswitch.state()
        health = data_health.read(now, self.monitor_db)
        clock_ok = None
        if self.last_clock and (now - self.last_clock[0]).total_seconds() <= CLOCK_VALID_S:
            clock_ok = self.last_clock[1]
        inp = gate.GateInputs(environment=self.environment, approval=appr, phase=sc.phase_at(plan, now),
                              decision_minute_utc=minute, now_utc=now, data=health, risk_reasons=None,
                              kill_switch=ksw, clock_ok=clock_ok, records_ok=self.records_ok)
        perm = gate.evaluate(inp)
        inputs = {"approval": appr.summary(), "approvals_sha256": appr.file_sha256, "kill_switch": {"on": ksw.on, "reason": ksw.reason},
                  "data": health.as_dict(), "clock_ok": clock_ok, "phase": inp.phase, "environment": self.environment}
        self.store.add_decision(self.d, minute.isoformat(), self.run_id, now.isoformat(), inp.phase, perm.allowed,
                                perm.reasons, inputs)
        return perm

    def _status(self, stage, **extra):
        if self.status_path:
            from trading.operations import progress
            progress.record(self.status_path, stage, run_id=self.run_id, session_date=self.d,
                            decisions_this_run=self.decisions, **extra)

    def _write_report(self, now):
        from datetime import date
        rep = report.classify(self.store, date.fromisoformat(self.d), now)
        self.store.save_report(self.d, rep["classification"], rep)
        if self.reports_dir:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            (self.reports_dir / f"{self.d}.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
        return rep

    # ---------------------------------------------------------------- main loop
    def run(self) -> int:
        now = self.now()
        d = sc.et_date(now)
        plan = sc.plan_for(d)
        self.d = str(d)
        self.run_id = f"{now:%Y%m%dT%H%M%S}Z-{os.getpid()}"
        start_class = sc.start_classification(plan, now)
        git_state = committed_code_state()
        cfg = {"plan": plan.as_dict(), "heartbeat_s": HEARTBEAT_S, "clock_check_every_s": CLOCK_CHECK_EVERY_S,
               "monitor_db": str(self.monitor_db), "approvals_path": str(self.approvals_path), "git": git_state}
        self.store.begin_run(self.run_id, "session", self.d, self.environment, os.getpid(), now.isoformat(), start_class,
                             code_fingerprint(), code_version(git_state), cfg)
        if not git_state["operations_code_committed"]:
            self._event("warn", "code_version", "operations code differs from the commit "
                        f"{(git_state['commit'] or 'unknown')[:12]} ({', '.join(git_state['uncommitted_paths'][:5])}); "
                        "this session cannot count toward acceptance")
        bad = self._record_checks("start", checks.safety_checks(self.environment))
        if bad:
            self._event("error", "refused", f"refusing to operate: unsafe configuration ({', '.join(bad)})")
            self.store.end_run(self.run_id, self.now().isoformat(), "refused: unsafe configuration")
            self._status("exited", exit_reason="refused: unsafe configuration")
            return 3
        if not plan.trading_day:
            self._event("info", "no_session", f"{d} is not an XNYS session; nothing to do")
            self.store.end_run(self.run_id, self.now().isoformat(), "no session")
            self._status("exited", exit_reason="no session")
            return 0
        self._event("info", "start", f"DRY_RUN for {d}: start {start_class}; open "
                    f"{plan.open_utc.astimezone(sc.ET):%H:%M} ET, close {plan.close_utc.astimezone(sc.ET):%H:%M} ET; "
                    f"report at {plan.report_utc.astimezone(sc.ET):%H:%M} ET")
        if start_class in (sc.LATE_START, sc.AFTER_SESSION):
            self._event("warn", "late_start", f"started {start_class}: earlier decision minutes are recorded as missing and are "
                        "never replayed; this session cannot PASS")
        pre_done = final_done = closing_done = False
        last_minute = None
        last_hb = None
        prev_wall, prev_mono = now, self.mono()
        try:
            while True:
                now = self.now()
                self.on_tick()
                try:
                    wall_dt, mono_dt = (now - prev_wall).total_seconds(), self.mono() - prev_mono
                    if wall_dt - mono_dt > JUMP_S or mono_dt > JUMP_S:
                        self._event("warn", "time_gap", f"{int(max(wall_dt, mono_dt))} s gap between loop iterations "
                                    "(sleep, freeze or clock jump suspected)")
                    prev_wall, prev_mono = now, self.mono()
                    if last_hb is None or (now - last_hb).total_seconds() >= HEARTBEAT_S:
                        self.store.heartbeat(self.run_id, now.isoformat())
                        last_hb = now
                        self._status("running", phase=sc.phase_at(plan, now), heartbeat_utc=now.isoformat())
                    ph = sc.phase_at(plan, now)
                    if ph == sc.PRE_OPEN_CHECKS:
                        if not pre_done:
                            self._preflight("pre_open", plan)
                            pre_done = True
                        if not final_done and now >= plan.final_check_utc:
                            self._preflight("final", plan)
                            final_done = True
                    elif ph == sc.DECISION_WINDOW:
                        if not pre_done:
                            self._preflight("late_start", plan)
                            pre_done = True
                        if self.last_clock_attempt is None or (now - self.last_clock_attempt).total_seconds() >= CLOCK_CHECK_EVERY_S:
                            self._periodic(plan)
                        minute = sc.minute_floor(now)
                        if minute != last_minute:
                            perm = self._decide(plan, minute, now)
                            self.decisions += 1
                            if last_minute is None or minute.minute % 15 == 0:
                                self._event("info", "decision", f"{minute.astimezone(sc.ET):%H:%M} entry "
                                            f"{'ALLOWED' if perm.allowed else 'DENIED'}: {perm.reasons[0]} "
                                            f"(+{len(perm.reasons) - 1} more reasons)")
                            last_minute = minute
                    elif ph == sc.CLOSING and not closing_done:
                        ok, det = self._closing_exposure()
                        self._record_checks("closing", [("exposure_none", ok, True, det)])
                        closing_done = True
                    elif ph == sc.REPORT_DUE:
                        self._event("info", "after_close", "after-close step reached; writing the report")
                        rep = self._write_report(self.now())
                        self._event("info", "report", f"session {self.d}: {rep['classification']}"
                                    + (f" ({'; '.join(rep['reasons'][:2])})" if rep["reasons"] else ""))
                        self.store.end_run(self.run_id, self.now().isoformat(), "completed")
                        self._status("exited", exit_reason="completed", classification=rep["classification"])
                        return 0
                    self.records_ok = True
                except sqlite3.Error as exc:            # records unavailable: no evidence, so no decisions
                    self.records_ok = False
                    print(f"WARNING: records unavailable ({type(exc).__name__}: {exc}); retrying", file=sys.stderr)
                    self.sleep(5)
                    continue
                self.sleep(1)
        except KeyboardInterrupt:
            self._event("warn", "stopped", "stopped by operator (Ctrl+C)")
            self.store.end_run(self.run_id, self.now().isoformat(), "stopped by operator")
            self._status("exited", exit_reason="stopped by operator")
            return 130
        except Exception as exc:
            self._event("error", "exception", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}")
            self.store.end_run(self.run_id, self.now().isoformat(), f"crash: {type(exc).__name__}")
            self._status("exited", exit_reason=f"crash: {type(exc).__name__}")
            return 1
