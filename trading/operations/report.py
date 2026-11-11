"""Session classification and the end-of-day report, computed only from recorded evidence.

Rules: docs/DRY_RUN_ACCEPTANCE.md. Missing evidence is never a pass. Precedence:
FAIL > INCOMPLETE > INTERRUPTED > PASS. Imports no broker code (the dashboard uses this module).
"""

import json
import re
import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta

from trading.operations.schedule import ET, plan_for
from trading.sessions import sessions_between

LABEL = "DRY RUN: verifies operation, not profitability. No strategy is approved and no order code exists."
HEARTBEAT_GAP_S = 90
WORKER_ALIVE_MIN_SHARE = 0.95
CLOCK_CHECK_EVERY_S = 1800
STREAK_REQUIRED = 5
SAFETY_CHECK_CODES = {"order_guard_disabled": "F3", "environment_dry_run": "F4", "runtime_outside_onedrive": "F5"}
# Owner-authorized correction (2026-11-10): the closing "no exposure" check used to be recorded as passed without asking
# the broker. From this session date on, broker evidence is required (F9 / I6 / N4); earlier sessions keep the
# classification they had under the original rules and are never relabelled.
EXPOSURE_EVIDENCE_FROM = date(2026, 11, 11)
PAPER_HOST = "https://paper-api.alpaca.markets"


def _verified_none(x: dict) -> bool:
    """Same test as broker_checks.verified_none (kept here: this module imports no broker code)."""
    return (x.get("verified") is True and x.get("status") == "VERIFIED_NONE" and x.get("environment_host") == PAPER_HOST
            and bool(x.get("account_ref")))


