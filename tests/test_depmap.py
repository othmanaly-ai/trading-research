"""Dependency-and-health map. SYNTHETIC fixtures only: no real monitor, job store or network.
Failures are injected into fixture inputs, never into the real monitor."""

from datetime import datetime, timedelta, timezone

from trading.dashboard import depmap
from trading.jobs import UNIMPLEMENTED_ROLES, WORKERS

NOW = datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc)      # a session time (market open in fixtures)
iso = lambda dt: dt.isoformat(timespec="seconds")
WORKER_DEFS = [{"worker": w, "kind": k, "version": v, "depends_on": d} for w, k, v, d in WORKERS]


def jobs_fixture(status="completed", reused=False, failed_step=None):
    """One pipeline over the six declared steps; optionally reusing earlier results."""
    jobs, ids = [], []
    for w in WORKERS:
        name, kind = w[0], w[1]
        st = "skipped" if kind == "model" else status
        if failed_step == name:
            st = "failed"
        pid = "p-old" if reused and name != "report" else "p-new"
        jid = f"{pid}:{name}"
        jobs.append({"id": jid, "pipeline_id": pid, "worker": name, "kind": kind, "status": st,
                     "created_utc": iso(NOW - timedelta(hours=2)), "started_utc": iso(NOW - timedelta(hours=2)),
                     "finished_utc": iso(NOW - timedelta(hours=1, minutes=50)), "error": "SYNTHETIC failure" if st == "failed" else None})
        ids.append(jid)
    return {"pipelines": [{"id": "p-new", "status": "completed", "created_utc": iso(NOW - timedelta(hours=2)), "job_ids": ids}],
            "jobs": jobs, "workers": WORKER_DEFS}


def healthy(**over):
    last_ok = iso(NOW - timedelta(seconds=40))
    mon = {
        "db_exists": True,
        "status": {"market": {"open": True}, "desired": "running",
                   "worker": {"pid": 101, "alive": True, "state": "running", "effective_state": "running",
                              "last_success_utc": last_ok, "heartbeat_utc": iso(NOW), "detail": "poll ok"},
                   "symbols": [{"symbol": s, "freshness": "FRESH"} for s in ("SPY", "QQQ", "IWM")]},
        "events": [], "last_received_utc": last_ok, "last_spawn_utc": iso(NOW - timedelta(hours=3)),
        "q_last_ok": {"started_utc": iso(NOW - timedelta(minutes=4)), "kind": "cycle", "status": "ok"},
        "q_last": {"started_utc": iso(NOW - timedelta(minutes=4)), "kind": "cycle", "status": "ok"},
        "q_report": {"session_date": "2026-11-05", "version": 1, "status": "finalized", "created_utc": iso(NOW - timedelta(hours=17))},
        "health": {"state": "ok", "detail": "up to date (SYNTHETIC)", "last_success_utc": iso(NOW - timedelta(minutes=4))},
    }
    inputs = {"monitor": mon, "jobs": jobs_fixture(), "review": {"available": False, "state": "OPTIONAL / DISABLED", "revoked": True},
              "research": {"experiments": [{"experiment": "001", "state": "FAILED_DEVELOPMENT"}], "history": {"usable_sessions": 1511, "retrieved_utc": "x"}},
              "unimplemented": UNIMPLEMENTED_ROLES}
    inputs.update(over)
    return inputs


def by_id(m):
    return {n["id"]: n for n in m["nodes"]}


def test_healthy_dependencies_are_ok_and_not_blocked():
    m = depmap.build_map(healthy(), NOW)
    n = by_id(m)
    for k in ("alpaca_iex", "alpaca_sip", "monitor_worker", "quality", "monitor_db", "daily_reports", "report"):
        assert n[k]["status"] == "OK", (k, n[k])
        assert n[k]["why_blocked"] == []
    assert n["monitor_worker"]["upstream"] == ["alpaca_iex", "supervisor"]
    assert "monitor_db" in n["monitor_worker"]["downstream"]
    e = {(x["from"], x["to"]): x for x in m["edges"]}
    rec = e[("alpaca_iex", "monitor_worker")]["recorded"]
    assert rec and not rec["historical"] and "worker record" in rec["evidence"]


