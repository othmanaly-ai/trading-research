"""Trade journal and end-to-end research run. DEMO fixtures and fake API-shaped
historical data only (SYNTHETIC); these check consistency, not market behavior."""

import csv
import json
import threading
import urllib.error
import urllib.request

import pytest

from trading.dashboard.demo_replay import DEFAULT_CONFIG, build_demo, load_config
from trading.dashboard.ledger import Ledger
from trading.dashboard.server import create_server
from trading.history import HistoryError, fetch_and_store
from trading.journal import COLUMNS, build_journal
from trading.research_run import run

from tests.test_history import END, SESSIONS, START, alpaca_payloads, fake_client, hist_config


@pytest.fixture(scope="module")
def demo():
    d = build_demo(load_config(DEFAULT_CONFIG))
    ledger = Ledger(d.meta)
    for e in d.events:
        ledger.apply(e.to_dict())
    return d, ledger


def test_journal_matches_ledger_engine_and_report(demo):
    d, ledger = demo
    for sid, bt in d.backtests.items():
        rows = build_journal(ledger, sid)
        assert [r["session_date"] for r in rows] == [s["date"] for s in d.meta["sessions"]]
        net = sum(r["net_pnl"] or 0 for r in rows)
        assert net == pytest.approx(ledger.strategies[sid]["realized_pnl"], abs=1e-9)
        assert net == pytest.approx(bt.end_equity - bt.start_equity, abs=1e-9)
        assert net == pytest.approx(ledger.evaluation(sid)["pnl"]["net"], abs=1e-9)
        assert sum(1 for r in rows if r["decision"] == "enter") == len(bt.trades)
        for a, b in zip(rows, rows[1:]):
            assert b["equity_before"] == pytest.approx(a["equity_after"])
        assert all(r["mode"] == "DEMO_REPLAY" and r["spec_version"] == "1.3" for r in rows)
        assert set(rows[0]) == set(COLUMNS)


def test_skipped_and_blocked_sessions_are_journaled(demo):
    _, ledger = demo
    long_only = build_journal(ledger, "imom-spy-long")
    assert any(r["decision"] == "skip" and "long-only" in r["decision_reason"] for r in long_only)
    tight = build_journal(ledger, "imom-iwm-tight")
    blocked = [r for r in tight if r["decision"] == "skip"]
    assert blocked and blocked[-1]["risk_status"] == "halted"
    assert blocked[-1]["net_pnl"] is None and blocked[-1]["equity_after"] == blocked[-1]["equity_before"]


def test_journal_mid_replay_marks_session_in_progress(demo):
    d, _ = demo
    ledger = Ledger(d.meta)
    cut = next(i for i, e in enumerate(d.events) if e.type == "signal")   # first signal of session 1
    for e in d.events[:cut + 1]:
        ledger.apply(e.to_dict())
    rows = build_journal(ledger, "imom-spy")
    assert len(rows) == 1 and rows[0]["decision"] == "none"
    assert "in progress" in rows[0]["decision_reason"]


def test_demo_research_run_writes_consistent_outputs(tmp_path, demo):
    _, ledger = demo
    log = tmp_path / "inspection.csv"
    summary = run("demo", results_root=tmp_path / "out", inspection_log=log)
    assert summary["mode"] == "DEMO_REPLAY"
    for s in summary["strategies"]:
        assert s["result_hash"] == ledger.evaluation(s["strategy_id"])["result_hash"]
        out = tmp_path / "out" / "demo_replay"
        journal = next(out.glob(f"*/{s['strategy_id']}_journal.csv"))
        with journal.open() as f:
            assert len(list(csv.DictReader(f))) == s["sessions"]
        prov = json.loads(journal.with_suffix(".provenance.json").read_text())
        assert prov["mode"] == "DEMO_REPLAY" and "synthetic" in prov["banner"]
    assert not log.exists()        # demo runs are not research records


def test_historical_research_run_logs_inspection(tmp_path):
    days, minute, daily = alpaca_payloads(SESSIONS)
    root = tmp_path / "history"
    fetch_and_store(fake_client(minute, daily), "SPY", START, END, "sip", "all", root=root)
    cfg = tmp_path / "h.json"
    cfg.write_text(json.dumps(hist_config()))
    log = tmp_path / "inspection.csv"
    summary = run("historical", cfg, history_root=root, results_root=tmp_path / "out", inspection_log=log)
    assert summary["mode"] == "HISTORICAL_REPLAY"
    with log.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["feed"] == "sip" and rows[0]["variant_id"]
    assert rows[0]["result_hash"] == summary["strategies"][0]["result_hash"]
    run("historical", cfg, history_root=root, results_root=tmp_path / "out", inspection_log=log)
    with log.open() as f:
        again = list(csv.DictReader(f))
    # A repeat is recorded, and its identical hash marks it as a reproducibility check.
    assert len(again) == 2 and again[1]["result_hash"] == again[0]["result_hash"]


def test_historical_research_run_refuses_without_data(tmp_path):
    cfg = tmp_path / "h.json"
    cfg.write_text(json.dumps(hist_config()))
    with pytest.raises(HistoryError):
        run("historical", cfg, history_root=tmp_path / "none", results_root=tmp_path / "out",
            inspection_log=tmp_path / "log.csv")
    assert not (tmp_path / "out").exists()


def test_journal_endpoints():
    httpd, ctrl, stop = create_server(None, 0, speed=3600, run_jobs=False, supervise_monitor=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        while not ctrl.status()["finished"]:
            ctrl.tick(10.0)
        with urllib.request.urlopen(base + "/api/strategies/imom-qqq/journal", timeout=10) as r:
            body = json.loads(r.read())
        assert body["mode"] == "DEMO_REPLAY" and len(body["rows"]) == 5
        with urllib.request.urlopen(base + "/api/strategies/imom-qqq/journal.csv", timeout=10) as r:
            assert r.headers["Content-Type"].startswith("text/csv")
            lines = r.read().decode().splitlines()
        assert lines[0].split(",") == COLUMNS and len(lines) == 6
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(base + "/api/strategies/nope/journal", timeout=10)
        assert err.value.code == 404
    finally:
        stop.set()
        httpd.shutdown()
        httpd.server_close()
