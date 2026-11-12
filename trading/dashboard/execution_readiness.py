"""Readiness for a SUPERVISED PAPER-ORDER TEST, derived from records. Read-only; it runs nothing and enables nothing.

A prerequisite is MET only when a record proves it (an owner-approved file, an acceptance result, a written
authorization). Code or documents that merely exist do not count. Missing evidence is NOT MET or UNKNOWN, never MET.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRILLS = ROOT / "results" / "execution_lab" / "crash_drills.json"
ADAPTER_DRILLS = ROOT / "results" / "execution_lab" / "paper_sim_drills.json"   # same drills via the adapter (simulated API)
PLAN = ROOT / "docs" / "PAPER_TEST_PLAN_DRAFT.md"
AUTHORIZATION = ROOT / "config" / "paper_order_test_authorization.json"     # does not exist: only the owner creates it
INTENDED_ACCOUNT = ROOT / "config" / "intended_paper_account.json"          # does not exist: owner confirmation


def _drills(path: Path = DRILLS) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def collect() -> dict:
    from trading.execution_lab.intents import NO_STRATEGY, approved_strategies
    from trading.execution_lab.policy import APPROVED
    items = []
    try:
        from trading.operations import snapshot                      # read-only (the dashboard already uses it)
        snap = snapshot.collect()
        acc = snap.get("acceptance") or {}
        if snap.get("records_visible") is False or not acc:
            items.append({"id": "dry_run", "item": "Dry-run acceptance (Milestone 1)", "status": "UNKNOWN",
                          "evidence": snap.get("note") or "operations records not readable from this process"})
        else:
            items.append({"id": "dry_run", "item": "Dry-run acceptance (Milestone 1)",
                          "status": "MET" if acc.get("accepted") else "NOT MET",
                          "evidence": f"streak {acc.get('current_streak')} of {acc.get('required_consecutive_passes')} "
                                      f"(python -m trading.operations acceptance)"})
    except Exception as exc:
        items.append({"id": "dry_run", "item": "Dry-run acceptance (Milestone 1)", "status": "UNKNOWN",
                      "evidence": f"unreadable: {type(exc).__name__}"})
    unset = [r for r in APPROVED.table() if r["status"] == "UNSET"]
    items.append({"id": "policy", "item": "Approved execution policies (decisions A1-A6)",
                  "status": "NOT MET" if unset else "MET",
                  "evidence": f"{len(unset)} of {len(APPROVED.table())} fields UNSET; no approval file exists"})
    from trading.execution_lab.intended_account import load as load_intended
    ref, ref_ev = load_intended(INTENDED_ACCOUNT)
    items.append({"id": "account", "item": "Verified intended paper-account identity",
                  "status": "MET" if ref else "NOT MET",
                  "evidence": ref_ev + ("" if ref else " (the dry run observes an account reference; an observation is not "
                                                       "a confirmation of intent)")})
    d = _drills()
    ps = _drills(ADAPTER_DRILLS)
    items.append({"id": "safety", "item": "Safety controls tested", "status": "PARTIAL (offline only)",
                  "evidence": ("offline: guard refusal, policy refusal, unknown-outcome handling, fresh-process recovery "
                               f"drills ({'all passed' if d and d.get('passed') else 'not all passed' if d else 'no recorded run'}"
                               f"{', recorded ' + d['recorded_utc'] if d else ''}); the same drills through the order adapter over "
                               f"a SIMULATED Alpaca API ({'all passed' if ps and ps.get('passed') else 'not all passed' if ps else 'no recorded run'}"
                               f"{', recorded ' + ps['recorded_utc'] if ps else ''}); kill switch and paper-only account checks "
                               "tested offline; none tested against the paper account")})
    items.append({"id": "plan", "item": "Written test scope and limits",
                  "status": "NOT MET", "evidence": f"{PLAN.name} is a DRAFT with owner blanks; not approved" if PLAN.exists()
                  else "no test plan"})
    items.append({"id": "authorization", "item": "Explicit authorization to submit the specified paper orders",
                  "status": "MET" if AUTHORIZATION.exists() else "NOT GIVEN",
                  "evidence": "no written authorization on record"})
    # Described, never imported or named by module path: the dashboard must stay unable to reach the adapter.
    adapter = {"status": "OFFLINE (fixtures and a simulated API) ONLY", "evidence": "offline order adapter: documented "
               "request formats, fixture and simulated transports, session controls and preflight; no network transport "
               "exists; every write calls the order-submission guard (which refuses)"}
    met = all(i["status"] == "MET" for i in items)
    return {"overall": "NOT READY" if not met else "PREREQUISITES RECORDED (owner still decides)", "items": items,
            "adapter": adapter, "strategy": NO_STRATEGY if not approved_strategies() else "approved strategy present",
            "crash_drills": d, "real_money": "NOT IN SCOPE: no live endpoint is reachable (paper host only)"}
