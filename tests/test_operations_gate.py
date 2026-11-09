"""SYNTHETIC: approvals registry, kill switch and entry-permission gate (no network)."""

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from trading.operations import approvals as ap
from trading.operations import gate as g
from trading.operations import killswitch as ks
from trading.operations import paths

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 10, 15, 0, 20, tzinfo=timezone.utc)
MIN = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)


def green(**over):
    base = dict(environment="DRY_RUN", approval=ap.ApprovalResult(True, True, approved={"strategy_id": "x"}),
                phase="DECISION_WINDOW", decision_minute_utc=MIN, now_utc=NOW,
                data=g.DataHealth(True, "iex", {}, ()), risk_reasons=(), kill_switch=ks.KillSwitchState(False, "off"),
                clock_ok=True, records_ok=True, reconciliation_ok=True)
    base.update(over)
    return g.GateInputs(**base)


def test_dry_run_denies_even_when_everything_else_is_green():
    p = g.evaluate(green())
    assert not p.allowed and p.reasons == ("environment DRY_RUN never permits entries",)


def test_undefined_environment_is_refused():
    for env in ("PAPER", "LIVE", ""):
        p = g.evaluate(green(environment=env))
        assert not p.allowed and "not defined in Milestone 1" in p.reasons[0]


def test_every_failing_condition_is_reported():
    p = g.evaluate(green(approval=ap.ApprovalResult(False, True, reasons=("no approved strategy",)), phase="CLOSING",
                         now_utc=MIN.replace(minute=2), data=None, risk_reasons=None,
                         kill_switch=ks.KillSwitchState(True, "owner test"), clock_ok=None, records_ok=False))
    text = " | ".join(p.reasons)
    for frag in ("DRY_RUN", "no approved strategy", "phase CLOSING", "never replayed", "data health unavailable",
                 "risk state unavailable", "kill switch ON: owner test", "clock not verified", "records not writable"):
        assert frag in text
    assert "skew" in " ".join(g.evaluate(green(clock_ok=False)).reasons)


def test_empty_registry_means_no_approved_strategy():
    r = ap.load_approval()                                   # the real, committed file
    assert r.readable and not r.ok and r.reasons == ("no approved strategy",) and r.summary() == "approved: NONE"


def write(tmp_path, entries, schema=1):
    p = tmp_path / "approved.json"
    p.write_text(json.dumps({"schema": schema, "approved": entries}), encoding="utf-8")
    return p


def test_closed_failed_deferred_unknown_and_multiple_are_refused(tmp_path):
    cases = {"intraday_momentum": "FAILED_DEVELOPMENT (closed)", "opening_range_breakout": "FAILED_DEVELOPMENT (closed)",
             "gap_down_opening": "DEFERRED_DATA_SEMANTICS",
             "made_up": "unknown strategy"}
    for sid, frag in cases.items():
        r = ap.load_approval(write(tmp_path, [{"strategy_id": sid}]))
        assert not r.ok and frag.lower() in r.reasons[0].lower(), (sid, r.reasons)
    assert "more than one" in ap.load_approval(write(tmp_path, [{"strategy_id": "a"}, {"strategy_id": "b"}])).reasons[0]
    assert not ap.load_approval(write(tmp_path, [], schema=2)).readable


def test_missing_or_corrupt_file_fails_closed(tmp_path):
    assert not ap.load_approval(tmp_path / "missing.json").ok
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    r = ap.load_approval(bad)
    assert not r.ok and not r.readable and "fail closed" in r.reasons[0]


def test_fingerprint_mismatch_and_no_approvable_state(tmp_path):
    """SYNTHETIC strategy tree: an open (not closed) strategy is still refused in Milestone 1."""
    from trading.strategies import registry
    spec = tmp_path / "research" / "001_intraday_momentum" / "SPEC.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("Spec version: 9.9\nSYNTHETIC\n", encoding="utf-8")
    (spec.parent / "STATUS.json").write_text(json.dumps({"state": "OPEN_SYNTHETIC"}), encoding="utf-8")
    bad = ap.load_approval(write(tmp_path, [{"strategy_id": "intraday_momentum", "spec_sha256": "000000000000"}]), root=tmp_path)
    assert "fingerprint mismatch" in bad.reasons[0]
    good_hash = registry.spec_hash(spec)
    r = ap.load_approval(write(tmp_path, [{"strategy_id": "intraday_momentum", "spec_sha256": good_hash}]), root=tmp_path)
    assert not r.ok and "no strategy state is approvable in Milestone 1" in r.reasons[0]


def test_kill_switch_on_off_and_fail_closed(tmp_path):
    p = tmp_path / "KILL_SWITCH.json"
    assert not ks.state(p).on
    ks.set_on("SYNTHETIC drill", path=p)
    assert ks.state(p) == ks.KillSwitchState(True, "SYNTHETIC drill")
    with pytest.raises(ValueError):
        ks.set_off("  ", path=p)
    ks.set_off("SYNTHETIC drill over", path=p)
    assert not ks.state(p).on and len((tmp_path / "kill_switch_history.jsonl").read_text().splitlines()) == 2
    p.write_text("{garbage", encoding="utf-8")
    assert ks.state(p).on and "fail closed" in ks.state(p).reason


def test_runtime_dir_refuses_onedrive_and_project(monkeypatch, tmp_path):
    monkeypatch.setenv("TRADING_OPS_DIR", str(ROOT / "data" / "ops"))
    with pytest.raises(paths.RuntimeDirRefused):
        paths.runtime_dir()
    monkeypatch.setenv("TRADING_OPS_DIR", str(tmp_path / "OneDrive" / "x"))
    with pytest.raises(paths.RuntimeDirRefused):
        paths.runtime_dir()
    monkeypatch.setenv("TRADING_OPS_DIR", str(tmp_path / "ops"))
    assert paths.runtime_dir() == tmp_path / "ops"
    monkeypatch.delenv("TRADING_OPS_DIR")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert paths.runtime_dir() == tmp_path / "Local" / "TradingProject" / "operations"


WRITE_CALLS = {"post", "put", "patch", "delete"}
FORBIDDEN_NAMES = ("submit_order", "place_order", "cancel_order", "replace_order", "close_position", "/v2/orders",
                   "/v2/positions", "ORDER_SUBMISSION_ENABLED=true")


def test_operations_package_has_no_order_capable_code():
    """Static check of every module in trading/operations: no HTTP write verbs, no order endpoints,
    and no import of anything except the read-only client for broker access."""
    for f in sorted((ROOT / "trading" / "operations").glob("*.py")):
        src = f.read_text(encoding="utf-8")
        for name in FORBIDDEN_NAMES:
            assert name not in src, (f.name, name)
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in WRITE_CALLS, (f.name, node.func.attr, node.lineno)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for m in mods:
                    assert "order" not in m.lower() and "execution" not in m.lower(), (f.name, m)
