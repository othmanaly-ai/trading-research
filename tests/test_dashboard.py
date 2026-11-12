"""DEMO REPLAY backend tests. All data is SYNTHETIC; results are simulated."""

import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from trading.dashboard.demo_replay import (
    DEFAULT_CONFIG, ConfigError, build_demo, load_config,
)
from trading.dashboard.ledger import Ledger
from trading.dashboard.server import ReplayController, create_server

ROOT = Path(__file__).resolve().parent.parent
EMPTY_CONFIG = ROOT / "dashboard" / "empty_config.json"


@pytest.fixture(scope="module")
def demo():
    return build_demo(load_config(DEFAULT_CONFIG))


def replay_all(demo, twice=False):
    ledger = Ledger(demo.meta)
    for e in demo.events:
        ledger.apply(e.to_dict())
        if twice:
            ledger.apply(e.to_dict())
    return ledger


def test_every_event_has_required_fields(demo):
    for e in demo.events:
        d = e.to_dict()
        assert {"event_id", "ts_utc", "source", "mode", "strategy_id", "instrument",
                "type", "payload"} <= d.keys()
        assert d["mode"] == "DEMO_REPLAY" and d["source"] == "demo_replay"
        assert d["ts_utc"].endswith("Z")
    assert len({e.event_id for e in demo.events}) == len(demo.events)


def test_build_is_deterministic(demo):
    again = build_demo(load_config(DEFAULT_CONFIG))
    assert [e.event_id for e in again.events] == [e.event_id for e in demo.events]


def test_events_are_time_ordered(demo):
    keys = [e.sort_key() for e in demo.events]
    assert keys == sorted(keys)


def test_replay_totals_match_engine(demo):
    snap = replay_all(demo).snapshot()
    for s in snap["strategies"]:
        bt = demo.backtests[s["id"]]
        assert s["trades"] == len(bt.trades)
        assert s["realized_pnl"] == pytest.approx(bt.end_equity - bt.start_equity, abs=1e-9)
        assert s["unrealized_pnl"] == 0.0
        session_sum = sum(r["per_strategy"][s["id"]]["realized_pnl"] for r in snap["sessions"])
        assert session_sum == pytest.approx(s["realized_pnl"], abs=1e-9)
    acct = snap["account"]
    assert acct["realized_pnl"] == pytest.approx(sum(s["realized_pnl"] for s in snap["strategies"]))
    assert acct["equity"] == pytest.approx(acct["start_equity"] + acct["realized_pnl"]
                                           + acct["unrealized_pnl"])


def test_duplicates_do_not_double_count(demo):
    once, twice = replay_all(demo).snapshot(), replay_all(demo, twice=True).snapshot()
    assert twice["duplicates_ignored"] == len(demo.events)
    for key in ("account", "strategies", "sessions"):
        assert once[key] == twice[key]


def test_wrong_mode_event_rejected(demo):
    ledger = Ledger(demo.meta)
    ev = demo.events[0].to_dict() | {"mode": "LIVE", "event_id": "x"}
    assert ledger.apply(ev) is False and ledger.rejected == 1


def test_unrealized_is_marked_while_open_and_zero_after(demo):
    """Ledger unrealized = engine's net-if-closed at the bar close, after modeled exit costs."""
    from trading.backtest import _net_if_closed
    from trading.costs import BASE
    entries = {}
    ledger = Ledger(demo.meta)
    marked = False
    for e in demo.events:
        ledger.apply(e.to_dict())
        if e.type == "fill" and e.payload["leg"] == "entry":
            entries[e.strategy_id] = e.payload["reference_price"]
        for s in ledger.strategies.values():
            if s["position"] and e.type == "bar" and e.instrument == s["instrument"]:
                pos = s["position"]
                assert s["unrealized_pnl"] == pytest.approx(_net_if_closed(
                    BASE, pos["direction"], pos["shares"], entries[s["id"]], e.payload["c"]))
                marked = True
    assert marked
    assert all(s["unrealized_pnl"] == 0 for s in ledger.strategies.values())


