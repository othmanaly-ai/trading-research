"""Read-only preview servers (`--read-only-preview`, used by the saved demo-dashboard launch configurations).
Everything runs on isolated temporary data (conftest redirects the monitoring store; job stores are temporary).
A preview must not start a worker, supervisor or job runner, must not write any record, and must refuse
state-changing requests other than the in-memory demo replay controls."""

import hashlib
import json
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pytest


def _dump_sha(path: Path) -> str:
    db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return hashlib.sha256("\n".join(db.iterdump()).encode()).hexdigest()
    finally:
        db.close()


def _post(port, path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Dashboard-Control": "1",
                                          "Origin": f"http://127.0.0.1:{port}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


@pytest.fixture
def preview(tmp_path, monkeypatch, _isolate_monitor):
    from trading import jobs as jobs_mod
    from trading.dashboard import server
    from trading.monitor import evidence_trace as et
    from trading.monitor import store as mst
    from trading.monitor import quality
    # isolated records with some content (SYNTHETIC)
    st = mst.MonitorStore()
    quality.ensure_schema(st)
    st.set_desired("running", "fixture", datetime(2026, 11, 16, 14, 0, tzinfo=timezone.utc))
    st.event("info", "fixture", "synthetic record", datetime(2026, 11, 16, 14, 0, tzinfo=timezone.utc))
    st.db.commit()
    st.close()
    jobs_db = tmp_path / "jobs" / "jobs.sqlite"
    jobs_mod.JobStore(jobs_db).close()
    monkeypatch.setattr(server, "JOBS_DB", jobs_db)
    monkeypatch.setattr(et, "DESK_DB", tmp_path / "jobs" / "desk.sqlite")
    monkeypatch.setenv("TRADING_OPS_DIR", str(tmp_path / "ops"))
    # flags are module state: let monkeypatch restore them after the test
    monkeypatch.setattr(server, "READ_ONLY_PREVIEW", False)
    monkeypatch.setattr(mst, "READ_ONLY_VIEW", False)
    before_threads = {t.name for t in threading.enumerate()}
    httpd, _ctrl, stop = server.create_server(server.DEFAULT_CONFIG, 0, 3600, read_only=True)
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    yield {"port": httpd.server_address[1], "monitor_db": mst.DB_PATH, "jobs_db": jobs_db,
           "spawned": _isolate_monitor, "before_threads": before_threads}
    stop.set()
    httpd.shutdown()
    httpd.server_close()


def test_preview_starts_no_worker_supervisor_or_job_runner(preview):
    from trading.monitor.control import Supervisor
    from trading.jobs import JobRunner
    assert not any(isinstance(t, (Supervisor, JobRunner)) for t in threading.enumerate())
    assert preview["spawned"] == []                                         # no worker process launched
    db = sqlite3.connect(f"file:{Path(preview['monitor_db']).as_posix()}?mode=ro", uri=True)
    assert db.execute("SELECT COUNT(*) FROM events WHERE kind='server'").fetchone()[0] == 0   # no lifecycle record
    db.close()


def test_preview_reads_change_no_records(preview):
    port = preview["port"]
    before = {k: _dump_sha(Path(preview[k])) for k in ("monitor_db", "jobs_db")}
    for path in ("/api/meta", "/api/monitor", "/api/monitor/readiness", "/api/monitor/sessions", "/api/depmap",
                 "/api/operations", "/api/jobs", "/api/desk"):
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=60) as r:
            assert r.status == 200, path
    after = {k: _dump_sha(Path(preview[k])) for k in ("monitor_db", "jobs_db")}
    assert after == before                                                  # readiness recording went to a snapshot
    assert preview["spawned"] == []


def test_preview_refuses_state_changes_but_keeps_replay_controls(preview):
    port = preview["port"]
    before = {k: _dump_sha(Path(preview[k])) for k in ("monitor_db", "jobs_db")}
    for path, body in (("/api/monitor/control", {"action": "start"}), ("/api/monitor/control", {"action": "stop"}),
                       ("/api/monitor/incidents/ack", {"id": 1}),
                       ("/api/pipelines", {"experiment": "001_intraday_momentum"}),
                       ("/api/pipelines/x/cancel", {})):
        code, out = _post(port, path, body)
        assert code == 403 and "read-only preview" in out["error"], path
    assert _post(port, "/api/control", {"action": "pause"})[0] == 200     # in-memory demo replay only
    after = {k: _dump_sha(Path(preview[k])) for k in ("monitor_db", "jobs_db")}
    assert after == before and preview["spawned"] == []


def test_saved_launch_configurations_are_read_only_on_their_own_ports():
    cfg = json.loads((Path(__file__).resolve().parents[1] / ".claude" / "launch.json").read_text(encoding="utf-8"))
    ports = {}
    for c in cfg["configurations"]:
        args = c["runtimeArgs"]
        if "trading.dashboard.server" in args:
            assert "--read-only-preview" in args, c["name"]                 # never a second production server
            port = int(args[args.index("--port") + 1])
            assert port == c["port"] and port != 8765, c["name"]            # 8765 is the production city server
            ports[c["name"]] = port
    assert len(set(ports.values())) == len(ports)