def test_upstream_failure_traces_to_refused_access_with_evidence_and_impact():
    inp = healthy()
    w = inp["monitor"]["status"]["worker"]
    w.update(state="refused", effective_state="refused")
    inp["monitor"]["events"] = [{"ts_utc": iso(NOW), "level": "error", "kind": "refused",
                                 "message": "access refused (HTTP 403) for feed iex: SYNTHETIC"}]
    n = by_id(depmap.build_map(inp, NOW))
    assert n["alpaca_iex"]["status"] == "FAILED" and "HTTP 403" in n["alpaca_iex"]["evidence"][0]
    assert n["monitor_worker"]["status"] == "FAILED"
    causes = n["monitor_worker"]["why_blocked"]
    assert [c["node"] for c in causes] == ["monitor_worker", "alpaca_iex"]
    assert causes[1]["depth"] == 1 and "HTTP 403" in causes[1]["evidence"][0]
    impacted = {i["node"] for i in n["alpaca_iex"]["impact"]}
    assert {"monitor_worker", "monitor_db", "quality", "daily_reports", "view_monitor"} <= impacted
    assert "Alpaca paper keys" in n["alpaca_iex"]["next_action"]


def test_stale_data_while_market_open():
    inp = healthy()
    old = iso(NOW - timedelta(minutes=20))
    inp["monitor"]["status"]["worker"]["last_success_utc"] = old
    inp["monitor"]["status"]["symbols"] = [{"symbol": "SPY", "freshness": "STALE"}]
    n = by_id(depmap.build_map(inp, NOW))
    assert n["alpaca_iex"]["status"] == "STALE" and "1200 s ago" in n["alpaca_iex"]["evidence"][0]
    assert n["monitor_worker"]["status"] == "STALE" and "SPY" in n["monitor_worker"]["evidence"][0]


def test_market_closed_is_idle_not_blocked_and_no_fresh_handoff():
    inp = healthy()
    inp["monitor"]["status"]["market"] = {"open": False}
    inp["monitor"]["status"]["worker"].update(effective_state="market_closed", last_success_utc=iso(NOW - timedelta(hours=18)))
    m = depmap.build_map(inp, NOW)
    n = by_id(m)
    assert n["alpaca_iex"]["status"] == "IDLE" and n["monitor_worker"]["status"] == "IDLE"
    assert n["monitor_worker"]["why_blocked"] == []
    rec = {(x["from"], x["to"]): x for x in m["edges"]}[("alpaca_iex", "monitor_worker")]["recorded"]
    assert rec["historical"] is True                          # old activity is never shown as current


def test_missing_evidence_is_unknown_not_guessed():
    m = depmap.build_map({"jobs": {"pipelines": [], "jobs": [], "workers": WORKER_DEFS}}, NOW)
    n = by_id(m)
    for k in ("alpaca_iex", "alpaca_sip", "monitor_worker", "quality", "monitor_db", "daily_reports", "ingest", "report"):
        assert n[k]["status"] == "UNKNOWN", k
    causes = n["report"]["why_blocked"]
    assert causes and all("UNKNOWN" in c["evidence"][0] for c in causes)
    assert not any(e["recorded"] for e in m["edges"])        # no record, no handoff


def test_disabled_optional_review_is_not_a_blocker():
    n = by_id(depmap.build_map(healthy(), NOW))
    mr = n["model_review"]
    assert mr["status"] == "DISABLED" and mr["mode"].startswith("disabled") and "revoked" in mr["evidence"][0]
    assert mr["why_blocked"] == [] and mr["impact"] == []
    assert "re-authorizes" in mr["next_action"]
    assert "model_review" not in n["report"]["upstream"]      # the report does not depend on it


def test_cached_job_results_are_labelled_reused():
    n = by_id(depmap.build_map(healthy(jobs=jobs_fixture(reused=True)), NOW))
    assert n["ingest"]["mode"] == "cached / reused result" and n["ingest"]["evidence"][0].startswith("Reused")
    assert n["report"]["mode"].startswith("manually started")


