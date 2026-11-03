"""Historical store and HISTORICAL REPLAY mode, tested with SYNTHETIC bars shaped
like Alpaca API responses (fake HTTP, no network, no keys). These tests check the
code path only; they say nothing about the real API or real prices."""

import json
from datetime import date

import pandas as pd
import pytest

from trading.alpaca_client import ReadOnlyAlpacaClient
from trading.dashboard.historical_replay import build_historical
from trading.dashboard.ledger import Ledger
from trading.dashboard.server import create_server, research_status
from trading.fixtures.synthetic import make_days
from trading.history import HistoryError, fetch_and_store, load_days, read_manifest
from trading import history as history_mod
from trading.sessions import sessions_between

from tests.test_alpaca_client import FakeHttp, FakeResponse

START, END = date(2016, 1, 4), date(2016, 3, 4)       # development period
SESSIONS = sessions_between(START, END)


def alpaca_payloads(sessions, broken_day=None):
    """Minute bars (with one pre-market bar per day) and daily bars, as Alpaca dicts."""
    days = make_days(sessions, seed=21, start_price=200.0, volume=1_000_000)
    minute, daily = [], []
    for s in sessions:
        d = days[s.date]
        pre = pd.Timestamp(s.open_utc) - pd.Timedelta(minutes=90)
        minute.append({"t": pre.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": 1, "h": 1, "l": 1, "c": 1, "v": 1, "n": 1, "vw": 1})
        for t, b in d.bars.iterrows():
            minute.append({"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": b["open"], "h": b["high"], "l": b["low"],
                           "c": b["close"], "v": int(b["volume"]), "n": 10, "vw": b["close"]})
        if s.date == broken_day:
            minute.append(dict(minute[-1]))                    # duplicate timestamp
        midnight_et = pd.Timestamp(str(s.date), tz="America/New_York").tz_convert("UTC")
        c = d.official_close
        daily.append({"t": midnight_et.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": c, "h": c * 1.01, "l": c * 0.99,
                      "c": c, "v": 1, "n": 1, "vw": c})
    return days, minute, daily


def fake_client(minute, daily):
    half = len(minute) // 2
    return ReadOnlyAlpacaClient("KEY", "SECRET", http=FakeHttp([
        FakeResponse(200, {"bars": {"SPY": minute[:half]}, "next_page_token": "p2"}),
        FakeResponse(200, {"bars": {"SPY": minute[half:]}, "next_page_token": None}),
        FakeResponse(200, {"bars": {"SPY": daily}, "next_page_token": None}),
    ]))


@pytest.fixture
def store(tmp_path):
    broken = SESSIONS[30].date
    days, minute, daily = alpaca_payloads(SESSIONS, broken_day=broken)
    manifest = fetch_and_store(fake_client(minute, daily), "SPY", START, END, "sip", "all", root=tmp_path)
    return tmp_path, days, manifest, broken


def test_store_keeps_regular_session_and_records_provenance(store):
    root, _, m, broken = store
    assert m["requested_feed"] == "sip" and m["adjustment"] == "all" and m["source"] == "alpaca_rest"
    assert m["requests"]["minute_pages"] == 2
    assert m["summary"]["expected_sessions"] == len(SESSIONS)
    assert m["summary"]["usable_sessions"] == len(SESSIONS) - 1
    assert m["summary"]["by_period"]["development"] == len(SESSIONS) - 1
    ok = m["sessions"][str(SESSIONS[0].date)]
    assert ok["rows"] == 390 and ok["present_minutes"] == 390 and ok["usable"]
    assert m["sessions"][str(broken)]["usable"] is False
    assert m["sessions"][str(broken)]["structure"]["duplicate_timestamps"] == 1
    assert m["requests"]["pagination_complete"] is True
    assert m["requests"]["minute_received"][0] < m["requests"]["minute_requested"][0]  # pre-market bar
    assert ok["missing_minutes"] == 0
    assert m["transformations"] and m["limitations"]
    assert not any(m["daily_structure"][k] for k in m["daily_structure"] if k != "rows")


def test_raw_responses_kept_unmodified(store):
    root, _, m, _ = store
    raw = pd.read_csv(root / "SPY" / "sip" / "all" / "raw" / "minute_all_hours.csv")
    assert len(raw) == m["requests"]["minute_rows_all_hours"]      # includes pre-market and the duplicate
    assert list(raw.columns[:6]) == ["t", "o", "h", "l", "c", "v"]


def test_load_days_round_trip_and_excludes_unusable(store):
    root, days, _, broken = store
    loaded = load_days("SPY", "sip", "all", SESSIONS, root)
    assert broken not in loaded and len(loaded) == len(SESSIONS) - 1
    d = SESSIONS[5].date
    assert loaded[d].official_close == pytest.approx(days[d].official_close)
    assert loaded[d].bars["close"].to_numpy() == pytest.approx(days[d].bars["close"].to_numpy())
    assert loaded[d].bars.index[0] == pd.Timestamp(SESSIONS[5].open_utc)


def test_final_period_download_refused(tmp_path):
    with pytest.raises(HistoryError, match="final"):
        fetch_and_store(fake_client([], []), "SPY", date(2024, 7, 1), date(2024, 7, 10), "sip", "all",
                        root=tmp_path)


def hist_config(first="2016-02-10", periods=("development",)):
    return {"symbol": "SPY", "feed": "sip", "adjustment": "all", "first_session": first, "sessions": 5,
            "warmup_sessions": 25, "allowed_periods": list(periods),
            "instances": [{"id": "h1", "name": "Intraday Momentum", "instrument": "SPY",
                           "allocation": 100000, "params": {}}]}


def test_historical_replay_mode_and_totals(store):
    root, *_ = store
    rep = build_historical(hist_config(), root)
    assert rep.meta["mode"] == "HISTORICAL_REPLAY" and rep.meta["source"] == "alpaca_history"
    assert "HISTORICAL REPLAY" in rep.meta["banner"] and "SIP" in rep.meta["banner"]
    assert rep.meta["provenance"]["requested_feed"] == "sip"
    assert all(e.mode == "HISTORICAL_REPLAY" for e in rep.events)
    ledger = Ledger(rep.meta)
    for e in rep.events:
        ledger.apply(e.to_dict())
    s = ledger.snapshot()["strategies"][0]
    bt = rep.backtests["h1"]
    assert s["realized_pnl"] == pytest.approx(bt.end_equity - bt.start_equity, abs=1e-9)
    assert ledger.evaluation("h1")["mode"] == "HISTORICAL_REPLAY"


@pytest.mark.parametrize("first, periods", [("2022-03-01", ("development",)),
                                            ("2024-08-01", ("development", "validation", "final"))])
def test_held_out_periods_refused(store, first, periods):
    root, *_ = store
    with pytest.raises(HistoryError, match="allowed periods"):
        build_historical(hist_config(first, periods), root)


def test_missing_data_refuses_without_fallback(tmp_path):
    with pytest.raises(HistoryError, match="No stored SPY sip history"):
        build_historical(hist_config(), tmp_path)
    cfg = tmp_path / "h.json"
    cfg.write_text(json.dumps(hist_config()))
    with pytest.raises(HistoryError):
        create_server(cfg, 0, mode="historical", history_root=tmp_path)


def test_research_status_reflects_stored_coverage(store, tmp_path_factory):
    root, *_ = store
    cfg = tmp_path_factory.mktemp("cfg") / "h.json"
    cfg.write_text(json.dumps(hist_config()))
    r = research_status(root, cfg)
    assert r["modes"]["HISTORICAL_REPLAY"]["available"] is True
    dev = next(p for p in r["historical_periods"] if p["period"] == "development")
    assert dev["sessions_with_verified_data"] == len(SESSIONS) - 1
    empty = research_status(tmp_path_factory.mktemp("empty"), cfg)
    assert empty["modes"]["HISTORICAL_REPLAY"]["available"] is False


def test_cli_blocked_without_credentials(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    monkeypatch.setattr(history_mod, "HISTORY_DIR", tmp_path)
    if (history_mod.PROJECT_ROOT / ".env").exists():
        pytest.skip("a real .env exists; not exercising the no-credentials path")
    assert history_mod.main(["--start", "2016-01-04", "--end", "2016-01-29"]) == 2
    assert "BLOCKED" in capsys.readouterr().out
    assert read_manifest("SPY", "sip", "all", tmp_path) is None
