"""Read-only broker checks for the dry run: clock skew, calendar agreement, account status, and exposure (positions
and open orders).

Uses only the existing read-only client (HTTP GET). Records no balances and no identifiers: account status flags, a
one-way 12-digit account reference, and for any exposure found only symbol/side/quantity/status. Imported by the
runner only, never by the dashboard.
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
    """Our XNYS calendar against the broker clock. Within 5 s of the open or close no comparison is possible; that
    is reported as not compared (ok=False), never as agreement."""
    ours_open = bool(plan.trading_day and plan.open_utc <= now < plan.close_utc)
    detail = {"ours_open": ours_open, "broker_open": clock["is_open"]}
    if plan.trading_day and min(abs((now - plan.open_utc).total_seconds()),
                                abs((now - plan.close_utc).total_seconds())) < BOUNDARY_S:
        # Not compared, so not verified: recorded as a failed check ("could not be performed"), never as a pass.
        # The runner's required comparisons (08:45, 09:25, then every 30 min from 09:55 ET) never fall in this window;
        # only a start or restart within 5 s of the open or close can.
        return False, {**detail, "compared": False,
                       "note": "NOT COMPARED: within 5 s of the open or close, where the broker's open/closed state is "
                               "ambiguous; no evidence either way"}
    if clock["is_open"] != ours_open:
        return False, {**detail, "compared": True, "note": "open/closed state disagrees"}
    if plan.trading_day and now < plan.open_utc:
        ok = _parse(clock["next_open"]) == plan.open_utc
        return ok, {**detail, "compared": True, "broker_next_open": clock["next_open"], "ours_open_utc": plan.open_utc.isoformat()}
    if ours_open:
        ok = _parse(clock["next_close"]) == plan.close_utc
        return ok, {**detail, "compared": True, "broker_next_close": clock["next_close"], "ours_close_utc": plan.close_utc.isoformat()}
    return True, {**detail, "compared": True}


def account_check(client) -> tuple[bool, dict]:
    a = client.get_account()
    detail = {k: a.get(k) for k in ("status", "trading_blocked", "account_blocked")}
    return (a.get("status") == "ACTIVE" and not a.get("trading_blocked") and not a.get("account_blocked")), detail


# ---------------------------------------------------------------- exposure (positions and open orders)

PAPER_HOST = "https://paper-api.alpaca.markets"
ORDER_LIST_LIMIT = 500          # largest page the open-order request asks for; a full page may be truncated
MAX_ROUND_TRIP_S = 30.0         # evidence gathered over a longer span is not a single observation
VERIFIED_NONE, EXPOSURE_FOUND, UNVERIFIABLE = "VERIFIED_NONE", "EXPOSURE_FOUND", "UNVERIFIABLE"


def _qty(x) -> float:
    return float(str(x))


def exposure_check(client, now_fn, expected_ref: str | None = None) -> tuple[bool, dict]:
    """Does the paper account hold no positions and no open orders, by broker evidence (HTTP GET only)?

    PASS (ok=True) only for VERIFIED_NONE: the paper host answered, the account reference is present (and equals
    `expected_ref` when one is given), both lists are well-formed, the open-order page is not full, the evidence was
    gathered within MAX_ROUND_TRIP_S, and both lists are empty. EXPOSURE_FOUND (verified, ok=False) lists what was
    found; nothing is closed or cancelled. Anything else is UNVERIFIABLE (ok=False) with the reason.
    """
    t0 = now_fn()
    det = {"verified": False, "status": UNVERIFIABLE, "observed_from_utc": t0.isoformat(),
           "method": "read-only client GETs: account identity, positions, open orders (incl. partially filled)"}
    try:
        ident = client.get_account_identity()
        positions = client.get_positions()
        orders = client.get_open_orders(limit=ORDER_LIST_LIMIT)
    except Exception as exc:                       # credentials, network, HTTP status, malformed body: never a pass
        det["reason"] = f"broker evidence unavailable: {type(exc).__name__}: {str(exc)[:200]}"
        return False, det
    t1 = now_fn()
    det.update({"observed_to_utc": t1.isoformat(), "environment_host": (ident or {}).get("environment_host"),
                "account_ref": (ident or {}).get("account_ref")})
    problems = []
    if det["environment_host"] != PAPER_HOST:
        problems.append(f"wrong environment: answered by {det['environment_host']!r}, expected the paper host")
    ref = det["account_ref"]
    if not (isinstance(ref, str) and len(ref) == 12 and all(c in "0123456789abcdef" for c in ref)):
        problems.append("account reference missing or malformed: account unverifiable")
    elif expected_ref and ref != expected_ref:
        problems.append("account differs from the one checked earlier this session")
    if not isinstance(positions, list) or not all(isinstance(p, dict) and p.get("symbol") and p.get("qty") is not None
                                                  for p in positions):
        problems.append("positions response malformed")
    if not isinstance(orders, list) or not all(isinstance(o, dict) and o.get("symbol") and o.get("status")
                                               for o in orders):
        problems.append("open-orders response malformed")
    elif len(orders) >= ORDER_LIST_LIMIT:
        problems.append(f"open-order list incomplete: a full page of {ORDER_LIST_LIMIT} may be truncated")
    if (t1 - t0).total_seconds() > MAX_ROUND_TRIP_S:
        problems.append(f"evidence gathered over {(t1 - t0).total_seconds():.0f} s (> {MAX_ROUND_TRIP_S:.0f} s): stale")
    held = []
    if not problems:
        try:
            held = [p for p in positions if _qty(p["qty"]) != 0]
        except (TypeError, ValueError):
            problems.append("position quantity unreadable")
    if problems:
        det["reason"] = "; ".join(problems)
        return False, det
    det["verified"] = True
    det["positions"] = held
    det["open_orders"] = orders
    if held or orders:
        det["status"] = EXPOSURE_FOUND
        det["reason"] = (f"unexpected exposure: {len(held)} position(s), {len(orders)} open order(s); DRY_RUN must hold "
                         "none. Nothing was closed or cancelled.")
        return False, det
    det["status"] = VERIFIED_NONE
    return True, det


def verified_none(detail: dict) -> bool:
    """True only for a recorded VERIFIED_NONE observation from the paper host with an account reference."""
    return (detail.get("verified") is True and detail.get("status") == VERIFIED_NONE
            and detail.get("environment_host") == PAPER_HOST and bool(detail.get("account_ref")))
