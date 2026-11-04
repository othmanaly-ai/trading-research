"""Research-job pipeline over copies of the real experiment artifacts (temp store and dirs)."""

import json
import shutil
import sqlite3
import threading
import urllib.request

import pytest

from trading import jobs

EXPS = ("001_intraday_momentum", "002_opening_range_breakout")


@pytest.fixture
def env(tmp_path, monkeypatch):
    research = tmp_path / "research"
    for e in EXPS:
        shutil.copytree(jobs.RESEARCH_DIR / e, research / e)
    monkeypatch.setattr(jobs, "REPORT_DIR", tmp_path / "reports")
    store = jobs.JobStore(tmp_path / "jobs.sqlite")
    yield store, research
    store.close()


def statuses(result):
    return {k.split(":")[1]: v for k, v in result["jobs"].items()}


def test_end_to_end_on_real_artifacts(env):
    store, research = env
    for e in EXPS:
        r = jobs.run_pipeline(e, store, research, env={})
        st = statuses(r)
        assert st == {"ingest": "completed", "reconcile": "completed", "analysis": "completed",
                      "rule_checks": "completed", "model_review": "blocked", "report": "completed"}
        rec = next(j for j in store.snapshot()["jobs"] if j["worker"] == "reconcile" and j["experiment"] == e)
        assert rec["outputs"]["reconciled"] is True and rec["outputs"]["discrepancies"] == []
        assert rec["started_utc"] and rec["finished_utc"] and rec["evidence"]["checks"]


def test_model_review_blocked_without_key_or_authorization(env):
    store, research = env
    jobs.run_pipeline(EXPS[1], store, research, env={})
    mr = next(j for j in store.snapshot()["jobs"] if j["worker"] == "model_review")
    assert mr["status"] == "blocked" and "ANTHROPIC_API_KEY is not set" in mr["error"] and mr["outputs"] is None
    jobs.run_pipeline(EXPS[1], store, research, env={"ANTHROPIC_API_KEY": "x"})
    mr2 = [j for j in store.snapshot()["jobs"] if j["worker"] == "model_review"][-1]
    assert mr2["status"] == "blocked" and "not authorized" in mr2["error"] and mr2["outputs"] is None


def test_missing_artifact_fails_ingest_and_blocks_downstream(env):
    store, research = env
    run = json.loads((research / EXPS[1] / "STATUS.json").read_text())["development_run_id"]
    (research / EXPS[1] / "runs" / f"{run}.json").unlink()
    st = statuses(jobs.run_pipeline(EXPS[1], store, research, env={}))
    assert st["ingest"] == "failed" and st["reconcile"] == "blocked" and st["report"] == "blocked"
    err = next(j for j in store.snapshot()["jobs"] if j["worker"] == "ingest")["error"]
    assert "missing" in err


def test_corrupt_artifact_fails_then_recovers_with_new_attempt(env):
    store, research = env
    status_path = research / EXPS[0] / "STATUS.json"
    good = status_path.read_text()
    status_path.write_text("{not json")
    assert statuses(jobs.run_pipeline(EXPS[0], store, research, env={}))["ingest"] == "failed"
    status_path.write_text(good)
    assert statuses(jobs.run_pipeline(EXPS[0], store, research, env={}))["report"] == "completed"
    ingests = [j for j in store.snapshot()["jobs"] if j["worker"] == "ingest"]
    assert [j["status"] for j in ingests] == ["failed", "completed"]       # failure record preserved


def test_retry_and_restart_never_duplicate_completed_jobs(env):
    store, research = env
    jobs.run_pipeline(EXPS[1], store, research, env={})
    before = sum(j["status"] == "completed" for j in store.snapshot()["jobs"])
    jobs.run_pipeline(EXPS[1], store, research, env={})                     # retry
    store.db.execute("UPDATE jobs SET status='running' WHERE worker='model_review'")   # simulated crash
    store.db.commit()
    assert store.recover_interrupted() >= 1
    jobs.run_pipeline(EXPS[1], store, research, env={})                     # restart
    after = sum(j["status"] == "completed" for j in store.snapshot()["jobs"])
    assert after == before
    interrupted = [j for j in store.snapshot()["jobs"] if j["error"] and "interrupted" in j["error"]]
    assert interrupted
    row = store.snapshot()["jobs"][0]
    with pytest.raises(sqlite3.IntegrityError):                             # database-level guarantee
        store.db.execute("INSERT INTO jobs (id, worker, experiment, input_key, status) VALUES (?,?,?,?,?)",
                         ("dup", row["worker"], row["experiment"], row["input_key"], "completed"))


def test_reconcile_detects_tampered_record(env):
    store, research = env
    status_path = research / EXPS[1] / "STATUS.json"
    s = json.loads(status_path.read_text())
    s["failed_rules"] = ["D1"]                                              # misreported
    status_path.write_text(json.dumps(s))
    jobs.run_pipeline(EXPS[1], store, research, env={})
    rec = next(j for j in store.snapshot()["jobs"] if j["worker"] == "reconcile")
    assert rec["outputs"]["reconciled"] is False
    assert any("STATUS" in d["check"] for d in rec["outputs"]["discrepancies"])


def test_cancel_only_queued_jobs(env):
    store, _ = env
    jid = store.create("p", "ingest", "deterministic", "x", "k" * 64, {})
    assert store.cancel(jid) and store.get(jid)["status"] == "cancelled"
    assert not store.cancel(jid)


def test_dashboard_endpoint_matches_store(env, monkeypatch, tmp_path):
    store, research = env
    jobs.run_pipeline(EXPS[1], store, research, env={})
    from trading.dashboard import server
    monkeypatch.setattr(server, "JOBS_DB", tmp_path / "jobs.sqlite")
    httpd, ctrl, stop = server.create_server(None, 0, speed=3600)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/api/jobs"
        with urllib.request.urlopen(url, timeout=10) as r:
            body = json.loads(r.read())
        assert [(j["id"], j["status"]) for j in body["jobs"]] == \
            [(j["id"], j["status"]) for j in store.snapshot()["jobs"]]
        assert body["mode_label"] == "REAL RESEARCH JOBS (not demo)"
    finally:
        stop.set()
        httpd.shutdown()
        httpd.server_close()


def test_api_and_store_emit_strict_json(env, monkeypatch, tmp_path):
    """Regression: NaN in saved reports made /api/jobs invalid JSON for browsers."""
    store, research = env
    jobs.run_pipeline(EXPS[1], store, research, env={})
    def reject(token):
        raise ValueError(f"non-strict JSON constant {token}")
    for row in store.db.execute("SELECT outputs_json, evidence_json FROM jobs"):
        for text in row:
            if text:
                json.loads(text, parse_constant=reject)
    from trading.dashboard import server
    monkeypatch.setattr(server, "JOBS_DB", tmp_path / "jobs.sqlite")
    httpd, ctrl, stop = server.create_server(None, 0, speed=3600)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        for path in ("/api/jobs", "/api/research", "/api/meta", "/api/snapshot"):
            with urllib.request.urlopen(base + path, timeout=10) as r:
                json.loads(r.read(), parse_constant=reject)
    finally:
        stop.set()
        httpd.shutdown()
        httpd.server_close()