def _p(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _et(s):
    return _p(s).astimezone(ET).strftime("%H:%M:%S")


def classify(store, d: date, now: datetime) -> dict:
    plan = plan_for(d)
    out = {"session_date": str(d), "label": LABEL, "plan": plan.as_dict(), "generated_utc": now.isoformat()}
    if not plan.trading_day:
        return {**out, "classification": "NO_SESSION", "reasons": ["not an XNYS session"]}
    if now < plan.report_utc:
        return {**out, "classification": "PENDING", "reasons": [f"report time {plan.report_utc.astimezone(ET):%H:%M} ET not reached"]}
    try:
        runs, decisions = store.runs_for(str(d)), store.decisions_for(str(d))
        checks, events, hbs = store.checks_for(str(d)), store.events_for(str(d)), store.heartbeats_for(str(d))
    except sqlite3.Error as exc:
        return {**out, "classification": "INCOMPLETE", "reasons": [f"I4 records unreadable ({type(exc).__name__})"]}
    fail, inc, intr = [], [], []
    if not runs:
        return {**out, "classification": "INCOMPLETE", "reasons": ["I1 NOT RUN: no run record for this scheduled session"]}

    # ---- FAIL
    for c in checks:
        if c["stage"] == "start" and not c["ok"] and c["name"] in SAFETY_CHECK_CODES:
            fail.append(f"{SAFETY_CHECK_CODES[c['name']]} safety check failed: {c['name']} {c['detail_json']}")
    if any(r["environment"] != "DRY_RUN" for r in runs):
        fail.append("F4 environment other than DRY_RUN")
    expected = [m.isoformat() for m in plan.decision_minutes()]
    exp_set = set(expected)
    allowed = [x for x in decisions if x["allowed"]]
    if allowed:
        fail.append(f"F1 {len(allowed)} decision(s) recorded with entry allowed")
    bad_time = [x for x in decisions if x["minute_utc"] not in exp_set
                or not (0 <= (_p(x["decided_utc"]) - _p(x["minute_utc"])).total_seconds() < 60)]
    if bad_time:
        fail.append(f"F2 {len(bad_time)} decision(s) outside the window or not in their own minute (first {bad_time[0]['minute_utc']})")
    if len({x["minute_utc"] for x in decisions}) != len(decisions):
        fail.append("F8 duplicate decisions for one minute")
    exc_events = [e for e in events if e["kind"] == "exception"]
    crashes = [r for r in runs if (r["exit_reason"] or "").startswith("crash")]
    if exc_events or crashes:
        fail.append(f"F6 software error: {len(exc_events)} exception event(s), {len(crashes)} crashed run(s)")
    no_reason = [x for x in decisions if not x["allowed"] and not json.loads(x["reasons_json"])]
    if no_reason:
        fail.append(f"F7 {len(no_reason)} denied decision(s) without reasons")

    # ---- INCOMPLETE
    first_start = min(_p(r["started_utc"]) for r in runs)
    if first_start >= plan.final_check_utc:
        inc.append(f"I2 late start: first run at {first_start.astimezone(ET):%H:%M:%S} ET (on time = before "
                   f"{plan.final_check_utc.astimezone(ET):%H:%M} ET)")
    finals = [c for c in checks if c["stage"] == "final"]
    if not finals:
        inc.append("I3 no final pre-open check recorded")
    gits = [(json.loads(r["config_json"] or "{}").get("git") or {}) for r in runs]
    if not all(g.get("operations_code_committed") for g in gits):
        inc.append("I5 operations code at run time was not exactly a committed version; evidence not tied to a commit")

    # ---- broker exposure evidence (sessions from EXPOSURE_EVIDENCE_FROM)
    exposure = []
    if d >= EXPOSURE_EVIDENCE_FROM:
        exp = [(c, json.loads(c["detail_json"] or "{}")) for c in checks if c["name"] == "exposure_none"]
        exposure = [{"stage": c["stage"], "ts_utc": c["ts_utc"], "ok": bool(c["ok"]), "status": x.get("status"),
                     "account_ref": x.get("account_ref"), "reason": x.get("reason"),
                     "positions": x.get("positions"), "open_orders": x.get("open_orders")} for c, x in exp]
        found = [x for _, x in exp if x.get("status") == "EXPOSURE_FOUND"]
        if found:
            fail.append(f"F9 unexpected exposure at the broker in {len(found)} check(s): {found[0].get('reason')} "
                        "(nothing was closed or cancelled; owner review required)")
        finals_all = [c for c in checks if c["stage"] == "final"]
        if finals_all and not any(c["name"] == "exposure_none" for c in finals_all):
            intr.append("N4 final pre-open exposure check not recorded")
        reached_close = any(e["kind"] == "after_close" for e in events) or any(c["stage"] == "closing" for c in checks)
        closing = [(c, x) for c, x in exp if c["stage"] == "closing"]
        if reached_close:
            if not closing:
                inc.append("I6 no closing exposure evidence recorded")
            else:
                c, x = closing[-1]
                if not (c["ok"] and _verified_none(x)):
                    if x.get("status") != "EXPOSURE_FOUND":
                        inc.append("I6 closing exposure not verified by broker evidence: "
                                   + (x.get("reason") or "no broker observation recorded (a local assertion is not evidence)"))
                elif _p(x["observed_from_utc"]) < plan.closing_utc:
                    inc.append("I6 closing exposure evidence predates the closing phase (stale)")
                else:
                    first = next((y for cc, y in exp if cc["stage"] in ("pre_open", "final", "late_start") and _verified_none(y)), None)
                    if first is None:
                        inc.append("I6 account unverifiable: no earlier broker observation this session to compare with")
                    elif first["account_ref"] != x["account_ref"]:
                        inc.append("I6 account at closing differs from the account observed earlier this session")

    # ---- INTERRUPTED
    recorded = {x["minute_utc"] for x in decisions}
    missing = [m for m in expected if m not in recorded]
    if missing:
        intr.append(f"N1 {len(missing)} of {len(expected)} decision minutes missing (first {_et(missing[0])} ET)")
    after = [e for e in events if e["kind"] == "after_close"]
    end_t = _p(after[0]["ts_utc"]) if after else max([_p(h["ts_utc"]) for h in hbs] or [first_start])
    ts = sorted({_p(h["ts_utc"]) for h in hbs} | {first_start})
    gaps = [(a, b) for a, b in zip(ts, ts[1:]) if (b - a).total_seconds() > HEARTBEAT_GAP_S and a < end_t]
    if gaps:
        a, b = max(gaps, key=lambda g: g[1] - g[0])
        intr.append(f"N2 {len(gaps)} heartbeat gap(s) over {HEARTBEAT_GAP_S} s; longest {int((b - a).total_seconds())} s "
                    f"from {a.astimezone(ET):%H:%M:%S} ET")
    if not after:
        intr.append("N3 the runner did not reach the after-close step")
    bad_final = [c["name"] for c in finals if c["dependency"] and not c["ok"]]
    if bad_final:
        intr.append(f"N4 final pre-open dependency check(s) failed: {', '.join(sorted(set(bad_final)))}")
    periodic = [c for c in checks if c["stage"] == "periodic" and c["name"] == "broker_clock_skew"]
    bad_periodic = [c for c in checks if c["stage"] == "periodic" and not c["ok"]]
    need = int((plan.closing_utc - plan.final_check_utc).total_seconds() // CLOCK_CHECK_EVERY_S) - 1
    if bad_periodic:
        intr.append(f"N5 {len(bad_periodic)} periodic check(s) failed: {', '.join(sorted({c['name'] for c in bad_periodic}))}")
    if not inc and len(periodic) < need:
        intr.append(f"N5 periodic clock checks recorded {len(periodic)}, expected at least {need}")
    inputs = [json.loads(x["inputs_json"]) for x in decisions]
    alive = sum(1 for i in inputs if (i.get("data") or {}).get("worker_alive"))
    share = alive / len(expected) if expected else 0.0
    if share < WORKER_ALIVE_MIN_SHARE:
        intr.append(f"N6 monitoring worker alive in {alive} of {len(expected)} decision minutes ({share:.1%} < 95%)")

    cls = "FAIL" if fail else "INCOMPLETE" if inc else "INTERRUPTED" if intr else "PASS"
    tallies = Counter(re.sub(r"\d+(\.\d+)?", "N", r) for x in decisions for r in json.loads(x["reasons_json"]))
    fresh = Counter()
    for i in inputs:
        for s, v in ((i.get("data") or {}).get("symbols") or {}).items():
            fresh[s] += int(bool(v.get("fresh")))
    kill_on = sum(1 for i in inputs if (i.get("kill_switch") or {}).get("on"))
    return {**out, "classification": cls, "reasons": fail + inc + intr,
            "runs": [{k: r[k] for k in ("run_id", "started_utc", "start_class", "ended_utc", "exit_reason",
                                        "code_fingerprint", "code_version")} for r in runs],
            "code_fingerprints": sorted({r["code_fingerprint"] for r in runs}),
            "code_version": {"commits": sorted({g.get("commit") or "unknown" for g in gits}),
                             "operations_code_committed": all(g.get("operations_code_committed") for g in gits),
                             "fingerprints": sorted({r["code_fingerprint"] for r in runs})},
            "final_preopen_checks": [{k: c[k] for k in ("name", "ok", "dependency", "detail_json")} for c in finals],
            "exposure_evidence": exposure if d >= EXPOSURE_EVIDENCE_FROM else
            "not required for sessions before 2026-11-11 (original rules; the closing check was a recorded assumption)",
            "decisions": {"expected": len(expected), "recorded": len(decisions), "missing": len(missing),
                          "allowed": len(allowed), "denied": len(decisions) - len(allowed),
                          "reason_tallies": dict(tallies.most_common())},
            "data": {"worker_alive_minutes": alive, "worker_alive_share": round(share, 4),
                     "fresh_minutes_by_symbol": dict(fresh)},
            "clock_checks": [{"ts_utc": c["ts_utc"], "stage": c["stage"], "ok": bool(c["ok"]),
                              **{k: json.loads(c["detail_json"]).get(k) for k in ("skew_s", "round_trip_s")}}
                             for c in checks if c["name"] == "broker_clock_skew"],
            "heartbeat_gaps": [{"from_utc": a.isoformat(), "to_utc": b.isoformat(), "seconds": int((b - a).total_seconds())}
                               for a, b in gaps],
            "kill_switch_on_minutes": kill_on,
            "warnings": [e["message"] for e in events if e["level"] in ("warn", "error")][:50]}


def acceptance(store, now: datetime) -> dict:
    dates = store.session_dates()
    if not dates:
        return {"sessions": [], "streak": 0, "accepted": False, "note": "no run recorded yet"}
    first = date.fromisoformat(dates[0])
    last = (now.astimezone(ET)).date()
    rows = []
    for s in sessions_between(first, last):
        c = classify(store, s.date, now)
        if c["classification"] == "PENDING":
            rows.append({"session_date": str(s.date), "classification": "PENDING", "fingerprints": []})
            continue
        rows.append({"session_date": str(s.date), "classification": c["classification"],
                     "fingerprints": c.get("code_fingerprints", []),
                     "commits": (c.get("code_version") or {}).get("commits", []), "reasons": c["reasons"][:3]})
    done = [r for r in rows if r["classification"] != "PENDING"]
    streak, accepted_on, run_fp, run_len = 0, None, None, 0
    for r in done:
        ok = r["classification"] == "PASS" and len(r["fingerprints"]) == 1
        if ok and r["fingerprints"][0] == run_fp:
            run_len += 1
        elif ok:
            run_fp, run_len = r["fingerprints"][0], 1
        else:
            run_fp, run_len = None, 0
        if run_len >= STREAK_REQUIRED and accepted_on is None:
            accepted_on = r["session_date"]
    streak = run_len
    return {"label": LABEL, "required_consecutive_passes": STREAK_REQUIRED, "sessions": rows, "current_streak": streak,
            "accepted": accepted_on is not None, "accepted_on": accepted_on}
