"""Local dashboard server (standard library only): DEMO or HISTORICAL REPLAY.

Run:  .venv\\Scripts\\python -m trading.dashboard.server                     (DEMO, synthetic)
      .venv\\Scripts\\python -m trading.dashboard.server --mode historical   (stored Alpaca bars)
then open http://127.0.0.1:8765

Binds to 127.0.0.1 only. It never loads broker credentials and has no order
or broker code paths. Historical mode reads only bars already stored on disk by
`python -m trading.history`; if they are missing it refuses to start.

Endpoints:
  GET  /api/meta                 replay description and configured instances
  GET  /api/snapshot             current ledger snapshot
  GET  /api/strategies/<id>      one instance's signals, decisions, fills, trades, bars
  GET  /api/strategies/<id>/evaluation   evaluation report up to the current replay time
  GET  /api/strategies/<id>/journal      journal rows (JSON); /journal.csv downloads them
  GET  /api/research             mode availability, periods, responsibilities
  GET  /api/depmap               read-only dependency-and-health map (declared / recorded / proposed)
  GET  /api/jobs                 real research-job records (trading/jobs.py), read-only
  GET  /api/experiments          allowed saved experiments with artifact inventories
  GET  /api/pipelines/preview?experiment=<allowed id>
  POST /api/pipelines            {"experiment": <allowed id>} queues the predefined pipeline
  POST /api/pipelines/<id>/cancel
  GET  /api/reports/<pipeline id>  the completed report's markdown
  GET  /api/stream               server-sent events: reset, ev, snapshot, replay
  POST /api/control              {"action": "pause"|"resume"|"restart"|"speed", "speed": n}
"""

import argparse
import csv
import io
import hashlib
import json
import math
import mimetypes
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from trading.dashboard.demo_replay import DEFAULT_CONFIG, ConfigError, build_demo, load_config
from trading.dashboard.historical_replay import DEFAULT_CONFIG as HIST_CONFIG
from trading.dashboard.historical_replay import build_historical
from trading.dashboard.historical_replay import load_config as load_hist_config
from trading.dashboard.ledger import Ledger
from trading.experiment import PERIODS
from trading.history import HISTORY_DIR, HistoryError, read_manifest
from trading.journal import COLUMNS as JOURNAL_COLUMNS
from trading.journal import build_journal
from trading import jobs as jobs_mod
from trading.sessions import sessions_between

HOST = "127.0.0.1"
WEB_DIST = Path(__file__).resolve().parents[2] / "dashboard" / "web" / "dist"
RESPONSIBILITIES = Path(__file__).resolve().parents[2] / "research" / "responsibilities.json"
JOBS_DB = Path(__file__).resolve().parents[2] / "data" / "jobs" / "jobs.sqlite"
JOBS_RESEARCH_DIR = Path(__file__).resolve().parents[2] / "research"
MAX_BODY = 2048
ALPACA_CHECKS = Path(__file__).resolve().parents[2] / "data" / "alpaca"