def test_strategy_records_belong_to_that_strategy(demo):
    ledger = replay_all(demo)
    ids = {e.event_id: e for e in demo.events}
    for sid, bt in demo.backtests.items():
        rec = ledger.strategy_records(sid)
        for kind in ("signals", "decisions", "fills", "trades", "risk"):
            assert all(ids[r["event_id"]].strategy_id == sid for r in rec[kind])
        assert [round(t["net_pnl"], 9) for t in rec["trades"]] == \
            [round(t.net_pnl, 9) for t in bt.trades]
        assert len(rec["fills"]) == 2 * len(bt.trades)
    assert ledger.strategy_records("does-not-exist") is None


def test_risk_halt_is_shown(demo):
    snap = replay_all(demo).snapshot()
    tight = next(s for s in snap["strategies"] if s["id"] == "imom-iwm-tight")
    assert tight["risk_status"] == "halted" and tight["status"] == "HALTED (RISK)"
    assert snap["account"]["risk_status"] == "ATTENTION"


def test_feed_outage_produces_stale_then_live(demo):
    feed = [(e.ts_utc, e.payload["status"]) for e in demo.events
            if e.type == "feed_status" and e.instrument == "QQQ.SYN" and e.ts_utc.startswith("2026-11-24T16")]
    assert [s for _, s in feed] == ["stale", "live"]


def test_empty_config(tmp_path):
    demo = build_demo(load_config(EMPTY_CONFIG))
    snap = replay_all(demo).snapshot()
    assert snap["strategies"] == [] and snap["account"]["risk_status"] == "NO STRATEGIES"


def test_invalid_config_rejected(tmp_path):
    cfg = json.loads(DEFAULT_CONFIG.read_text())
    cfg["instances"][0]["instrument"] = "NOPE"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(cfg))
    with pytest.raises(ConfigError):
        load_config(bad)


def test_controller_replay_with_injected_duplicates_matches_direct(demo):
    ctrl = ReplayController(demo, start_speed=3600, duplicate_every=50)
    while not ctrl.status()["finished"]:
        ctrl.tick(10.0)
    snap = ctrl.snapshot()
    assert snap["duplicates_ignored"] > 0
    direct = replay_all(demo).snapshot()
    assert snap["account"] == direct["account"] and snap["strategies"] == direct["strategies"]


def test_controller_pause_restart_speed(demo):
    ctrl = ReplayController(demo, start_speed=600)
    ctrl.tick(5.0)
    cursor = ctrl.cursor
    assert cursor > 0
    ctrl.control("pause")
    ctrl.tick(5.0)
    assert ctrl.cursor == cursor
    ctrl.control("resume")
    ctrl.tick(5.0)
    assert ctrl.cursor > cursor
    gen = ctrl.generation
    ctrl.control("restart")
    assert ctrl.cursor == 0 and ctrl.generation == gen + 1 and ctrl.ledger.applied == 0
    assert ctrl.control("speed", 10**9)["speed"] == 3600
    with pytest.raises(ValueError):
        ctrl.control("submit_order")


