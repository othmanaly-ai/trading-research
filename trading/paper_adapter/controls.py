"""Paper-session controls for the execution core: kill switch, paper-only account checks, session preflight.

OFFLINE-TESTED ONLY. Nothing here enables order submission; every write still passes through the adapter's guard
(`trading.safety.require_order_submission_allowed`, which refuses unless the owner sets the flags for a test process).

- `EntryControls` is injected into the execution core (`Lab(entry_controls=...)`). The core calls it when an entry is
  validated AND again immediately before the entry is sent. Any reason blocks the entry; nothing is sent.
  It blocks only risk-INCREASING orders. Cancels, protective stops, reconciliation and the emergency stop still run
  while the kill switch is on (the operations kill switch is an entry-blocking switch).
- `session_preflight` lists every precondition for a supervised paper session. It reads only (GET requests).
- Any failure to determine a control's state counts as a block (fail closed).
- This module does not import the dry run's operations code (project boundary). The kill-switch reader and the
  Milestone 1 acceptance reader are INJECTED by the caller; when one is missing, everything blocks.
"""

from __future__ import annotations

from trading.execution_lab import intended_account

PAPER_HOST = "https://paper-api.alpaca.markets"


def kill_switch_reasons(reader=None) -> list[str]:
    """The kill switch, through an injected read-only reader returning an object with .on and .reason.
    No reader, ON, or unreadable blocks entries."""
    if reader is None:
        return ["KILL SWITCH READER NOT CONFIGURED: entries blocked (fail closed)"]
    try:
        s = reader()
        on, reason = bool(s.on), str(s.reason)
    except Exception as exc:
        return [f"KILL SWITCH STATE UNKNOWN ({type(exc).__name__}): entries blocked (fail closed)"]
    return [f"KILL SWITCH ON: {reason}"] if on else []


def host_reasons(transport) -> list[str]:
    host = getattr(transport, "host", None)
    return [] if host == PAPER_HOST else [f"NOT PAPER: transport host {host!r} is not {PAPER_HOST} (refused)"]


def account_reasons(transport, intended_ref: str | None) -> list[str]:
    """Paper host, account reachable, ACTIVE, not blocked, and the owner-confirmed account. GET only."""
    out = host_reasons(transport)
    if not intended_ref:
        out.append("INTENDED ACCOUNT NOT CONFIRMED by the owner (config/intended_paper_account.json)")
    try:
        status, js = transport.request("GET", "/v2/account")
    except Exception as exc:
        return out + [f"ACCOUNT UNVERIFIABLE: {type(exc).__name__}: {str(exc)[:120]}"]
    if status != 200 or not isinstance(js, dict):
        return out + [f"ACCOUNT UNVERIFIABLE: HTTP {status}"]
    ref = intended_account.account_ref(js.get("id"))
    if not ref:
        out.append("ACCOUNT UNVERIFIABLE: no account id in the response")
    elif intended_ref and ref != intended_ref:
        out.append(f"WRONG ACCOUNT: answered by account ref {ref}, owner confirmed {intended_ref}")
    if js.get("status") != "ACTIVE":
        out.append(f"ACCOUNT NOT ACTIVE: status {js.get('status')!r}")
    if js.get("trading_blocked") is not False or js.get("account_blocked") is not False:
        out.append("ACCOUNT BLOCKED or block flags missing (trading_blocked / account_blocked)")
    return out


class EntryControls:
    """Injected into the execution core; returns blocking reasons (empty = no block from these controls)."""

    def __init__(self, transport, intended_ref: str | None, kill_reader=None):
        self.transport, self.intended_ref, self.kill_reader = transport, intended_ref, kill_reader

    def __call__(self) -> list[str]:
        return kill_switch_reasons(self.kill_reader) + account_reasons(self.transport, self.intended_ref)


def session_preflight(transport, intended=None, kill_reader=None, acceptance=None, policy=None, guard=None) -> dict:
    """Every precondition for one supervised paper session, each with evidence. ok only when ALL pass.

    intended: (ref, evidence) from intended_account.load(); acceptance: () -> (accepted, evidence);
    policy: an ExecutionPolicy (default: the APPROVED one, all unset); guard: the write guard (default: the real one).
    """
    from trading.execution_lab.policy import APPROVED, describe_missing
    ref, ref_ev = intended if intended is not None else intended_account.load()
    items = []

    def add(name, reasons, evidence=""):
        items.append({"check": name, "ok": not reasons, "reasons": reasons, "evidence": evidence})

    add("paper host only", host_reasons(transport), str(getattr(transport, "host", None)))
    add("intended account confirmed by the owner", [] if ref else [ref_ev], ref_ev)
    add("account reachable, ACTIVE, unblocked, and the confirmed one",
        [r for r in account_reasons(transport, ref) if not r.startswith(("NOT PAPER", "INTENDED ACCOUNT"))])
    try:
        sp, pos = transport.request("GET", "/v2/positions")
        so, opn = transport.request("GET", "/v2/orders", params={"status": "open", "nested": "true", "limit": 500})
        r = []
        if sp != 200 or not isinstance(pos, list) or so != 200 or not isinstance(opn, list):
            r.append(f"exposure unverifiable (HTTP {sp}/{so})")
        else:
            if [p for p in pos if float(p.get("qty") or 0)]:
                r.append(f"account not flat: {len(pos)} position(s); the test starts only from zero exposure")
            if opn:
                r.append(f"{len(opn)} open order(s) in the account; the test starts only with none")
        add("account flat: no positions and no open orders", r)
    except Exception as exc:
        add("account flat: no positions and no open orders", [f"exposure unverifiable: {type(exc).__name__}"])
    try:
        sc, clk = transport.request("GET", "/v2/clock")
        add("market open (regular session)", [] if sc == 200 and isinstance(clk, dict) and clk.get("is_open") is True
            else ["market not open (or clock unverifiable)"])
    except Exception as exc:
        add("market open (regular session)", [f"clock unverifiable: {type(exc).__name__}"])
    add("kill switch off", kill_switch_reasons(kill_reader))
    try:
        if acceptance is None:
            accepted, acc_ev = False, "acceptance reader not configured (fail closed)"
        else:
            accepted, acc_ev = acceptance()
    except Exception as exc:
        accepted, acc_ev = False, f"unreadable: {type(exc).__name__}"
    add("Milestone 1 dry run accepted (five consecutive PASS sessions)", [] if accepted else [f"NOT ACCEPTED ({acc_ev})"],
        acc_ev)
    pol = policy or APPROVED
    add("execution policy approved for entries", describe_missing(pol.missing("entry")), pol.label)
    try:
        (guard or __import__("trading.safety", fromlist=["x"]).require_order_submission_allowed)()
        add("write permission for this process", [])
    except Exception as exc:
        add("write permission for this process", [f"REFUSED: {exc}"])
    return {"ok": all(i["ok"] for i in items), "items": items,
            "note": "read-only checks; passing them authorizes nothing (written owner authorization is separate)"}
