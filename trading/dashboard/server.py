"""Local DEMO REPLAY dashboard server (standard library only).

Run:  .venv\\Scripts\\python -m trading.dashboard.server  then open http://127.0.0.1:8765

Binds to 127.0.0.1 only. It never loads broker credentials and has no order
or broker code paths; the only data source is the synthetic demo replay.

Endpoints:
  GET  /api/meta                 replay description and configured instances
  GET  /api/snapshot             current ledger snapshot
  GET  /api/strategies/<id>      one instance's signals, decisions, fills, trades, bars
  GET  /api/strategies/<id>/evaluation   evaluation report up to the current replay time
  GET  /api/research             mode availability, periods, responsibilities
  GET  /api/stream               server-sent events: reset, ev, snapshot, replay
  POST /api/control              {"action": "pause"|"resume"|"restart"|"speed", "speed": n}
"""

import argparse
import json
import mimetypes
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from trading.dashboard.demo_replay import DEFAULT_CONFIG, ConfigError, build_demo, load_config
from trading.dashboard.ledger import Ledger
from trading.experiment import PERIODS
from trading.sessions import sessions_between

HOST = "127.0.0.1"
WEB_DIST = Path(__file__).resolve().parents[2] / "dashboard" / "web" / "dist"
RESPONSIBILITIES = Path(__file__).resolve().parents[2] / "research" / "responsibilities.json"
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


def research_status() -> dict:
    """What the Research Lab can and cannot do right now, from files on disk."""
    responsibilities = json.loads(RESPONSIBILITIES.read_text(encoding="utf-8"))
    periods = [{"period": name, "start": str(a), "end": str(b),
                "expected_sessions": len(sessions_between(a, b)),
                "sessions_with_verified_data": 0}
               for name, (a, b) in PERIODS.items()]
    return {
        "modes": {
            "DEMO": {"available": True, "reason": "synthetic fixtures"},
            "HISTORICAL_REPLAY": {"available": False,
                                  "reason": "Alpaca data access not verified; no historical data loaded"},
            "SIMULATION": {"available": False,
                           "reason": "method proposed in docs/PRODUCT_SPEC.md section 8, awaiting review; "
                                     "also needs historical replay"},
            "PAPER_ACCOUNT": {"available": False, "reason": "Alpaca paper access not verified"},
        },
        "historical_periods": periods,
        "responsibilities": responsibilities["responsibilities"],
        "skills_note": "The eleven-skill package from the reference video has not been received or installed.",
        "scanner_news": {"available": False,
                         "reason": "Universe fixed by spec (SPY). No verified, time-stamped news source."},
        "product_spec": "docs/PRODUCT_SPEC.md",
    }


def make_handler(ctrl: ReplayController):
    research = research_status()

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
            body = json.dumps(obj, default=str).encode()
            self._headers(status, "application/json", len(body))
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/api/meta":
                return self._json(ctrl.meta)
            if path == "/api/snapshot":
                with ctrl.cond:
                    return self._json({"snapshot": ctrl.snapshot(), "replay": ctrl.status()})
            if path == "/api/research":
                return self._json(research)
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
            if urlparse(self.path).path != "/api/control":
                return self._json({"error": "not found"}, 404)
            # A custom header forces a CORS preflight, so other websites can't drive this.
            if self.headers.get("X-Dashboard-Control") != "1":
                return self._json({"error": "missing X-Dashboard-Control header"}, 403)
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                return self._json(ctrl.control(body.get("action"), body.get("speed")))
            except (ValueError, TypeError) as exc:
                return self._json({"error": str(exc)}, 400)

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


def create_server(config_path: Path, port: int, speed: float | None = None):
    config = load_config(config_path)
    demo = build_demo(config)
    replay_cfg = config["replay"]
    ctrl = ReplayController(demo, speed or replay_cfg.get("start_speed", 600),
                            replay_cfg.get("duplicate_every", 0))
    httpd = ThreadingHTTPServer((HOST, port), make_handler(ctrl))
    httpd.daemon_threads = True
    stop = threading.Event()
    threading.Thread(target=_ticker, args=(ctrl, stop), daemon=True).start()
    return httpd, ctrl, stop


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Local DEMO REPLAY dashboard server")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--speed", type=float, default=None)
    args = parser.parse_args(argv)
    try:
        httpd, ctrl, stop = create_server(args.config, args.port, args.speed)
    except (ConfigError, FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        print(f"Config error: {exc}")
        return 2
    print(f"DEMO REPLAY (synthetic data, simulated outcomes) on http://{HOST}:{args.port}")
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