def strict_json(obj):
    """Replace non-finite floats with None, recursively."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: strict_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [strict_json(v) for v in obj]
    return obj


def paper_account_reason() -> str:
    """Accurate status from saved verification outputs (read-only; no credentials are loaded)."""
    runs = sorted(p.name for p in ALPACA_CHECKS.glob("*") if (p / "account.json").is_file())         if ALPACA_CHECKS.is_dir() else []
    if runs:
        return (f"read-only paper account access verified by `trading.verify_data_access` (latest saved "
                f"check {runs[-1]}); live account monitoring in this dashboard is not implemented")
    return "Alpaca paper account access not yet verified in this project"


REVIEW_ID = re.compile(r"^rv-[A-Za-z0-9-]{1,80}$")


def monitor_snapshot() -> dict:
    """Monitoring records (separate process writes them; this server only reads)."""
    from trading.monitor import store as mst
    store = mst.MonitorStore()
    try:
        snap = store.status()
        feed = snap["config"]["feed"]
        snap["recent_bars"] = {r["symbol"]: store.bars(r["symbol"], feed, 30) for r in snap["symbols"]}
        snap["controls"] = {
            "start": "desired state running; launches one worker process if none is alive",
            "pause": "worker stays alive but makes no API calls",
            "stop": "worker exits within about a second; nothing restarts it until Start",
        }
    finally:
        store.close()
    return snap


QUALITY_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
QUALITY_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\+00:00$")


def quality_report(date_s: str | None) -> dict:
    from trading.monitor import quality, store as mst
    if date_s and not QUALITY_DATE.match(date_s):
        raise ValueError("date must be YYYY-MM-DD")
    store = mst.MonitorStore()
    try:
        return quality.report(store, date_s or None)
    finally:
        store.close()


def quality_minute(symbol: str, t_utc: str) -> dict:
    from trading.monitor import quality, store as mst
    if not re.match(r"^[A-Z]{1,5}$", symbol or "") or not QUALITY_TS.match(t_utc or ""):
        raise ValueError("symbol must be 1-5 capital letters and t a minute timestamp like 2026-11-04T15:00:00+00:00")
    store = mst.MonitorStore()
    try:
        return quality.minute_record(store, symbol, t_utc)
    finally:
        store.close()


def monitor_sessions() -> dict:
    from trading.monitor import quality, reliability, store as mst
    store = mst.MonitorStore()
    try:
        quality.ensure_schema(store)
        return {"sessions": reliability.sessions_overview(store),
                "comparison_health": dict(store.db.execute("SELECT * FROM q_health WHERE id=1").fetchone()),
                "operating_note": "Monitoring runs only while this computer is on and the city server is running. "
                                  "There is no Windows startup task and no 24/7 service. Unfinished sessions within "
                                  f"the last {quality.RECOVERY_LOOKBACK_SESSIONS} trading sessions are recovered "
                                  "when the worker runs again; live capture gaps cannot be recovered."}
    finally:
        store.close()


def monitor_report(date_s: str) -> dict:
    from trading.monitor import reliability, store as mst
    if not QUALITY_DATE.match(date_s or ""):
        raise ValueError("date must be YYYY-MM-DD")
    store = mst.MonitorStore()
    try:
        return reliability.stored_or_current(store, date_s)
    finally:
        store.close()


def monitor_control(action: str) -> dict:
    from trading.monitor import control, store as mst
    store = mst.MonitorStore()
    try:
        if action == "start":
            note = control.start(store, "dashboard")
        elif action == "pause":
            store.set_desired("paused", "dashboard")
            note = "paused: the worker keeps running but fetches nothing"
        elif action == "stop":
            store.set_desired("stopped", "dashboard")
            note = "stop requested: the worker exits within about a second"
        else:
            raise ValueError("action must be start, pause or stop")
        return {"action": action, "desired": store.desired(), "note": note}
    finally:
        store.close()


def _server_env() -> dict:
    from trading.reviewer import review
    return review.server_env()


def reviewer_status() -> dict:
    """Readiness gates (no secret is read or returned) and recent records. Server context: no keys."""
    from trading.reviewer import budget, review
    store = budget.ReviewStore()
    try:
        r = review.readiness(review.server_env(), store)
        r["recent"] = store.recent(10)
    finally:
        store.close()
    r["label"] = "automated second review; not proof of independent correctness"
    return r


def review_record(review_id: str):
    from trading.reviewer import budget
    if not REVIEW_ID.match(review_id):
        return None
    store = budget.ReviewStore()
    try:
        return store.get(review_id)
    finally:
        store.close()


def with_store(fn):
    store = jobs_mod.JobStore(JOBS_DB)
    try:
        return fn(store)
    finally:
        store.close()


def experiments_overview() -> dict:
    """Allowed experiments only, with read-only artifact inventories and pipeline state."""
    def build(st):
        out = []
        for exp in jobs_mod.ALLOWED_EXPERIMENTS:
            item = jobs_mod.inventory(exp, JOBS_RESEARCH_DIR)
            item["active_pipeline"] = st.active_pipeline(exp)
            row = st.db.execute("SELECT id, status FROM pipelines WHERE experiment=? ORDER BY rowid DESC LIMIT 1",
                                (exp,)).fetchone()
            item["latest_pipeline"] = dict(row) if row else None
            out.append(item)
        return out
    return {"mode_label": "REAL RESEARCH JOBS (not demo)", "pipelines": jobs_mod.PIPELINES,
            "experiments": with_store(build), "candidates": candidates_overview()}


CANDIDATES_DIR = Path(__file__).resolve().parents[2] / "research" / "candidates"


def candidates_overview(root: Path | None = None) -> list[dict]:
    """Research candidates that are not experiments (no pipeline can run on them). Read-only;
    never raises for missing or corrupt files."""
    root = root or CANDIDATES_DIR
    project = root.parents[1]
    out = []
    for status_path in sorted(root.glob("*/STATUS.json")) if root.is_dir() else []:
        item = {"candidate": status_path.parent.name, "status": None, "artifacts": [], "problems": []}
        try:
            st = json.loads(status_path.read_text(encoding="utf-8"))
            item["status"] = {k: st.get(k) for k in ("candidate_id", "title", "state", "status", "is_experiment",
                                                      "performance_evaluated", "downloads", "blockers",
                                                      "open_uncertainties", "resume_requires", "decided_utc")}
            for rel in st.get("records") or []:
                p = project / rel
                if p.is_file():
                    item["artifacts"].append({"name": rel, "present": True, "bytes": p.stat().st_size,
                                              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()[:16]})
                else:
                    item["artifacts"].append({"name": rel, "present": False})
                    item["problems"].append(f"{rel} is missing")
        except (OSError, ValueError) as exc:
            item["problems"].append(f"STATUS.json unreadable: {type(exc).__name__}")
        out.append(item)
    return out


def jobs_snapshot() -> dict:
    """Real research-job records, read from the job store (never demo data)."""
    from trading.jobs import MODEL_POLICY, UNIMPLEMENTED_ROLES, WORKERS, JobStore
    if not JOBS_DB.is_file():
        snap = {"pipelines": [], "jobs": [], "roles": UNIMPLEMENTED_ROLES, "model_policy": MODEL_POLICY,
                "workers": [{"worker": w, "kind": k, "version": v, "depends_on": d} for w, k, v, d in WORKERS]}
    else:
        store = JobStore(JOBS_DB)
        try:
            snap = store.snapshot()
        finally:
            store.close()
    return {"mode_label": "REAL RESEARCH JOBS (not demo)", **snap}
TICK_SECONDS = 0.05
MAX_IDLE_REPLAY_SECONDS = 90      # skip quiet stretches (overnight, mid-day) faster
MIN_SPEED, MAX_SPEED = 1, 3600
HEARTBEAT_SECONDS = 15


def _epoch(ts: str) -> float:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


class ReplayController:
    """Releases events in timestamp order on a speed-adjustable replay clock."""

    def __init__(self, demo, start_speed: float, duplicate_every: int = 0):
        self.meta = demo.meta
        self.events = [e.to_dict() for e in demo.events]
        self.times = [_epoch(e["ts_utc"]) for e in self.events]
        self.duplicate_every = duplicate_every
        self.cond = threading.Condition()
        self.speed = float(start_speed)
        self.generation = 0
        self._reset()

    def _reset(self):
        self.cursor = 0
        self.ledger = Ledger(self.meta)
        self.clock = self.times[0] if self.times else None
        self.playing = True
        self.history: list[dict] = []
        self.released = 0
        self.generation += 1
        self._snapshot_cache = None

    def tick(self, dt: float) -> bool:
        with self.cond:
            if not self.playing or self.cursor >= len(self.events):
                return False
            self.clock += dt * self.speed
            nxt = self.times[self.cursor]
            if nxt - self.clock > MAX_IDLE_REPLAY_SECONDS:
                self.clock = nxt
            changed = False
            while self.cursor < len(self.events) and self.times[self.cursor] <= self.clock:
                ev = self.events[self.cursor]
                self.cursor += 1
                self._release(ev)
                self.released += 1
                if self.duplicate_every and self.released % self.duplicate_every == 0:
                    # Deliberately resend an earlier event, as a flaky network might.
                    self._release(self.events[max(0, self.cursor - 10)])
                changed = True
            if self.cursor >= len(self.events):
                self.playing = False
                changed = True
            if changed:
                self._snapshot_cache = None
                self.cond.notify_all()
            return changed

    def _release(self, ev: dict):
        self.ledger.apply(ev)
        self.history.append(ev)

    def control(self, action: str, speed=None) -> dict:
        with self.cond:
            if action == "pause":
                self.playing = False
            elif action == "resume":
                self.playing = self.cursor < len(self.events)
            elif action == "restart":
                self._reset()
            elif action == "speed":
                self.speed = float(min(MAX_SPEED, max(MIN_SPEED, float(speed))))
            else:
                raise ValueError(f"unknown action {action!r}")
            self._snapshot_cache = None
            self.cond.notify_all()
            return self.status()

    def status(self) -> dict:
        clock = (datetime.fromtimestamp(self.clock, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                 if self.clock else None)
        return {"mode": self.meta["mode"], "playing": self.playing, "speed": self.speed,
                "replay_clock_utc": clock,
                "cursor": self.cursor, "total": len(self.events),
                "finished": self.cursor >= len(self.events), "generation": self.generation}

    def snapshot(self) -> dict:
        if self._snapshot_cache is None:
            self._snapshot_cache = self.ledger.snapshot()
        return self._snapshot_cache


def _lock_status() -> dict:
    from trading.experiment_lock import LOCK_PATH, LockMismatch, check_lock
    from trading.risk import RiskLimits
    if not LOCK_PATH.is_file():
        return {"present": False, "status": "no lock written"}
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    try:
        check_lock(RiskLimits())
        status = "matches current definition"
    except LockMismatch as exc:
        status = f"MISMATCH: {exc}"
    return {"present": True, "experiment_id": lock["experiment_id"], "created_utc": lock["created_utc"],
            "hypothesis": lock["hypothesis"], "status": status,
            "risk_limits_are_placeholders": lock["risk_limits_are_placeholders"],
            "data_status_at_lock": lock["data_status_at_lock"]}


def _order_gate() -> dict:
    """Order-submission gate as configured for this server process (environment flags only)."""
    from trading.safety import order_submission_enabled, trading_mode
    return {"enabled": order_submission_enabled(), "trading_mode": trading_mode(),
            "note": "No order-submission code exists in this project; the Alpaca client sends HTTP GET only "
                    "(enforced by tests). Any future order code must pass trading.safety first."}


def research_status(history_root: Path = HISTORY_DIR, hist_config_path: Path = HIST_CONFIG) -> dict:
    """What the Research Lab can and cannot do right now, from files on disk."""
    responsibilities = json.loads(RESPONSIBILITIES.read_text(encoding="utf-8"))
    hc = load_hist_config(hist_config_path)
    manifest = read_manifest(hc["symbol"], hc["feed"], hc["adjustment"], history_root)
    by_period = manifest["summary"]["by_period"] if manifest else {}
    periods = [{"period": name, "start": str(a), "end": str(b),
                "expected_sessions": len(sessions_between(a, b)),
                "sessions_with_verified_data": by_period.get(name, 0)}
               for name, (a, b) in PERIODS.items()]
    usable = manifest["summary"]["usable_sessions"] if manifest else 0
    hist_reason = (f"{usable} usable {hc['symbol']} {hc['feed']} sessions stored "
                   f"(retrieved {manifest['retrieved_utc']}); start the server with --mode historical"
                   if usable else "no verified historical data stored; needs Alpaca paper keys and "
                                  "`python -m trading.history`")
    return {
        "modes": {
            "DEMO": {"available": True, "reason": "synthetic fixtures"},
            "HISTORICAL_REPLAY": {"available": usable > 0, "reason": hist_reason},
            "SIMULATION": {"available": False,
                           "reason": "scenario-simulation method proposed in docs/PRODUCT_SPEC.md section 8; "
                                     "awaiting owner review, not implemented"},
            "PAPER_ACCOUNT": {"available": False, "reason": paper_account_reason()},
        },
        "historical_periods": periods,
        "historical_data": None if not manifest else {
            k: manifest.get(k) for k in ("source", "symbol", "requested_feed", "actual_feed", "adjustment",
                                         "interval", "calendar", "start", "end", "retrieved_utc",
                                         "transformations", "limitations")
        } | {"requests": manifest.get("requests"), "summary": manifest.get("summary")},
        "experiment_lock": _lock_status(),
        "responsibilities": responsibilities["responsibilities"],
        "order_submission": _order_gate(),
        "skills_note": "The eleven-skill package from the reference video has not been received or installed.",
        "scanner_news": {"available": False,
                         "reason": "Universe fixed by spec (SPY). No verified, time-stamped news source."},
        "product_spec": "docs/PRODUCT_SPEC.md",
    }


def make_handler(ctrl: ReplayController, history_root: Path = HISTORY_DIR):
    research = research_status(history_root)
    research["active_mode"] = ctrl.meta["mode"]

    class Handler(BaseHTTPRequestHandler):
        server_version = "DemoReplayDashboard/0.1"

        def log_message(self, fmt, *args):     # keep the console quiet; no request bodies
            pass

        def _headers(self, status: int, ctype: str, length: int | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
            self.send_header("Cache-Control", "no-store")
            if length is not None:
                self.send_header("Content-Length", str(length))
            self.end_headers()

        def _json(self, obj, status=200):
            # Strict JSON: NaN/Infinity are not valid JSON and break browsers, so send null.
            body = json.dumps(strict_json(obj), default=str, allow_nan=False).encode()
            self._headers(status, "application/json", len(body))
            self.wfile.write(body)

        def _host_ok(self) -> bool:
            """Only requests addressed to this local server (blocks DNS-rebinding hosts)."""
            port = self.server.server_address[1]
            return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _state_change_ok(self) -> str | None:
            """Reason to refuse a state-changing request from anything but this page, or None."""
            if not self._host_ok():
                return "host not allowed"
            if self.headers.get("X-Dashboard-Control") != "1":      # forces a CORS preflight cross-site
                return "missing X-Dashboard-Control header"
            origin = self.headers.get("Origin")
            if origin is not None and origin != f"http://{self.headers.get('Host')}":
                return "cross-origin request refused"
            if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
                return "cross-site request refused"
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return "Content-Type must be application/json"
            return None

        def _drain(self) -> None:
            """Read and discard a refused request's body (bounded) so the client sees the reply
            instead of a connection reset; oversized bodies close the connection."""
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            if 0 < n <= 64 * 1024:
                self.rfile.read(n)
            elif n > 64 * 1024:
                self.close_connection = True

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                self._drain()
                raise ValueError("request body too large")
            body = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("JSON object required")
            return body

        def do_GET(self):
            path = urlparse(self.path).path
            if path.startswith("/api/") and not self._host_ok():
                return self._json({"error": "host not allowed"}, 403)
            if path == "/api/experiments":
                return self._json(experiments_overview())
            if path == "/api/pipelines/preview":
                exp = parse_qs(urlparse(self.path).query).get("experiment", [""])[0]
                try:
                    return self._json(with_store(lambda st: jobs_mod.preview(exp, st, JOBS_RESEARCH_DIR, env=_server_env())))
                except ValueError as exc:
                    return self._json({"error": str(exc)}, 400)
            if path == "/api/depmap":
                from trading.dashboard import depmap
                return self._json(depmap.collect(jobs_db=JOBS_DB))
            if path == "/api/monitor":
                return self._json(monitor_snapshot())
            if path == "/api/monitor/sessions":
                return self._json(monitor_sessions())
            if path == "/api/monitor/report":
                try:
                    return self._json(monitor_report(parse_qs(urlparse(self.path).query).get("date", [""])[0]))
                except ValueError as exc:
                    return self._json({"error": str(exc)}, 400)
            if path in ("/api/quality", "/api/quality/minute"):
                q = parse_qs(urlparse(self.path).query)
                try:
                    if path == "/api/quality":
                        return self._json(quality_report(q.get("date", [""])[0]))
                    return self._json(quality_minute(q.get("symbol", [""])[0], q.get("t", [""])[0]))
                except ValueError as exc:
                    return self._json({"error": str(exc)}, 400)
            if path == "/api/reviewer/status":
                return self._json(reviewer_status())
            if path.startswith("/api/reviews/"):
                rec = review_record(unquote(path[len("/api/reviews/"):]))
                return self._json(rec) if rec else self._json({"error": "unknown review"}, 404)
            if path.startswith("/api/reports/"):
                return self._report(unquote(path[len("/api/reports/"):]))
            if path == "/api/meta":
                return self._json(ctrl.meta)
            if path == "/api/snapshot":
                with ctrl.cond:
                    return self._json({"snapshot": ctrl.snapshot(), "replay": ctrl.status()})
            if path == "/api/jobs":
                return self._json(jobs_snapshot())
            if path == "/api/research":
                return self._json(research)
            if path.startswith("/api/strategies/") and path.endswith(("/journal", "/journal.csv")):
                sid = unquote(path.split("/")[3])
                with ctrl.cond:
                    if sid not in ctrl.ledger.strategies:
                        return self._json({"error": f"unknown strategy {sid}"}, 404)
                    rows = build_journal(ctrl.ledger, sid)
                if not path.endswith(".csv"):
                    return self._json({"mode": ctrl.meta["mode"], "strategy_id": sid, "rows": rows})
                buf = io.StringIO()
                w = csv.DictWriter(buf, fieldnames=JOURNAL_COLUMNS)
                w.writeheader()
                w.writerows(rows)
                body = buf.getvalue().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="{ctrl.meta["mode"].lower()}_{sid}_journal.csv"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            if path.startswith("/api/strategies/") and path.endswith("/evaluation"):
                sid = unquote(path.split("/")[3])
                with ctrl.cond:
                    rep = ctrl.ledger.evaluation(sid)
                return self._json(rep) if rep else self._json({"error": f"unknown strategy {sid}"}, 404)
            if path.startswith("/api/strategies/"):
                sid = unquote(path.rsplit("/", 1)[-1])
                with ctrl.cond:
                    rec = ctrl.ledger.strategy_records(sid)
                return self._json(rec) if rec else self._json({"error": f"unknown strategy {sid}"}, 404)
            if path == "/api/stream":
                return self._stream()
            if path.startswith("/api/"):
                return self._json({"error": "not found"}, 404)
            return self._static(path)

        def do_POST(self):
            path = urlparse(self.path).path
            refusal = self._state_change_ok()
            if refusal:
                self._drain()
                return self._json({"error": refusal}, 403)
            try:
                body = self._body()
                if path == "/api/control":
                    return self._json(ctrl.control(body.get("action"), body.get("speed")))
                if path == "/api/monitor/control":
                    if set(body) != {"action"} or not isinstance(body["action"], str):
                        raise ValueError("expected only {action}")
                    return self._json(monitor_control(body["action"]))
                if path == "/api/pipelines":
                    if set(body) - {"experiment", "pipeline"} or not isinstance(body.get("experiment"), str) \
                            or not isinstance(body.get("pipeline", "reconcile_report"), str):
                        raise ValueError("expected only {experiment, pipeline} as strings")
                    pid, created = with_store(lambda st: jobs_mod.plan_pipeline(
                        body["experiment"], st, JOBS_RESEARCH_DIR, body.get("pipeline", "reconcile_report"), env=_server_env()))
                    return self._json({"pipeline_id": pid, "created": created,
                                       "note": "queued for the background runner" if created
                                       else "an active pipeline already exists; no new work created"},
                                      201 if created else 200)
                if path.startswith("/api/pipelines/") and path.endswith("/cancel"):
                    if body:
                        raise ValueError("cancel takes no parameters")
                    pid = unquote(path[len("/api/pipelines/"):-len("/cancel")])
                    try:
                        result = with_store(lambda st: jobs_mod.request_cancel(pid, st))
                    except KeyError:
                        return self._json({"error": "unknown pipeline"}, 404)
                    return self._json({"pipeline_id": pid, "result": result})
                return self._json({"error": "not found"}, 404)
            except (ValueError, TypeError) as exc:
                return self._json({"error": str(exc)}, 400)
            except sqlite3.Error as exc:
                return self._json({"error": f"job store busy or unavailable ({type(exc).__name__}); "
                                            "nothing was changed, retry"}, 503)

        def _report(self, pipeline_id: str):
            """Serve a report only for a known pipeline whose report job completed, from REPORT_DIR."""
            def find(st):
                p = st.pipeline(pipeline_id)
                if p is None:
                    return None
                for jid in p["job_ids"]:
                    j = st.get(jid)
                    if j["worker"] == "report" and j["status"] == "completed":
                        return j["outputs"]["report_path"]
                return None
            rel = with_store(find)
            if rel is None:
                return self._json({"error": "no completed report for this pipeline"}, 404)
            root = jobs_mod.REPORT_DIR.resolve()
            target = (jobs_mod.PROJECT_ROOT / rel).resolve()
            if root not in target.parents or not target.is_file():
                return self._json({"error": "report file not available"}, 404)
            return self._json({"pipeline_id": pipeline_id, "report_markdown": target.read_text(encoding="utf-8")})

        def _send_sse(self, name: str, data) -> None:
            self.wfile.write(f"event: {name}\ndata: {json.dumps(data, default=str)}\n\n".encode())

        def _stream(self):
            self._headers(200, "text/event-stream")
            gen, idx, sent_snapshot, last_beat = None, 0, None, time.monotonic()
            try:
                while True:
                    with ctrl.cond:
                        ctrl.cond.wait(timeout=0.5)
                        if gen != ctrl.generation:
                            gen, idx, sent_snapshot = ctrl.generation, 0, None
                            self._send_sse("reset", {"generation": gen})
                        batch = ctrl.history[idx:]
                        idx += len(batch)
                        snap = ctrl.snapshot()
                        status = ctrl.status()
                    for ev in batch:
                        self._send_sse("ev", ev)
                    if batch or snap is not sent_snapshot:
                        self._send_sse("snapshot", snap)
                        sent_snapshot = snap
                    self._send_sse("replay", status)
                    if time.monotonic() - last_beat > HEARTBEAT_SECONDS:
                        self.wfile.write(b": heartbeat\n\n")
                        last_beat = time.monotonic()
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return

        def _static(self, path: str):
            if not WEB_DIST.is_dir():
                msg = b"Frontend not built. Run: cd dashboard/web && npm install && npm run build"
                self._headers(503, "text/plain; charset=utf-8", len(msg))
                return self.wfile.write(msg)
            target = (WEB_DIST / unquote(path).lstrip("/")).resolve()
            if WEB_DIST.resolve() not in target.parents and target != WEB_DIST.resolve():
                return self._json({"error": "not found"}, 404)
            if not target.is_file():
                target = WEB_DIST / "index.html"
            body = target.read_bytes()
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self._headers(200, ctype, len(body))
            self.wfile.write(body)

    return Handler


def _ticker(ctrl: ReplayController, stop: threading.Event):
    last = time.monotonic()
    while not stop.wait(TICK_SECONDS):
        now = time.monotonic()
        ctrl.tick(now - last)
        last = now


def create_server(config_path: Path | None, port: int, speed: float | None = None, mode: str = "demo",
                  history_root: Path = HISTORY_DIR, run_jobs: bool = True, supervise_monitor: bool = True):
    """mode "demo" uses synthetic fixtures; mode "historical" uses stored Alpaca bars and
    raises HistoryError if they are missing. One server runs exactly one mode."""
    if mode == "historical":
        replay = build_historical(load_hist_config(config_path or HIST_CONFIG), history_root)
        ctrl = ReplayController(replay, speed or 600, duplicate_every=0)
    elif mode == "demo":
        config = load_config(config_path or DEFAULT_CONFIG)
        replay_cfg = config["replay"]
        ctrl = ReplayController(build_demo(config), speed or replay_cfg.get("start_speed", 600),
                                replay_cfg.get("duplicate_every", 0))
    else:
        raise ValueError(f"unknown mode {mode!r}")
    httpd = ThreadingHTTPServer((HOST, port), make_handler(ctrl, history_root))
    httpd.daemon_threads = True
    stop = threading.Event()
    threading.Thread(target=_ticker, args=(ctrl, stop), daemon=True).start()
    if run_jobs:
        # Research jobs run here, outside web requests. Interrupted work is marked failed on start.
        runner = jobs_mod.JobRunner(JOBS_DB, JOBS_RESEARCH_DIR)
        runner.stop_event = stop
        runner.start()
    if supervise_monitor:
        from trading.monitor.control import Supervisor
        Supervisor(stop).start()          # restart recovery for the separate monitoring worker
    return httpd, ctrl, stop


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Local dashboard server (DEMO or HISTORICAL REPLAY)")
    parser.add_argument("--mode", choices=["demo", "historical"], default="demo")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--speed", type=float, default=None)
    args = parser.parse_args(argv)
    try:
        httpd, ctrl, stop = create_server(args.config, args.port, args.speed, args.mode)
    except HistoryError as exc:
        print(f"HISTORICAL REPLAY unavailable: {exc}")
        print("Not starting. (No fallback to demo data.)")
        return 2
    except (ConfigError, FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        print(f"Config error: {exc}")
        return 2
    print(f"{ctrl.meta['banner']}\nServing on http://{HOST}:{args.port}")
    print(f"{ctrl.meta['event_count']} events, {len(ctrl.meta['instances'])} instances. "
          f"Order submission: disabled. Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
