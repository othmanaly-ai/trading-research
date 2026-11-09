"""Approved-strategy registry (config/approved_strategies.json). Fail closed.

Milestone 1 defines NO approvable strategy state, so every entry is refused. The checks below still
run in order, so a refusal names the most specific reason:
  unknown strategy -> no status record -> refused state (closed/failed/deferred) -> fingerprint
  mismatch -> "no approvable state in Milestone 1".
The file is re-read at every decision, so editing it (or revoking an entry) takes effect within a
minute. Only the owner edits it.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from trading.operations.paths import PROJECT_ROOT

APPROVALS_PATH = PROJECT_ROOT / "config" / "approved_strategies.json"
REFUSED_STATE_WORDS = ("CLOSED", "FAILED", "DEFERRED", "REJECTED", "REVOKED")
APPROVABLE_STATES: tuple = ()          # Milestone 1: none


@dataclass(frozen=True)
class ApprovalResult:
    ok: bool
    readable: bool
    approved: dict | None = None
    reasons: tuple = field(default_factory=tuple)
    file_sha256: str | None = None

    def summary(self) -> str:
        return "approved: " + (self.approved["strategy_id"] if self.ok else "NONE")


def _status_for(strategy_id: str, root: Path):
    from trading.strategies.registry import STRATEGIES, spec_hash
    if strategy_id in STRATEGIES:
        spec = root / STRATEGIES[strategy_id]["spec_path"]
        return spec.parent / "STATUS.json", spec, spec_hash
    cand = root / "research" / "candidates" / strategy_id / "STATUS.json"
    if cand.is_file():
        return cand, None, None
    return None, None, None


def load_approval(path: Path = APPROVALS_PATH, root: Path = PROJECT_ROOT) -> ApprovalResult:
    try:
        raw = Path(path).read_bytes()
        cfg = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        return ApprovalResult(False, False, reasons=(f"approvals file unreadable ({type(exc).__name__}); fail closed",))
    sha = hashlib.sha256(raw).hexdigest()
    if not isinstance(cfg, dict) or cfg.get("schema") != 1 or not isinstance(cfg.get("approved"), list):
        return ApprovalResult(False, False, reasons=("approvals file has an unknown format; fail closed",), file_sha256=sha)
    entries = cfg["approved"]
    if not entries:
        return ApprovalResult(False, True, reasons=("no approved strategy",), file_sha256=sha)
    if len(entries) > 1:
        return ApprovalResult(False, True, reasons=("more than one approved strategy; refused",), file_sha256=sha)
    e = entries[0] if isinstance(entries[0], dict) else {}
    sid = str(e.get("strategy_id", ""))
    status_path, spec, hasher = _status_for(sid, root)
    if status_path is None:
        return ApprovalResult(False, True, reasons=(f"unknown strategy {sid!r}; refused",), file_sha256=sha)
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ApprovalResult(False, True, reasons=(f"{sid}: no readable status record; refused",), file_sha256=sha)
    state = str(status.get("state", ""))
    if status.get("closed") or any(w in state.upper() for w in REFUSED_STATE_WORDS):
        closed = " (closed)" if status.get("closed") else ""
        return ApprovalResult(False, True, reasons=(f"{sid}: state {state or 'unknown'}{closed}; refused",), file_sha256=sha)
    if spec is not None and e.get("spec_sha256") != hasher(spec):
        return ApprovalResult(False, True, reasons=(f"{sid}: spec fingerprint mismatch; refused",), file_sha256=sha)
    if state not in APPROVABLE_STATES:
        return ApprovalResult(False, True, reasons=(f"{sid}: no strategy state is approvable in Milestone 1; refused",),
                              file_sha256=sha)
    return ApprovalResult(True, True, approved=e, file_sha256=sha)      # unreachable while APPROVABLE_STATES is empty
