"""Research-job control endpoints: validation, origin protection, background execution,
deduplication, cancellation, restart recovery and report access. Uses copies of the real
experiment artifacts and a temporary job database; no trading evaluation is re-run."""

import json
import shutil
import threading
import time
import urllib.error
import urllib.request

import pytest

from trading import jobs
from trading.dashboard import server

EXPS = ("001_intraday_momentum", "002_opening_range_breakout")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    research = tmp_path / "research"
    for e in EXPS:
        shutil.copytree(jobs.RESEARCH_DIR / e, research / e)
    db = tmp_path / "jobs.sqlite"
    monkeypatch.setattr(server, "JOBS_DB", db)
    monkeypatch.setattr(server, "JOBS_RESEARCH_DIR", research)
    monkeypatch.setattr(jobs, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(jobs, "STEP_HOOK", None)
    started = []

    def start(run_jobs=True):
        httpd, ctrl, stop = server.create_server(None, 0, speed=3600, run_jobs=run_jobs)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        started.append((httpd, stop))
        return f"http://127.0.0.1:{httpd.server_address[1]}"

    yield start, db, research
    for httpd, stop in started:
        stop.set()
        httpd.shutdown()
        httpd.server_close()


def call(base, path, body=None, headers=None, method=None):
    h = {"Content-Type": "application/json", "X-Dashboard-Control": "1"} if body is not None else {}
    h.update(headers or {})
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    req = urllib.request.Request(base + path, data=data, headers=h, method=method or ("POST" if body is not None else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def wait_status(base, pid, wanted, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        p = next((p for p in call(base, "/api/jobs")[1]["pipelines"] if p["id"] == pid), None)
        if p and p["status"] in wanted:
            return p
        time.sleep(0.1)
    raise AssertionError(f"pipeline {pid} did not reach {wanted}")


def test_experiments_and_preview(setup):
    start, _, _ = setup
    base = start(run_jobs=False)
    code, body = call(base, "/api/experiments")
    assert code == 200 and [e["experiment"] for e in body["experiments"]] == list(EXPS)
    assert all(a["present"] for e in body["experiments"] for a in e["artifacts"])
    code, prev = call(base, "/api/pipelines/preview?experiment=002_opening_range_breakout")
    assert code == 200 and [t["worker"] for t in prev["tasks"]][0] == "ingest"
    assert "UNAVAILABLE: no model call" in next(t for t in prev["tasks"] if t["worker"] == "model_review")["action"]
    assert call(base, "/api/pipelines/preview?experiment=../etc")[0] == 400


@pytest.mark.parametrize("headers, body, code", [
    ({"X-Dashboard-Control": ""}, {"experiment": EXPS[1]}, 403),
    ({"Origin": "https://evil.example"}, {"experiment": EXPS[1]}, 403),
    ({"Host": "evil.example"}, {"experiment": EXPS[1]}, 403),
    ({"Sec-Fetch-Site": "cross-site"}, {"experiment": EXPS[1]}, 403),
    ({"Content-Type": "text/plain"}, {"experiment": EXPS[1]}, 403),
    ({}, {"experiment": "003_secret"}, 400),
    ({}, {"experiment": EXPS[1], "command": "rm -rf"}, 400),
    ({}, {"experiment": EXPS[1], "pipeline": "shell"}, 400),
    ({}, {"experiment": ["x"]}, 400),
    ({}, b"x" * 5000, 400),
])
def test_invalid_or_cross_site_requests_refused(setup, headers, body, code):
    start, db, _ = setup
    base = start(run_jobs=False)
    assert call(base, "/api/pipelines", body, headers)[0] == code
    assert call(base, "/api/jobs")[1]["pipelines"] == []               # nothing was created


def test_get_with_foreign_host_refused(setup):
    start, _, _ = setup
    base = start(run_jobs=False)
    assert call(base, "/api/jobs", headers={"Host": "attacker.test"})[0] == 403


def test_launch_runs_in_background_and_report_opens(setup):
    start, _, _ = setup
    base = start()
    code, body = call(base, "/api/pipelines", {"experiment": EXPS[1]})
    assert code == 201 and body["created"]
    p = wait_status(base, body["pipeline_id"], {"completed"})
    snap = call(base, "/api/jobs")[1]
    statuses = {j["worker"]: j["status"] for j in snap["jobs"] if j["id"] in p["job_ids"]}
    assert statuses["report"] == "completed" and statuses["model_review"] == "blocked"
    code, rep = call(base, f"/api/reports/{body['pipeline_id']}")
    assert code == 200 and rep["report_markdown"].startswith("# Research job report")
    assert call(base, "/api/reports/..%2F..%2Fsecret")[0] == 404
    assert call(base, "/api/reports/nope")[0] == 404


def test_repeated_clicks_do_not_duplicate_work(setup, monkeypatch):
    start, _, _ = setup
    gate = threading.Event()
    monkeypatch.setattr(jobs, "STEP_HOOK", lambda w: gate.wait(10) if w == "ingest" else None)
    base = start()
    first = call(base, "/api/pipelines", {"experiment": EXPS[0]})[1]
    wait_status(base, first["pipeline_id"], {"running"})
    for _ in range(5):
        again = call(base, "/api/pipelines", {"experiment": EXPS[0]})
        assert again[0] == 200 and again[1]["created"] is False and again[1]["pipeline_id"] == first["pipeline_id"]
    gate.set()
    wait_status(base, first["pipeline_id"], {"completed"})
    later = call(base, "/api/pipelines", {"experiment": EXPS[0]})[1]        # new pipeline reuses results
    p = wait_status(base, later["pipeline_id"], {"completed"})
    snap = call(base, "/api/jobs")[1]
    assert len(snap["pipelines"]) == 2
    assert sum(j["status"] == "completed" for j in snap["jobs"]) == 5        # no duplicate completed work
    assert set(p["job_ids"]) <= {j["id"] for j in snap["jobs"]}


def test_cancel_running_pipeline_keeps_completed_evidence(setup, monkeypatch):
    start, _, _ = setup
    gate = threading.Event()
    monkeypatch.setattr(jobs, "STEP_HOOK", lambda w: gate.wait(10) if w == "reconcile" else None)
    base = start()
    pid = call(base, "/api/pipelines", {"experiment": EXPS[1]})[1]["pipeline_id"]
    deadline = time.time() + 10
    while time.time() < deadline:                                       # wait until reconcile is running
        js = {j["worker"]: j["status"] for j in call(base, "/api/jobs")[1]["jobs"]}
        if js.get("reconcile") == "running":
            break
        time.sleep(0.05)
    code, res = call(base, f"/api/pipelines/{pid}/cancel", {})
    assert code == 200 and res["result"] == "cancel_requested"
    p = next(p for p in call(base, "/api/jobs")[1]["pipelines"] if p["id"] == pid)
    assert p["status"] == "running" and p["cancel_requested"] is True    # requested, not yet completed
    gate.set()
    p = wait_status(base, pid, {"cancelled"})
    js = {j["worker"]: j for j in call(base, "/api/jobs")[1]["jobs"] if j["id"] in p["job_ids"]}
    assert js["ingest"]["status"] == "completed" and js["ingest"]["outputs"]   # evidence kept
    assert js["reconcile"]["status"] == "completed"                          # the running step finished
    assert all(js[w]["status"] == "cancelled" for w in ("analysis", "rule_checks", "model_review", "report"))
    assert call(base, f"/api/reports/{pid}")[0] == 404
    assert call(base, "/api/pipelines/nope/cancel", {})[0] == 404


def test_cancel_queued_pipeline_immediately(setup):
    start, _, _ = setup
    base = start(run_jobs=False)
    pid = call(base, "/api/pipelines", {"experiment": EXPS[1]})[1]["pipeline_id"]
    assert call(base, f"/api/pipelines/{pid}/cancel", {})[1]["result"] == "cancelled"
    snap = call(base, "/api/jobs")[1]
    assert next(p for p in snap["pipelines"] if p["id"] == pid)["status"] == "cancelled"
    assert all(j["status"] == "cancelled" for j in snap["jobs"])


def test_restart_marks_interrupted_work_failed_not_successful(setup):
    start, db, research = setup
    store = jobs.JobStore(db)
    pid, _ = jobs.plan_pipeline(EXPS[1], store, research)
    p = store.pipeline(pid)
    store.db.execute("UPDATE pipelines SET status='running' WHERE id=?", (pid,))
    store.db.execute("UPDATE jobs SET status='running' WHERE id=?", (p["job_ids"][0],))
    store.db.commit()
    store.close()                                                      # "process died" here
    base = start()                                                     # restart: runner recovers
    p = wait_status(base, pid, {"failed"})
    assert "interrupted" in p["error"]
    snap = call(base, "/api/jobs")[1]
    js = {j["id"]: j for j in snap["jobs"]}
    assert js[p["job_ids"][0]]["status"] == "failed" and "interrupted" in js[p["job_ids"][0]]["error"]
    assert all(js[j]["status"] == "cancelled" for j in p["job_ids"][1:])
    assert not any(j["status"] == "completed" for j in snap["jobs"])


def test_dashboard_records_match_database(setup):
    start, db, _ = setup
    base = start()
    pid = call(base, "/api/pipelines", {"experiment": EXPS[0]})[1]["pipeline_id"]
    wait_status(base, pid, {"completed"})
    api = call(base, "/api/jobs")[1]
    store = jobs.JobStore(db)
    try:
        rows = store.db.execute("SELECT id, status, error FROM jobs ORDER BY rowid").fetchall()
    finally:
        store.close()
    assert [(j["id"], j["status"], j["error"]) for j in api["jobs"]] == [tuple(r) for r in rows]


def test_simultaneous_start_requests_create_one_pipeline(setup):
    """Regression: the active-pipeline check and the insert share one write transaction."""
    start, db, _ = setup
    base = start(run_jobs=False)                                       # stays queued: nothing finishes
    barrier = threading.Barrier(8)
    results = []

    def click():
        barrier.wait()
        results.append(call(base, "/api/pipelines", {"experiment": EXPS[1]}))

    threads = [threading.Thread(target=click) for _ in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert sorted(c for c, _ in results) == [200] * 7 + [201]
    assert len({b["pipeline_id"] for _, b in results}) == 1
    snap = call(base, "/api/jobs")[1]
    assert len(snap["pipelines"]) == 1 and len(snap["jobs"]) == 6