@pytest.fixture(scope="module")
def server():
    httpd, ctrl, stop = create_server(DEFAULT_CONFIG, 0, speed=3600, run_jobs=False, supervise_monitor=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    stop.set()
    httpd.shutdown()
    httpd.server_close()


def _get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, json.loads(r.read())


def _post(url, body, header=True):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          **({"X-Dashboard-Control": "1"} if header else {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_http_endpoints(server):
    status, meta = _get(server + "/api/meta")
    assert status == 200 and meta["mode"] == "DEMO_REPLAY" and meta["order_submission"] == "disabled"
    status, body = _get(server + "/api/snapshot")
    assert status == 200 and body["snapshot"]["mode"] == "DEMO_REPLAY"
    status, rec = _get(server + "/api/strategies/imom-spy")
    assert status == 200 and rec["strategy"]["id"] == "imom-spy"
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(server + "/api/strategies/nope", timeout=10)
    assert err.value.code == 404


def test_control_requires_header_and_valid_action(server):
    assert _post(server + "/api/control", {"action": "pause"}, header=False)[0] == 403
    assert _post(server + "/api/control", {"action": "place_order"})[0] == 400
    status, st = _post(server + "/api/control", {"action": "pause"})
    assert status == 200 and st["playing"] is False
    assert _post(server + "/api/control", {"action": "resume"})[1]["playing"] is True


def test_stream_starts_with_reset(server):
    with urllib.request.urlopen(server + "/api/stream", timeout=10) as r:
        assert r.headers["Content-Type"] == "text/event-stream"
        first = r.readline().decode()
    assert first.startswith("event: reset")


def test_server_never_loads_broker_code():
    code = ("import sys, trading.dashboard.server; "
            "print(any(m in sys.modules for m in ('trading.alpaca_client', 'requests')))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert out.stdout.strip() == "False", out.stderr


def test_candidates_overview_lists_deferred_candidate_read_only():
    from trading.dashboard import server as srv
    from trading import jobs
    c = {x["candidate"]: x for x in srv.candidates_overview()}
    g = c["gap_down_opening"]
    assert g["status"]["state"] == "DEFERRED_DATA_SEMANTICS" and g["status"]["performance_evaluated"] is False
    assert g["status"]["blockers"] and not g["problems"]
    assert "gap_down_opening" not in jobs.ALLOWED_EXPERIMENTS          # no pipeline can run on it


def test_candidates_overview_tolerates_corrupt_status(tmp_path):
    from trading.dashboard import server as srv
    (tmp_path / "research" / "candidates" / "x").mkdir(parents=True)
    (tmp_path / "research" / "candidates" / "x" / "STATUS.json").write_text("{not json", encoding="utf-8")
    out = srv.candidates_overview(tmp_path / "research" / "candidates")
    assert out[0]["status"] is None and "unreadable" in out[0]["problems"][0]


def test_depmap_endpoint_is_read_only_and_has_no_execution_path(server, tmp_path, monkeypatch):
    from trading.dashboard import server as srv
    monkeypatch.setattr(srv, "JOBS_DB", tmp_path / "no-jobs.sqlite")      # isolated: never the real job store
    status, body = _get(server + "/api/depmap")
    assert status == 200
    ids = {n["id"] for n in body["nodes"]}
    assert {"alpaca_iex", "monitor_worker", "quality", "report", "model_review"} <= ids
    assert not any(k in i for i in ids for k in ("order", "execution"))
    assert all(set(e["kinds"]) <= {"declared", "recorded", "proposed"} for e in body["edges"])
    assert not (tmp_path / "no-jobs.sqlite").exists()                      # reading created nothing


def test_csp_allows_only_the_local_agency_workspace(server):
    """The city workspace switcher may frame the separate Website Agency board and read its
    health check; nothing else from outside this server is allowed, and this page can't be framed."""
    with urllib.request.urlopen(server + "/api/meta", timeout=10) as r:
        csp = r.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-src http://127.0.0.1:4310 http://localhost:4310" in csp
    assert "connect-src 'self' http://127.0.0.1:4310 http://localhost:4310" in csp
    assert "frame-ancestors 'none'" in csp
    assert "script-src" not in csp            # scripts stay same-origin via default-src


def test_workspace_switcher_is_navigation_only():
    """Switching workspaces must not call this dashboard's API (monitor, research, settings, orders)."""
    js = (Path(__file__).resolve().parents[1] / "dashboard" / "web" / "public" / "workspaces.js").read_text(encoding="utf-8")
    assert "/api/" in js and js.count("/api/") == 1 and "/api/health" in js    # only the agency health probe
    assert "127.0.0.1:4310" in js and "8765" not in js
    for forbidden in ("/api/control", "/api/monitor", "/api/pipelines", "X-Dashboard-Control", "method:"):
        assert forbidden not in js