def test_failed_step_blocks_dependents_as_impact_only():
    n = by_id(depmap.build_map(healthy(jobs=jobs_fixture(failed_step="analysis")), NOW))
    assert n["analysis"]["status"] == "FAILED" and "SYNTHETIC failure" in n["analysis"]["evidence"][0]
    impacted = {i["node"]: i for i in n["analysis"]["impact"]}
    assert {"rule_checks", "report", "view_jobs"} <= set(impacted)
    assert impacted["report"]["status"] == "OK"               # impact is dependency reach, not proof of failure


def test_recovery_keeps_edges_unique_and_handoff_ids_stable():
    bad = healthy()
    bad["monitor"]["status"]["worker"].update(state="refused", effective_state="refused")
    m1 = depmap.build_map(bad, NOW)
    m2 = depmap.build_map(healthy(), NOW + timedelta(minutes=1))
    m3 = depmap.build_map(healthy(), NOW + timedelta(minutes=2))
    for m in (m1, m2, m3):
        keys = [(e["from"], e["to"]) for e in m["edges"]]
        assert len(keys) == len(set(keys))                     # no duplicate links
    ids2 = {(e["from"], e["to"]): e["recorded"]["event_id"] for e in m2["edges"] if e["recorded"]}
    ids3 = {(e["from"], e["to"]): e["recorded"]["event_id"] for e in m3["edges"] if e["recorded"]}
    assert ids2 == ids3                                        # same records -> same ids -> no repeated animation
    assert by_id(m2)["alpaca_iex"]["status"] == "OK"


def test_no_execution_path_and_proposed_edges_carry_no_status():
    m = depmap.build_map(healthy(), NOW)
    ids = {n["id"] for n in m["nodes"]}
    assert not any(k in i for i in ids for k in ("order", "execution", "trade"))
    assert "proposed_broker_reconciliation" in ids
    assert not any("proposed_broker_reconciliation" in (e["from"], e["to"]) for e in m["edges"])
    prop = [e for e in m["edges"] if e["kinds"] == ["proposed"]]
    assert prop and all(e["recorded"] is None for e in prop)
    n = by_id(m)
    assert "proposed_news_analysis" not in n["analysis"]["upstream"]


def test_static_code_relations_are_separate_from_status():
    graph = {"pairs": {("trading/alpaca_client.py", "trading/monitor/worker.py"): 3}, "source": "SYNTHETIC graph", "built_at_commit": "abc"}
    m = depmap.build_map(healthy(), NOW, graph)
    e = {(x["from"], x["to"]): x for x in m["edges"]}
    assert e[("alpaca_iex", "monitor_worker")]["static_code"]["relations"] == 3
    assert e[("ingest", "reconcile")]["static_code"]["relations"] is None      # same file: not applicable
    unknown = depmap.build_map({}, NOW, graph)
    assert by_id(unknown)["monitor_worker"]["status"] == "UNKNOWN"             # code structure never implies success


def test_collect_is_read_only_with_isolated_stores(tmp_path):
    from trading.monitor import store as mst
    m = depmap.collect(NOW, jobs_db=tmp_path / "missing.sqlite")
    assert not mst.DB_PATH.exists()                            # no monitoring store created by reading
    assert not (tmp_path / "missing.sqlite").exists()
    assert by_id(m)["monitor_worker"]["status"] == "UNKNOWN"


def test_ok_component_with_failed_upstream_is_not_called_blocked():
    inp = healthy()
    inp["monitor"]["status"]["worker"].update(state="refused", effective_state="refused")
    n = by_id(depmap.build_map(inp, NOW))
    assert n["quality"]["status"] == "OK" and n["quality"]["why_blocked"] == []
    assert [c["node"] for c in n["quality"]["upstream_issues"]] == ["alpaca_iex"]     # reported as an upstream issue
    assert n["model_review"]["upstream_issues"] == []                                # disabled: nothing to report
