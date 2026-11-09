"""Read-only broker checks for the dry run: clock skew, calendar agreement, account status.

Uses only the existing read-only client (HTTP GET). Records no balances and no identifiers: only
status, trading_blocked and account_blocked. Imported by the runner only, never by the dashboard.
"""

from datetime import datetime

SKEW_TOLERANCE_S = 2.0
BOUNDARY_S = 5.0


def _parse(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def clock_check(client, now_fn) -> dict:
    t0 = now_fn()
    c = client.get_clock()
    t1 = now_fn()
    mid = t0 + (t1 - t0) / 2
    skew = (_parse(c["timestamp"]) - mid).total_seconds()
    return {"ok": abs(skew) <= SKEW_TOLERANCE_S, "skew_s": round(skew, 3), "round_trip_s": round((t1 - t0).total_seconds(), 3),
            "tolerance_s": SKEW_TOLERANCE_S, "is_open": bool(c.get("is_open")), "next_open": c.get("next_open"),
            "next_close": c.get("next_close"), "checked_utc": mid.isoformat()}


def calendar_agreement(clock: dict, plan, now: datetime) -> tuple[bool, dict]:
    """Our XNYS calendar against the broker clock. Comparisons within 5 s of the open or close are skipped."""
    ours_open = bool(plan.trading_day and plan.open_utc <= now < plan.close_utc)
    detail = {"ours_open": ours_open, "broker_open": clock["is_open"]}
    if plan.trading_day and min(abs((now - plan.open_utc).total_seconds()),
                                abs((now - plan.close_utc).total_seconds())) < BOUNDARY_S:
        return True, {**detail, "note": "within 5 s of a boundary; not compared"}
    if clock["is_open"] != ours_open:
        return False, {**detail, "note": "open/closed state disagrees"}
    if plan.trading_day and now < plan.open_utc:
        ok = _parse(clock["next_open"]) == plan.open_utc
        return ok, {**detail, "broker_next_open": clock["next_open"], "ours_open_utc": plan.open_utc.isoformat()}
    if ours_open:
        ok = _parse(clock["next_close"]) == plan.close_utc
        return ok, {**detail, "broker_next_close": clock["next_close"], "ours_close_utc": plan.close_utc.isoformat()}
    return True, detail


def account_check(client) -> tuple[bool, dict]:
    a = client.get_account()
    detail = {k: a.get(k) for k in ("status", "trading_blocked", "account_blocked")}
    return (a.get("status") == "ACTIVE" and not a.get("trading_blocked") and not a.get("account_blocked")), detail
