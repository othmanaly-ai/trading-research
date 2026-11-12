"""The owner's confirmation of WHICH paper account an order test may use. Read-only; nothing here writes the file.

`config/intended_paper_account.json` is written by the owner only. It records a one-way account reference, not the
account id or number: the first 12 hex digits of SHA-256 of the account id, the same reference the dry run records
(`trading/alpaca_client.py::get_account_identity`). An observation of an account by the dry run is evidence of
which account the keys reach; it is NOT the owner's confirmation that this is the intended test account.

    {"schema": 1, "environment": "paper", "account_ref": "<12 hex>", "confirmed_by": "...", "confirmed_utc": "..."}

Missing, unreadable or malformed means NOT CONFIRMED, and every order test refuses.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "config" / "intended_paper_account.json"


def account_ref(account_id) -> str | None:
    """The one-way reference for an account id (never store or print the id itself)."""
    return hashlib.sha256(str(account_id).encode()).hexdigest()[:12] if account_id else None


def _is_ref(x) -> bool:
    return isinstance(x, str) and len(x) == 12 and all(c in "0123456789abcdef" for c in x)


def load(path: Path | None = None) -> tuple[str | None, str]:
    """(account_ref, evidence). account_ref is None unless the owner's file is present and well-formed."""
    p = Path(path or PATH)
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, f"NOT CONFIRMED: {p.name} does not exist (only the owner writes it)"
    except (OSError, ValueError) as exc:
        return None, f"NOT CONFIRMED: {p.name} unreadable ({type(exc).__name__}); fail closed"
    problems = []
    if not isinstance(d, dict) or d.get("schema") != 1:
        problems.append("unknown format (schema must be 1)")
    else:
        if d.get("environment") != "paper":
            problems.append("environment must be 'paper'")
        if not _is_ref(d.get("account_ref")):
            problems.append("account_ref must be 12 lowercase hex digits")
        if not str(d.get("confirmed_by") or "").strip():
            problems.append("confirmed_by is empty")
        if not str(d.get("confirmed_utc") or "").strip():
            problems.append("confirmed_utc is empty")
    if problems:
        return None, f"NOT CONFIRMED: {p.name}: " + "; ".join(problems)
    return d["account_ref"], f"confirmed by {d['confirmed_by']} at {d['confirmed_utc']} (account ref {d['account_ref']})"
