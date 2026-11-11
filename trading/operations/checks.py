"""Pre-open and periodic checks. Each check records ok/failed with details; nothing is skipped silently.

Safety checks (dependency=0) failing means the runner must refuse to operate (a FAIL). Dependency
checks (dependency=1) failing at the final pre-open check means the session is INTERRUPTED.
"""

import shutil
import uuid
from pathlib import Path

from trading import safety
from trading.operations import ENVIRONMENT, approvals, data_health, killswitch, paths

MIN_FREE_BYTES = 1_000_000_000


def safety_checks(environment: str) -> list[tuple[str, bool, bool, dict]]:
    out = []
    enabled, mode = safety.order_submission_enabled(), safety.trading_mode()
    out.append(("order_guard_disabled", (not enabled) and mode == "paper", False,
                {"order_submission_enabled": enabled, "trading_mode": mode}))
    out.append(("environment_dry_run", environment == ENVIRONMENT, False, {"environment": environment}))
    try:
        d = paths.runtime_dir()
        out.append(("runtime_outside_onedrive", True, False, {"runtime_dir": str(d)}))
    except paths.RuntimeDirRefused as exc:
        out.append(("runtime_outside_onedrive", False, False, {"error": str(exc)}))
    return out


def local_checks(store, approvals_path: Path, monitor_db: Path, now) -> list[tuple[str, bool, bool, dict]]:
    out = []
    try:
        token = uuid.uuid4().hex
        store.event(None, None, now.isoformat(), "debug", "write_test", token)
        ok = bool(store.rows("SELECT 1 FROM events WHERE message=?", (token,)))
        out.append(("records_writable", ok, True, {"db": str(store.path)}))
    except Exception as exc:
        out.append(("records_writable", False, True, {"error": f"{type(exc).__name__}: {exc}"}))
    try:
        free = shutil.disk_usage(store.path.parent).free
        out.append(("disk_free", free >= MIN_FREE_BYTES, True, {"free_bytes": free, "minimum": MIN_FREE_BYTES}))
    except OSError as exc:
        out.append(("disk_free", False, True, {"error": str(exc)}))
    a = approvals.load_approval(approvals_path)
    out.append(("approvals_readable", a.readable, True, {"result": a.summary(), "reasons": list(a.reasons),
                                                          "file_sha256": a.file_sha256}))
    k = killswitch.state()
    out.append(("kill_switch_readable", "fail closed" not in k.reason, True, {"on": k.on, "reason": k.reason}))
    h = data_health.read(now, monitor_db)
    out.append(("monitor_worker_alive", h.worker_alive, True, {"feed": h.feed, "reasons": list(h.reasons[:3])}))
    return out


def broker_checks(client_factory, plan, now_fn, expected_ref: str | None = None) -> tuple[list, dict | None]:
    """credentials -> clock skew -> calendar agreement -> account status -> exposure. Returns (checks, clock).
    Exposure (no positions, no open orders) is broker evidence only; any failure to obtain it is a failed check."""
    from trading.operations import broker_checks as bc
    out, clock = [], None
    try:
        client = client_factory()
        out.append(("credentials_present", True, True, {"names": ["APCA_API_KEY_ID", "APCA_API_SECRET_KEY"]}))
    except Exception as exc:                       # MissingCredentials or anything else: never print values
        out.append(("credentials_present", False, True, {"error": type(exc).__name__}))
        return out, None
    try:
        clock = bc.clock_check(client, now_fn)
        out.append(("broker_clock_skew", clock["ok"], True, clock))
        ok, det = bc.calendar_agreement(clock, plan, now_fn())
        out.append(("calendar_agreement", ok, True, det))
    except Exception as exc:
        out.append(("broker_clock_skew", False, True, {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}))
    try:
        ok, det = bc.account_check(client)
        out.append(("account_status", ok, True, det))
    except Exception as exc:
        out.append(("account_status", False, True, {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}))
    ok, det = bc.exposure_check(client, now_fn, expected_ref)
    out.append(("exposure_none", ok, True, det))
    return out, clock
