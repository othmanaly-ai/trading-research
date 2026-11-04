"""Daily monitoring evidence report (one per session). Reads stored records only; no network.

Three kinds of IEX/SIP information are kept apart on purpose:
  live            what the live monitor actually received, and when (table `bars`; never back-filled
                  from later re-fetches, so gaps in the live capture stay visible)
  iex_revisions   what IEX reported later when re-fetched (table `q_obs`, feed iex), compared with the
                  live capture; a later re-fetch never implies the live capture was complete or accurate
  sip_comparison  delayed consolidated (SIP) bars vs IEX; "eligible" = when the free plan first allows
                  a SIP bar to be known (bar end + 15 min), "received" = when it actually arrived

`evidence` contains only facts derived from stored records (deterministic for a closed session; its
hash makes finalization idempotent). Anything that depends on the current time is in `live_view`.
"""

import json
from datetime import date, datetime, timedelta

from trading.monitor import store as st

NORMAL_LIVE_LATENCY_S = 180       # bar end -> received; above this the bar arrived by catch-up after a gap
STALE_GAP_S = st.STALE_AFTER_S    # no new live bar for longer than this = stale interval
CATEGORY_LABELS = {
    "consistent_subset": "IEX within the SIP range (prices can still differ; not identical, not a suitability check)",
    "expected_coverage_difference": "SIP bar, no IEX bar (expected: no IEX trades)",
    "both_absent": "no bar in either feed",
    "unresolved_anomaly": "unresolved anomaly",
    "structural_defect": "structural defect",
}


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def _secs(a, b):
    return (st.parse(a) - st.parse(b)).total_seconds() if a and b else None


def _session(date_s: str):
    found = st.sessions_between(date.fromisoformat(date_s), date.fromisoformat(date_s))
    return found[0] if found else None


def _intervals_uncovered(start: datetime, end: datetime, covered: list[tuple[datetime, datetime]]):
    gaps, cur = [], start
    for a, b in sorted(covered):
        if b <= cur:
            continue
        if a > cur:
            gaps.append((cur, min(a, end)))
        cur = max(cur, b)
        if cur >= end:
            break
    if cur < end:
        gaps.append((cur, end))
    return [(a, b) for a, b in gaps if (b - a).total_seconds() >= 60]


def _state(store, date_s, session, now):
    row = store.db.execute("SELECT * FROM q_state WHERE session_date=?", (date_s,)).fetchone()
    reports = [dict(r) for r in store.db.execute(
        "SELECT version, status, created_utc, amends_version, report_sha FROM q_reports WHERE session_date=? "
        "ORDER BY version", (date_s,))]
    if row is None:
        return {"state": "not_monitored", "detail": "the live monitor did not run during this session",
                "reports": reports}
    row = dict(row)
    through = st.parse(row["compared_through_utc"]) if row.get("compared_through_utc") else None
    if row.get("status") == "incomplete":
        state = "incomplete"
    elif session and through and through >= session.close_utc and row.get("eod_recheck_utc"):
        state = "finalized"
    elif session and now >= session.close_utc:
        state = "provisional"
    else:
        state = "in_progress"
    return {"state": state, "detail": row.get("detail"), "compared_through_utc": row.get("compared_through_utc"),
            "eod_recheck_utc": row.get("eod_recheck_utc"), "first_monitored_utc": row.get("first_monitored_utc"),
            "access_failures": row.get("access_failures") or 0, "reports": reports}


