"""Read-only dependency-and-health map.

Three kinds of knowledge, never mixed:
  * DECLARED  - implementation dependencies taken from this codebase (file and symbol given as provenance)
  * RECORDED  - handoffs observed in runtime records (table and timestamp given as provenance)
  * PROPOSED  - connections listed as unimplemented in trading/jobs.py (UNIMPLEMENTED_ROLES)
Graphify's static code relationships are attached separately as `static_code` evidence; they never
set a status. Statuses come only from runtime records; with no record the status is UNKNOWN.

Nothing here starts, stops or changes anything. `collect()` only reads existing stores.
There is no execution system, so no order or trading node exists in the map.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = PROJECT_ROOT / "graphify-out" / "graph.json"

BAD = ("FAILED", "STALE", "UNKNOWN")
STALE_AFTER_S = 300          # market open, no successful poll for 5 minutes
RECENT_S = 3600              # recorded handoffs older than this are labelled historical

# ------------------------------------------------------------------ declared architecture
# (id, label, group, work mode, source files)
NODES = [
    ("alpaca_iex", "Alpaca market data · IEX (live)", "external", "external service", ["trading/alpaca_client.py"]),
    ("alpaca_sip", "Alpaca market data · SIP (15-min delayed)", "external", "external service", ["trading/alpaca_client.py"]),
    ("supervisor", "Supervisor (city server)", "collection", "continuous while the city server runs", ["trading/monitor/control.py"]),
    ("monitor_worker", "Market collection worker", "collection", "continuous while the city server runs", ["trading/monitor/worker.py"]),
    ("quality", "Delayed-SIP data-quality comparison", "quality", "continuous (inside the worker)", ["trading/monitor/quality.py"]),
    ("monitor_db", "Monitoring store", "storage", "stored evidence", ["trading/monitor/store.py"]),
    ("daily_reports", "Daily evidence reports", "storage", "stored evidence (amend-only)", ["trading/monitor/reliability.py"]),
    ("history", "Development-period history (data/history)", "storage", "stored research data (historical)", ["trading/history.py"]),
    ("experiments", "Experiments 001-002 (closed)", "research", "closed research records", ["trading/experiment.py", "trading/evaluate.py"]),
    ("view_monitor", "Market monitor view", "views", "read on request", ["trading/dashboard/server.py", "dashboard/web/src/components/MonitorView.tsx"]),
    ("view_jobs", "Research jobs view", "views", "read on request", ["trading/dashboard/server.py", "dashboard/web/src/components/JobsView.tsx"]),
]
# (from, to, provenance)   from -> to means "to depends on from" (data flows from -> to)
EDGES = [
    ("alpaca_iex", "monitor_worker", "trading/monitor/worker.py: ReadOnlyAlpacaClient.get_bars_multi(feed='iex')"),
    ("supervisor", "monitor_worker", "trading/monitor/control.py: Supervisor.check_once -> launch()"),
    ("monitor_worker", "monitor_db", "trading/monitor/store.py: MonitorStore.insert_bars"),
    ("alpaca_sip", "quality", "trading/monitor/quality.py: QualityChecker.compare_window (feed='sip')"),
    ("alpaca_iex", "quality", "trading/monitor/quality.py: QualityChecker.compare_window (IEX re-fetch)"),
    ("monitor_db", "quality", "trading/monitor/quality.py: live bars read for comparison"),
    ("quality", "daily_reports", "trading/monitor/quality.py: QualityChecker.finalize -> reliability.daily_report"),
    ("monitor_db", "view_monitor", "trading/dashboard/server.py: /api/monitor, /api/monitor/sessions"),
    ("daily_reports", "view_monitor", "trading/dashboard/server.py: /api/monitor/report"),
    ("history", "experiments", "trading/evaluate.py: development runs read data/history"),
    ("experiments", "ingest", "trading/jobs.py: ingest reads EXPECTED_ARTIFACTS of saved experiments"),
    ("report", "view_jobs", "trading/dashboard/server.py: /api/reports/<id>"),
]
ACTIONS = {
    ("external", "FAILED"): "Owner: check the Alpaca paper keys and data subscription in .env (never in chat). The worker retries by itself after its backoff.",
    ("external", "UNKNOWN"): "No request recorded yet. Start monitoring from Market monitor → Start (the city server must be running).",
    ("external", "STALE"): "Check Market monitor events for request errors; the worker retries automatically.",
    ("monitor_worker", "FAILED"): "Market monitor → Start, or start the city server; the supervisor relaunches a crashed worker (max 6 per hour).",
    ("monitor_worker", "STALE"): "Check Market monitor events; if the worker is not responding, Market monitor → Start.",
    ("quality", "FAILED"): "Waits and retries automatically (see backoff); access refusals are listed in the daily report.",
    ("job", "FAILED"): "Read the failed job's error in Research jobs, fix its cause, then start the predefined pipeline again.",
    ("job", "UNKNOWN"): "No job record yet: start the predefined pipeline from Research jobs.",
    ("supervisor", "FAILED"): "Wait for the hourly launch limit to clear, or restart the city server outside market hours.",
}


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _age(ts: str | None, now: datetime) -> float | None:
    t = _parse(ts)
    return None if t is None else (now - t).total_seconds()


def static_relations(path: Path = GRAPH_PATH) -> dict | None:
    """File-pair counts of static code relations from Graphify (code structure only, no runtime meaning)."""
    if not path.is_file():
        return None
    try:
        g = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    files = {n["id"]: n.get("source_file") for n in g.get("nodes", [])}
    pairs: dict[tuple[str, str], int] = {}
    for link in g.get("links", []):
        a, b = files.get(link.get("source")), files.get(link.get("target"))
        if a and b and a != b:
            key = tuple(sorted((a, b)))
            pairs[key] = pairs.get(key, 0) + 1
    return {"pairs": pairs, "built_at_commit": g.get("built_at_commit"), "source": "graphify-out/graph.json"}


# ------------------------------------------------------------------ status from records

def _node(nid, label, group, mode, files, status, evidence, last_ok=None, freshness=None):
    return {"id": nid, "label": label, "group": group, "mode": mode, "files": files, "status": status,
            "evidence": evidence, "last_success_utc": last_ok, "freshness": freshness}


def build_map(inputs: dict, now: datetime | None = None, graph: dict | None = None) -> dict:
    """Pure function: runtime inputs -> nodes, edges, traces. `inputs` keys (each may be missing):
    monitor{status, events, last_received_utc, last_spawn_utc, q_last_ok, q_last, q_report, health, db_exists},
    jobs{pipelines, jobs, workers}, review{available, state, revoked}, research{experiments, history}."""
    now = now or datetime.now(timezone.utc)
    mon = inputs.get("monitor") or {}
    st = mon.get("status") or {}
    worker = st.get("worker") or {}
    market = st.get("market") or {}
    events = mon.get("events") or []
    defs = {n[0]: n for n in NODES}
    nodes: dict[str, dict] = {}

    def add(nid, status, evidence, last_ok=None, freshness=None, **extra):
        _, label, group, mode, files = defs[nid]
        nodes[nid] = {**_node(nid, label, group, mode, files, status, evidence, last_ok, freshness), **extra}

    open_ = bool(market.get("open"))
    last_ok = worker.get("last_success_utc")
    refusals = [e for e in events if e.get("level") == "error" and ("HTTP 401" in e.get("message", "") or "HTTP 403" in e.get("message", ""))
                and (not last_ok or e.get("ts_utc", "") > last_ok)]
    # --- IEX (live)
    if not st:
        add("alpaca_iex", "UNKNOWN", ["No monitoring record available."])
    elif worker.get("state") == "refused" or refusals:
        ev = refusals[0] if refusals else {"ts_utc": worker.get("heartbeat_utc"), "message": worker.get("detail", "")}
        add("alpaca_iex", "FAILED", [f"{ev.get('ts_utc')}: {ev.get('message')} (monitor events)"], last_ok)
    elif last_ok:
        age = _age(last_ok, now)
        if open_ and age is not None and age > STALE_AFTER_S:
            add("alpaca_iex", "STALE", [f"Market open but last successful IEX poll was {int(age)} s ago ({last_ok})."], last_ok, "stale")
        else:
            add("alpaca_iex", "OK" if open_ else "IDLE",
                [f"Last successful IEX poll {last_ok}." + ("" if open_ else " Not requested while the market is closed.")], last_ok,
                "current" if open_ else "market closed")
    else:
        add("alpaca_iex", "UNKNOWN", ["No successful IEX request recorded."])
    # --- SIP (delayed)
    q_last, q_ok = mon.get("q_last"), mon.get("q_last_ok")
    if not q_last:
        add("alpaca_sip", "UNKNOWN", ["No comparison request recorded."])
    elif q_last.get("status") == "access_failure":
        add("alpaca_sip", "FAILED", [f"{q_last.get('started_utc')}: access refused (HTTP {q_last.get('http_status')}): {q_last.get('error')} (q_runs)"],
            q_ok and q_ok.get("started_utc"))
    elif q_last.get("status") == "error":
        add("alpaca_sip", "FAILED", [f"{q_last.get('started_utc')}: request failed: {q_last.get('error')} (q_runs)"], q_ok and q_ok.get("started_utc"))
    else:
        add("alpaca_sip", "OK", [f"Last comparison request succeeded {q_last.get('started_utc')} (q_runs)."], q_last.get("started_utc"))
    # --- supervisor
    limit = [e for e in events if e.get("kind") == "supervisor" and e.get("level") == "error" and (_age(e.get("ts_utc"), now) or 1e9) < 900]
    if not st:
        add("supervisor", "UNKNOWN", ["No monitoring record available."])
    elif limit and not worker.get("alive"):
        add("supervisor", "FAILED", [f"{limit[0].get('ts_utc')}: {limit[0].get('message')} (monitor events)"], mon.get("last_spawn_utc"))
    else:
        add("supervisor", "OK", ["City server is responding (this map was served by it)."] +
            ([f"Last worker launch {mon.get('last_spawn_utc')} (spawns)."] if mon.get("last_spawn_utc") else []), mon.get("last_spawn_utc"))
    # --- collection worker
    eff = worker.get("effective_state")
    if not st or eff is None:
        add("monitor_worker", "UNKNOWN", ["No worker record."])
    elif eff in ("disconnected", "error", "refused") or (st.get("desired") == "running" and not worker.get("alive")):
        add("monitor_worker", "FAILED", [f"Worker state {eff}; heartbeat {worker.get('heartbeat_utc')}; {worker.get('detail', '')} (worker record)"], last_ok)
    elif eff == "running":
        stale = [s["symbol"] for s in st.get("symbols", []) if s.get("freshness") == "STALE"]
        if stale:
            add("monitor_worker", "STALE", [f"Running, but data is stale for {', '.join(stale)} (freshness from bar timestamps)."], last_ok, "stale")
        else:
            add("monitor_worker", "OK", [f"Running (pid {worker.get('pid')}); last successful poll {last_ok}."], last_ok, "current")
    else:
        why = {"market_closed": "market closed: no polling until the next open", "paused": "paused by request",
               "stopped": "stopped by request"}.get(eff, eff)
        add("monitor_worker", "IDLE", [f"Worker {why} (worker record); last successful poll {last_ok}."], last_ok, eff)
    # --- quality comparison
    h = mon.get("health")
    if not h:
        add("quality", "UNKNOWN", ["No comparison health record."])
    elif h.get("state") in ("access_failure", "error"):
        add("quality", "FAILED", [f"{h.get('updated_utc')}: {h.get('detail')} (q_health)"], h.get("last_success_utc"))
    elif h.get("state") == "backoff":
        add("quality", "STALE", [f"Backing off until {h.get('backoff_until_utc')}: {h.get('detail')} (q_health)"], h.get("last_success_utc"))
    else:
        add("quality", "OK", [f"{h.get('detail')} (q_health)"], h.get("last_success_utc"))
    # --- stored evidence
    if mon.get("db_exists"):
        add("monitor_db", "OK", [f"Store present; newest live bar stored {mon.get('last_received_utc') or 'never'} (bars)."], mon.get("last_received_utc"))
    else:
        add("monitor_db", "UNKNOWN", ["Monitoring store not found."])
    rep = mon.get("q_report")
    if not rep:
        add("daily_reports", "UNKNOWN", ["No stored daily report."])
    elif rep.get("status") == "incomplete":
        add("daily_reports", "STALE", [f"Latest report {rep.get('session_date')} v{rep.get('version')} is INCOMPLETE (stored {rep.get('created_utc')})."], rep.get("created_utc"))
    else:
        add("daily_reports", "OK", [f"Latest report {rep.get('session_date')} v{rep.get('version')} {rep.get('status')} (stored {rep.get('created_utc')}; q_reports)."], rep.get("created_utc"))
    # --- research
    res = inputs.get("research") or {}
    hist = res.get("history")
    add("history", "CLOSED" if hist else "UNKNOWN",
        [f"Manifest present: {hist.get('usable_sessions')} usable development sessions, retrieved {hist.get('retrieved_utc')} (historical)."] if hist else ["No history manifest found."],
        hist and hist.get("retrieved_utc"))
    exps = res.get("experiments") or []
    if exps:
        add("experiments", "CLOSED", [f"{e['experiment']}: {e.get('state')} (STATUS.json)" for e in exps])
    else:
        add("experiments", "UNKNOWN", ["No experiment status records."])
    # --- research pipeline steps (declared in trading/jobs.py WORKERS; status from the job store)
    jobs = inputs.get("jobs") or {}
    workers = jobs.get("workers") or []
    pipes = jobs.get("pipelines") or []
    latest = pipes[-1] if pipes else None
    by_id = {j["id"]: j for j in jobs.get("jobs") or []}
    rv = inputs.get("review") or {}
    for w in workers:
        name, kind = w["worker"], w["kind"]
        j = next((by_id[i] for i in (latest or {}).get("job_ids", []) if i in by_id and by_id[i]["worker"] == name), None)
        reused = bool(j and latest and j.get("pipeline_id") != latest["id"])
        mode = ("disabled (optional, paid calls revoked)" if kind == "model" else
                "cached / reused result" if reused else "manually started (predefined pipeline)")
        ev, status = [], "UNKNOWN"
        if kind == "model" and not rv.get("available", False):
            status = "DISABLED"
            ev.append(f"Optional model review: {rv.get('state', 'OPTIONAL / DISABLED')}" + ("; owner authorization revoked" if rv.get("revoked") else "") + " (reviewer readiness).")
            if j:
                ev.append(f"Latest pipeline job: {j['status']} at {j.get('finished_utc') or j.get('created_utc')} (job store).")
        elif not j:
            ev.append("No job record in the latest pipeline.")
        elif j["status"] in ("completed", "skipped"):
            status = "OK"
            ev.append(f"{'Reused' if reused else 'Completed'} {j.get('finished_utc')} (job {j['id']}, pipeline {j.get('pipeline_id')}).")
        elif j["status"] == "running":
            status = "OK"
            ev.append(f"RUNNING since {j.get('started_utc')} (job store).")
        elif j["status"] in ("failed", "blocked"):
            status = "FAILED"
            ev.append(f"{j['status'].upper()} at {j.get('finished_utc') or j.get('created_utc')}: {j.get('error') or 'no error text'} (job {j['id']}).")
        else:
            status = "IDLE"
            ev.append(f"{j['status']} (job store).")
        nodes[name] = _node(name, f"Pipeline step · {name}", "research", mode, ["trading/jobs.py"], status, ev,
                            j and j.get("finished_utc"), "historical" if j and j["status"] != "running" else None)
        nodes[name]["implementation"] = {"deterministic": "deterministic code", "model": "optional model review",
                                         "unimplemented": "not implemented"}.get(kind, kind) + f" v{w.get('version')}"
        nodes[name]["job_status"] = j and j["status"]
    # --- views
    add("view_monitor", "OK", ["Served by the city server on request."])
    add("view_jobs", "OK", ["Served by the city server on request."])
    # --- proposed / unimplemented (from trading/jobs.py UNIMPLEMENTED_ROLES)
    for r in inputs.get("unimplemented") or []:
        rid = "proposed_" + r["role"].replace(" ", "_")
        nodes[rid] = _node(rid, r["role"].capitalize() + " (not implemented)", "proposed", "not implemented",
                           ["trading/jobs.py"], "NOT IMPLEMENTED", [f"{r['status']} (UNIMPLEMENTED_ROLES)"])

    # ------------------------------------------------------------------ edges
    edges: dict[tuple[str, str], dict] = {}

    def edge(a, b, kind, prov):
        if a not in nodes or b not in nodes:
            return
        e = edges.setdefault((a, b), {"from": a, "to": b, "kinds": [], "declared": None, "recorded": None, "proposed": None, "static_code": None})
        if kind not in e["kinds"]:
            e["kinds"].append(kind)
        e[kind] = prov

    for a, b, prov in EDGES:
        edge(a, b, "declared", {"provenance": prov})
    for w in workers:
        for dep in w.get("depends_on", []):
            edge(dep, w["worker"], "declared", {"provenance": f"trading/jobs.py: WORKERS[{w['worker']!r}] depends_on {dep!r}"})
    # proposed connections only where the role says what it would feed
    if "proposed_news_analysis" in nodes and "analysis" in nodes:
        edge("proposed_news_analysis", "analysis", "proposed", {"provenance": "trading/jobs.py UNIMPLEMENTED_ROLES: news analysis (no verified news source)"})
    if "proposed_live_performance_monitoring" in nodes:
        edge("monitor_db", "proposed_live_performance_monitoring", "proposed", {"provenance": "trading/jobs.py UNIMPLEMENTED_ROLES: live performance monitoring (no running service)"})

    def rec(a, b, ts, evidence):
        if ts and (a, b) in edges:
            age = _age(ts, now)
            edge(a, b, "recorded", {"ts_utc": ts, "evidence": evidence, "historical": age is None or age > RECENT_S,
                                    "event_id": f"{a}>{b}@{ts}"})

    rec("alpaca_iex", "monitor_worker", last_ok, "last successful IEX poll (worker record)")
    rec("monitor_worker", "monitor_db", mon.get("last_received_utc"), "newest stored live bar (bars.received_utc)")
    rec("supervisor", "monitor_worker", mon.get("last_spawn_utc"), "last worker launch (spawns)")
    if q_ok:
        rec("alpaca_sip", "quality", q_ok.get("started_utc"), f"last successful comparison run ({q_ok.get('kind')}, q_runs)")
    if rep:
        rec("quality", "daily_reports", rep.get("created_utc"), f"report {rep.get('session_date')} v{rep.get('version')} stored (q_reports)")
    for w in workers:
        j = nodes.get(w["worker"])
        for dep in w.get("depends_on", []):
            d = nodes.get(dep)
            if j and d and j.get("job_status") in ("completed", "running") and d.get("job_status") == "completed":
                rec(dep, w["worker"], j.get("last_success_utc") or (latest or {}).get("created_utc"),
                    f"{w['worker']} consumed {dep}'s completed output (job store)")
    if nodes.get("ingest", {}).get("job_status") == "completed":
        rec("experiments", "ingest", nodes["ingest"].get("last_success_utc"), "ingest read saved experiment artifacts (job store)")
    if nodes.get("report", {}).get("job_status") == "completed":
        rec("report", "view_jobs", nodes["report"].get("last_success_utc"), "report written (job store)")

    if graph:
        for e in edges.values():
            if e["kinds"] == ["proposed"]:
                continue                              # nothing is implemented, so code structure says nothing
            fa, fb = nodes[e["from"]]["files"], nodes[e["to"]]["files"]
            if set(fa) == set(fb):
                e["static_code"] = {"relations": None, "note": f"both sides are in {', '.join(fa)}: a file-level relation does not apply",
                                    "source": graph["source"], "built_at_commit": graph.get("built_at_commit")}
                continue
            n = sum(graph["pairs"].get(tuple(sorted((a, b))), 0) for a in fa for b in fb if a != b)
            e["static_code"] = {"relations": n, "files": [fa, fb], "source": graph["source"], "built_at_commit": graph.get("built_at_commit"),
                                "note": "static code relations between the files (imports/calls); not runtime evidence" if n else
                                        "no static relation found between these files (the dependency may be via data files)"}

    up: dict[str, list[str]] = {k: [] for k in nodes}
    down: dict[str, list[str]] = {k: [] for k in nodes}
    for (a, b), e in edges.items():
        if "proposed" in e["kinds"] and len(e["kinds"]) == 1:
            continue                                  # proposed edges never carry status or blame
        up[b].append(a)
        down[a].append(b)

    for nid, n in nodes.items():
        n["upstream"], n["downstream"] = up[nid], down[nid]
        # "Why blocked?" only for components whose own record is bad; an OK component with a bad
        # upstream gets `upstream_issues` instead (a dependency problem, not proof it is blocked)
        n["why_blocked"] = why_blocked(nid, nodes, up) if n["status"] in BAD else []
        n["upstream_issues"] = [] if n["status"] in BAD or n["status"] in ("DISABLED", "NOT IMPLEMENTED") else             [c for u in up[nid] if nodes[u]["status"] in BAD for c in why_blocked(u, nodes, up, 1)]
        n["impact"] = impact(nid, nodes, down) if n["status"] in BAD else []
        n["next_action"] = next_action(n)
    return {"generated_utc": now.isoformat(timespec="seconds"), "nodes": list(nodes.values()), "edges": list(edges.values()),
            "legend": {"declared": "implementation dependency in code/config (provenance: file and symbol)",
                       "recorded": "handoff observed in runtime records (provenance: table and timestamp)",
                       "proposed": "unimplemented connection listed in trading/jobs.py",
                       "static_code": "Graphify static code relations between the files (code structure only; not runtime evidence)"},
            "no_execution_path": "No order or trading execution system exists, so none is drawn."}


def why_blocked(nid: str, nodes: dict, up: dict, depth: int = 0, seen: set | None = None) -> list[dict]:
    """Supported causes only: this node's own evidence plus upstream nodes whose records are bad.
    Missing evidence is reported as UNKNOWN, never guessed."""
    seen = seen if seen is not None else set()
    if nid in seen or depth > 4:
        return []
    seen.add(nid)
    n = nodes[nid]
    causes: list[dict] = []
    if n["status"] in BAD:
        causes.append({"node": nid, "label": n["label"], "status": n["status"], "depth": depth,
                       "evidence": n["evidence"] if n["status"] != "UNKNOWN" else [f"UNKNOWN: no evidence recorded for {n['label']}."]})
    for u in up.get(nid, []):
        if nodes[u]["status"] in BAD:
            causes += why_blocked(u, nodes, up, depth + 1, seen)
    return causes


def impact(nid: str, nodes: dict, down: dict) -> list[dict]:
    """Directly and transitively dependent components (dependency impact, not proof of failure)."""
    out, queue, seen = [], [(d, 1) for d in down.get(nid, [])], {nid}
    while queue:
        d, depth = queue.pop(0)
        if d in seen:
            continue
        seen.add(d)
        out.append({"node": d, "label": nodes[d]["label"], "depth": depth, "status": nodes[d]["status"]})
        queue += [(x, depth + 1) for x in down.get(d, [])]
    return out


def next_action(n: dict) -> str:
    if n["status"] in ("OK", "CLOSED"):
        return "None needed."
    if n["status"] == "IDLE":
        return "None: idle by design (market closed, paused or stopped by request). Polling resumes at the next open while the computer and server are on."
    if n["status"] == "DISABLED":
        return "None: optional review stays disabled until the owner explicitly re-authorizes paid calls."
    if n["status"] == "NOT IMPLEMENTED":
        return "None: not implemented."
    key = "job" if n["group"] == "research" and n["id"] not in ("experiments",) else n["group"] if n["group"] == "external" else n["id"]
    return ACTIONS.get((key, n["status"])) or ACTIONS.get((n["group"], n["status"])) or \
        ("UNKNOWN: no record to act on yet." if n["status"] == "UNKNOWN" else "See the evidence above; no automatic action is defined.")


# ------------------------------------------------------------------ read-only collection

def collect(now: datetime | None = None, jobs_db: Path | None = None) -> dict:
    """Read existing stores only (no writes, no network, no credentials) and build the map."""
    from trading import jobs as jobs_mod
    from trading.monitor import quality, store as mst
    now = now or datetime.now(timezone.utc)
    inputs: dict = {"unimplemented": jobs_mod.UNIMPLEMENTED_ROLES}
    mon: dict = {"db_exists": mst.DB_PATH.is_file()}
    if mon["db_exists"]:
        store = mst.MonitorStore()
        try:
            quality.ensure_schema(store)
            mon["status"] = store.status(now)
            mon["events"] = store.events(60)
            one = lambda sql: store.db.execute(sql).fetchone()
            r = one("SELECT MAX(received_utc) FROM bars")
            mon["last_received_utc"] = r[0] if r else None
            r = one("SELECT MAX(ts_utc) FROM spawns")
            mon["last_spawn_utc"] = r[0] if r else None
            r = one("SELECT * FROM q_runs WHERE status='ok' ORDER BY id DESC LIMIT 1")
            mon["q_last_ok"] = dict(r) if r else None
            r = one("SELECT * FROM q_runs WHERE status != 'running' ORDER BY id DESC LIMIT 1")
            mon["q_last"] = dict(r) if r else None
            r = one("SELECT session_date, version, status, created_utc FROM q_reports ORDER BY created_utc DESC LIMIT 1")
            mon["q_report"] = dict(r) if r else None
            r = one("SELECT * FROM q_health WHERE id=1")
            mon["health"] = dict(r) if r else None
        finally:
            store.close()
    inputs["monitor"] = mon
    db = jobs_db or PROJECT_ROOT / "data" / "jobs" / "jobs.sqlite"
    workers = [{"worker": w, "kind": k, "version": v, "depends_on": d} for w, k, v, d in jobs_mod.WORKERS]
    if db.is_file():
        js = jobs_mod.JobStore(db)
        try:
            snap = js.snapshot()
        finally:
            js.close()
        inputs["jobs"] = {"pipelines": snap.get("pipelines", []), "jobs": snap.get("jobs", []), "workers": workers}
    else:
        inputs["jobs"] = {"pipelines": [], "jobs": [], "workers": workers}
    try:
        from trading.reviewer import budget, review
        rs = budget.ReviewStore()
        try:
            r = review.readiness(review.server_env(), rs)
        finally:
            rs.close()
        inputs["review"] = {"available": r.get("available"), "state": r.get("state"), "revoked": r.get("revoked")}
    except Exception as exc:                          # missing review records -> UNKNOWN-style evidence
        inputs["review"] = {"available": False, "state": f"UNKNOWN ({type(exc).__name__})"}
    exps = []
    for e in jobs_mod.ALLOWED_EXPERIMENTS:
        inv = jobs_mod.inventory(e)
        exps.append({"experiment": e, "state": (inv.get("status") or {}).get("state")})
    hist = None
    try:
        from trading.history import read_manifest
        m = read_manifest("SPY", "sip", "all")
        if m:
            hist = {"usable_sessions": (m.get("summary") or {}).get("usable_sessions"), "retrieved_utc": m.get("retrieved_utc")}
    except Exception:
        hist = None
    inputs["research"] = {"experiments": exps, "history": hist}
    return build_map(inputs, now, static_relations())