def daily_report(store: st.MonitorStore, date_s: str, now: datetime | None = None) -> dict:
    from trading.monitor import quality as q
    q.ensure_schema(store)
    now = now or st.now_utc()
    session = _session(date_s)
    out = {"label": "MONITORING EVIDENCE REPORT · read-only · not a research dataset · not a trading signal "
                    "or suitability certificate", "session_date": date_s, "generated_utc": st.iso(now),
           "status": _state(store, date_s, session, now), "evidence": {}, "live_view": {}}
    if session is None:
        out["evidence"] = {"schedule": {"note": "no regular session on this date (weekend or exchange holiday)"}}
        return out
    end = min(now, session.close_utc)
    cfg_row = store.worker().get("config") or {}
    symbols = cfg_row.get("symbols") or list(st.DEFAULT_SYMBOLS)
    ev = out["evidence"]
    ev["schedule"] = {"open_utc": st.iso(session.open_utc), "close_utc": st.iso(session.close_utc),
                      "early_close": session.early_close, "scheduled_minutes": session.regular_minutes}
    runs = store.runs_between(session.open_utc, session.close_utc + timedelta(hours=3))
    covered = [(st.parse(r["started_utc"]), st.parse(r["last_alive_utc"]) + timedelta(seconds=st.HEARTBEAT_DEAD_S))
               for r in runs]

    # ---- live capture ----------------------------------------------------------------------
    live, revisions, sipc = {}, {}, {}
    for sym in symbols:
        bars = [dict(r) for r in store.db.execute(
            "SELECT * FROM bars WHERE symbol=? AND feed='iex' AND session_date=? ORDER BY t_utc", (sym, date_s))]
        lat = [(_secs(b["received_utc"], b["t_utc"]) or 0) - 60 for b in bars]
        normal = [x for x in lat if x <= NORMAL_LIVE_LATENCY_S]
        catch = [x for x in lat if x > NORMAL_LIVE_LATENCY_S]
        starts = [st.parse(b["t_utc"]) for b in bars]
        edges = [session.open_utc] + [t + timedelta(minutes=1) for t in starts]
        nexts = starts + [end]
        stale = []
        for a, b in zip(edges, nexts):
            if (b - a).total_seconds() > STALE_GAP_S:
                alive = sum(max(0.0, (min(b, y) - max(a, x)).total_seconds()) for x, y in covered)
                stale.append({"from_utc": st.iso(a), "to_utc": st.iso(b), "minutes": int((b - a).total_seconds() // 60),
                              "worker_alive_share": round(alive / (b - a).total_seconds(), 3)})
        sip_t = {r[0] for r in store.db.execute("SELECT DISTINCT t_utc FROM q_obs WHERE symbol=? AND feed='sip' AND "
                                                "session_date=? AND defects IS NULL", (sym, date_s))}
        live_t = {b["t_utc"] for b in bars}
        live[sym] = {
            "received_minutes": len(bars), "received_normal": len(normal), "received_by_catch_up": len(catch),
            "latency_normal_median_s": _median(normal), "latency_catch_up_median_s": _median(catch),
            "latency_max_s": max(lat) if lat else None,
            "not_received_minutes": session.regular_minutes - len(bars) if now >= session.close_utc else None,
            "not_received_while_sip_had_a_bar": len(sip_t - live_t),
            "first_received_utc": min((b["received_utc"] for b in bars), default=None),
            "last_received_utc": max((b["received_utc"] for b in bars), default=None),
            "stale_intervals": stale,
        }
        # ---- later IEX re-fetch vs what was received live ------------------------------
        first = {r["t_utc"]: dict(r) for r in store.db.execute(
            "SELECT * FROM q_obs WHERE symbol=? AND feed='iex' AND session_date=? AND revision=1", (sym, date_s))}
        diffs = []
        for b in bars:
            f = first.get(b["t_utc"])
            if f and any(f[k] != b[k] for k in ("o", "h", "l", "c", "v")):
                diffs.append({"t_utc": b["t_utc"], "live": {k: b[k] for k in ("o", "h", "l", "c", "v")},
                              "refetch": {k: f[k] for k in ("o", "h", "l", "c", "v")},
                              "live_received_utc": b["received_utc"], "refetch_retrieved_utc": f["retrieved_utc"]})
        revisions[sym] = {
            "minutes_in_both": len(live_t & set(first)), "live_differs_from_refetch": len(diffs),
            "examples": diffs[:10], "refetch_only_minutes": len(set(first) - live_t),
            "live_only_minutes": len(live_t - set(first)),
            "later_iex_revisions": store.db.execute("SELECT COUNT(*) FROM q_obs WHERE symbol=? AND feed='iex' AND "
                                                    "session_date=? AND revision>1", (sym, date_s)).fetchone()[0],
            "note": "re-fetched IEX is what the provider reports later; it does not show the live capture was "
                    "complete or accurate",
        }
        # ---- delayed SIP comparison ----------------------------------------------------
        rows = [dict(r) for r in store.db.execute(
            "SELECT * FROM q_compare c WHERE symbol=? AND session_date=? AND NOT EXISTS (SELECT 1 FROM q_compare d "
            "WHERE d.symbol=c.symbol AND d.t_utc=c.t_utc AND (d.sip_rev > c.sip_rev OR (d.sip_rev = c.sip_rev AND "
            "d.iex_rev > c.iex_rev)))", (sym, date_s))]
        both = [r for r in rows if r["sip_present"] and r["iex_present"] and r["category"] != "structural_defect"]
        pos = [r for r in both if r["sip_volume"] and r["sip_volume"] > 0]
        after_elig = [_secs(r["sip_retrieved_utc"], r["sip_provider_available_utc"]) for r in rows
                      if r["sip_retrieved_utc"] and r["sip_provider_available_utc"]]
        normal_cut = (q.SAFETY_MARGIN + q.CYCLE_EVERY).total_seconds() + 60
        sipc[sym] = {
            "minutes_compared": len(rows),
            "categories": {CATEGORY_LABELS[k]: sum(r["category"] == k for r in rows) for k in CATEGORY_LABELS},
            "sip_bars": sum(r["sip_present"] for r in rows), "iex_refetch_bars": sum(r["iex_present"] for r in rows),
            "close_diff_vs_refetched_iex_bps": {"median_abs": _median([abs(r["d_c_bps"]) for r in both if r["d_c_bps"] is not None]),
                                                "max_abs": max((abs(r["d_c_bps"]) for r in both if r["d_c_bps"] is not None), default=None),
                                                "max_abs_usd": max((abs(r["d_c_usd"]) for r in both if r["d_c_usd"] is not None), default=None)},
            "close_diff_vs_live_iex_bps": {"median_abs": _median([abs(r["d_c_bps_live"]) for r in rows if r.get("d_c_bps_live") is not None]),
                                           "max_abs": max((abs(r["d_c_bps_live"]) for r in rows if r.get("d_c_bps_live") is not None), default=None),
                                           "minutes": sum(1 for r in rows if r.get("d_c_bps_live") is not None)},
            "high_diff_bps_median": _median([r["d_h_bps"] for r in both]),
            "low_diff_bps_median": _median([r["d_l_bps"] for r in both]),
            "iex_volume_share_total": (sum(r["iex_volume"] for r in pos) / sum(r["sip_volume"] for r in pos)) if pos else None,
            "iex_volume_share_median": _median([r["iex_volume_share"] for r in pos]),
            "zero_volume_sip_minutes": sum(1 for r in rows if r["sip_present"] and not r["sip_volume"]),
            "sip_revisions": store.db.execute("SELECT COUNT(*) FROM q_obs WHERE symbol=? AND feed='sip' AND "
                                              "session_date=? AND revision>1", (sym, date_s)).fetchone()[0],
            "sip_received_after_eligible_s": {
                "normal_median": _median([x for x in after_elig if x <= normal_cut]),
                "catch_up_median": _median([x for x in after_elig if x > normal_cut]),
                "catch_up_minutes": sum(1 for x in after_elig if x > normal_cut)},
            "flagged": [{k: r[k] for k in ("t_utc", "category", "detail")} for r in rows
                        if r["category"] in ("unresolved_anomaly", "structural_defect")][:30],
        }
    ev["live"], ev["iex_revisions"], ev["sip_comparison"] = live, revisions, sipc

    # ---- operations ----------------------------------------------------------------------
    gaps = _intervals_uncovered(session.open_utc, end, covered)
    downtime, unrecorded = [], []
    receipts = [st.parse(r[0]) for r in store.db.execute(
        "SELECT received_utc FROM bars WHERE feed='iex' AND session_date=?", (date_s,))]
    for a, b in gaps:
        prev = [r for r in runs if st.parse(r["started_utc"]) < a]
        if not prev and any(a <= t < b for t in receipts):
            unrecorded.append({"from_utc": st.iso(a), "to_utc": st.iso(b), "minutes": int((b - a).total_seconds() // 60),
                               "kind": "unrecorded: live bars were received in this interval, so a worker ran at "
                                       "times, but worker-run recording began later; exact downtime unknown"})
            continue
        if not prev:
            kind = "not running (no worker had started for this session yet)"
        elif prev[-1]["exit_reason"] == "stop requested":
            kind = "planned (stopped by request)"
        else:
            kind = ("unplanned (process ended without a clean stop: crash, kill, or the server/computer was "
                    "shut down)" if not prev[-1]["exit_reason"] else f"unplanned ({prev[-1]['exit_reason']})")
        downtime.append({"from_utc": st.iso(a), "to_utc": st.iso(b), "minutes": int((b - a).total_seconds() // 60),
                         "kind": kind})
    win = (st.iso(session.open_utc - timedelta(minutes=30)), st.iso(session.close_utc + timedelta(hours=3)))
    errors = [dict(r) for r in store.db.execute(
        "SELECT ts_utc, kind, message FROM events WHERE level='error' AND ts_utc BETWEEN ? AND ? ORDER BY id", win)]
    refusals = [e for e in errors if "HTTP 401" in e["message"] or "HTTP 403" in e["message"]
                or e["kind"] == "quality-access_failure"]
    qruns = [dict(r) for r in store.db.execute(
        "SELECT id, kind, status, http_status, requests, window_start_utc, window_end_utc, error, started_utc "
        "FROM q_runs WHERE session_date=? ORDER BY id", (date_s,))]
    ev["operations"] = {
        "worker_runs": [{k: r[k] for k in ("pid", "started_utc", "last_alive_utc", "stopped_utc", "exit_reason",
                                            "code_version")} for r in runs],
        "restarts_during_session": max(0, sum(1 for r in runs if session.open_utc < st.parse(r["started_utc"]) < session.close_utc)
                                       - (0 if any(st.parse(r["started_utc"]) <= session.open_utc for r in runs) else 1)),
        "downtime_intervals": downtime,
        "unrecorded_intervals": unrecorded,
        "unrecorded_minutes": sum(d["minutes"] for d in unrecorded),
        "downtime_minutes": sum(d["minutes"] for d in downtime),
        "unplanned_downtime_minutes": sum(d["minutes"] for d in downtime if d["kind"].startswith("unplanned")),
        "request_failures": len(errors), "access_refusals": len(refusals), "failure_events": errors[:30],
        "comparison_runs": {"total": len(qruns), "ok": sum(r["status"] == "ok" for r in qruns),
                            "failed": [r for r in qruns if r["status"] not in ("ok", "running")][:20],
                            "by_kind": {k: sum(r["kind"] == k for r in qruns) for k in ("cycle", "recovery", "eod_recheck")},
                            "requests": sum(r["requests"] or 0 for r in qruns)},
    }
    stt = out["status"]
    through = stt.get("compared_through_utc")
    unresolved = []
    if not through or st.parse(through) < session.close_utc:
        unresolved.append({"what": "minutes not yet compared with delayed SIP",
                           "from_utc": through or st.iso(session.open_utc), "to_utc": st.iso(session.close_utc)})
    if not stt.get("eod_recheck_utc"):
        unresolved.append({"what": "post-close re-observation (late corrections) not done"})
    for r in ev["operations"]["comparison_runs"]["failed"]:
        unresolved.append({"what": f"comparison run {r['id']} {r['status']}", "from_utc": r["window_start_utc"],
                           "to_utc": r["window_end_utc"], "error": (r["error"] or "")[:200]})
    if downtime:
        unresolved.append({"what": "live capture gaps cannot be recovered after the fact (the later re-fetch "
                                   "is a different observation)", "minutes": ev["operations"]["downtime_minutes"]})
    ev["unresolved"] = unresolved
    ev["provenance"] = {
        "data_host": "https://data.alpaca.markets", "endpoint": "/v2/stocks/bars (HTTP GET, read-only)",
        "timeframe": "1Min", "adjustment": "raw", "symbols": symbols,
        "live_feed": "iex (single exchange, real-time on the free plan)",
        "comparison_feed": "sip (consolidated, free plan: only bars at least 15 min old)",
        "comparison_rule": "minute compared once its end is >= 20 min old (15 min delay + 5 min safety margin)",
        "thresholds": {"stale_gap_s": STALE_GAP_S, "normal_live_latency_s": NORMAL_LIVE_LATENCY_S,
                       "heartbeat_dead_s": st.HEARTBEAT_DEAD_S, "recovery_lookback_sessions": q.RECOVERY_LOOKBACK_SESSIONS,
                       "request_budget_per_hour": q.REQUEST_BUDGET_PER_HOUR, "max_chunk_minutes": int(q.MAX_CHUNK.total_seconds() // 60)},
        "code_versions": sorted({r["code_version"] or "unknown" for r in runs}),
        "store": "data/monitoring/monitor.sqlite (git-ignored; separate from research data)",
    }
    out["live_view"] = {"now_utc": st.iso(now), "comparable_now_until_utc": st.iso(min(q.boundary(now), session.close_utc)),
                        "pending_from_utc": through or st.iso(session.open_utc)}
    return out


def sessions_overview(store: st.MonitorStore, now: datetime | None = None, limit: int = 20) -> list[dict]:
    """One row per monitored session for the city's session history."""
    from trading.monitor import quality as q
    q.ensure_schema(store)
    now = now or st.now_utc()
    rows = [dict(r) for r in store.db.execute("SELECT * FROM q_state ORDER BY session_date DESC LIMIT ?", (limit,))]
    out = []
    for r in rows:
        rep = daily_report(store, r["session_date"], now)
        ev = rep["evidence"]
        live = ev.get("live", {})
        sched = ev.get("schedule", {}).get("scheduled_minutes")
        out.append({
            "session_date": r["session_date"], "state": rep["status"]["state"], "detail": rep["status"].get("detail"),
            "scheduled_minutes": sched, "early_close": ev.get("schedule", {}).get("early_close"),
            "live_received_min": min((v["received_minutes"] for v in live.values()), default=0),
            "compared_min": min((v["minutes_compared"] for v in ev.get("sip_comparison", {}).values()), default=0),
            "downtime_minutes": ev.get("operations", {}).get("downtime_minutes"),
            "unplanned_downtime_minutes": ev.get("operations", {}).get("unplanned_downtime_minutes"),
            "request_failures": ev.get("operations", {}).get("request_failures"),
            "access_refusals": ev.get("operations", {}).get("access_refusals"),
            "report_versions": len(rep["status"].get("reports", [])),
        })
    return out


def stored_or_current(store: st.MonitorStore, date_s: str, now: datetime | None = None) -> dict:
    """The latest stored (finalized/incomplete) report if one exists, else a provisional one computed now."""
    from trading.monitor import quality as q
    q.ensure_schema(store)
    row = store.db.execute("SELECT * FROM q_reports WHERE session_date=? ORDER BY version DESC LIMIT 1",
                           (date_s,)).fetchone()
    if row:
        rep = json.loads(row["report_json"])
        rep["stored_version"] = row["version"]
        rep["stored_utc"] = row["created_utc"]
        rep["status"]["reports"] = _state(store, date_s, _session(date_s), now or st.now_utc())["reports"]
        return rep
    rep = daily_report(store, date_s, now)
    rep["stored_version"] = None
    return rep
