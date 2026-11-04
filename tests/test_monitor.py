"""Market-monitoring worker. ALL MARKET DATA IN THIS FILE IS SYNTHETIC (labelled fixtures): the
fake client never touches the network, prices are invented, and nothing here is evidence of
market behaviour. Real read-only access is verified separately (python -m trading.monitor run)."""

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest
import requests

from trading.alpaca_client import AlpacaAccessError, MissingCredentials
from trading.monitor import control
from trading.monitor import store as mst
from trading.monitor.worker import BACKOFF, Worker

UTC = timezone.utc
OPEN_DAY = datetime(2026, 11, 4, 14, 30, tzinfo=UTC)          # Wed 4 Nov 2026, 09:30 ET open


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += timedelta(seconds=seconds)


def synthetic_bar(t: datetime, price=100.0):
    """SYNTHETIC bar in Alpaca's shape; values are invented."""
    return {"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": price, "h": price + 0.1, "l": price - 0.1,
            "c": price, "v": 1000, "n": 10, "vw": price}


class FakeClient:
    """SYNTHETIC stand-in for ReadOnlyAlpacaClient.get_bars_multi; records each request."""

    def __init__(self, clock, script=None):
        self.clock, self.script, self.calls = clock, list(script or []), []

    def get_bars_multi(self, symbols, timeframe, start, end, feed, adjustment):
        self.calls.append({"symbols": symbols, "start": start, "end": end, "feed": feed})
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, Exception):
                raise step
            if step is not None:
                return step
        s, e = mst.parse(start), mst.parse(end)
        out, t = {sym: [] for sym in symbols}, s
        while t <= e:
            for sym in symbols:
                out[sym].append(synthetic_bar(t))
            t += timedelta(minutes=1)
        return {"bars": out, "pages": 1}


@pytest.fixture
def env():
    store = mst.MonitorStore()
    yield store
    store.close()


def make_worker(store, clock, client=None, quality=False, **kw):
    client = client or FakeClient(clock)
    w = Worker(store, clock=clock, client_factory=lambda sleep: client, pid=1234, **kw)
    if not quality:
        w.quality = None             # live-polling tests; the quality checker has its own tests
    return w, client


# ---- lifecycle ------------------------------------------------------------------------

def test_single_worker_lock_start_stop_and_release(env):
    clock = Clock(OPEN_DAY + timedelta(minutes=10))
    env.set_desired("running", "test")
    w1, _ = make_worker(env, clock)
    assert w1.start()
    w2, c2 = make_worker(env, clock)
    assert not w2.start() and c2.calls == []                          # duplicate refused
    assert any(e["kind"] == "duplicate" for e in env.events())
    env.set_desired("stopped", "test")
    w1.step()
    assert w1.stopping
    w1.shutdown("stop requested")
    assert env.worker()["state"] == "stopped"
    w3, _ = make_worker(env, clock)
    assert w3.start()                                                 # lock released on stop
    w3.shutdown("test done")


def test_run_loop_exits_on_stop_and_records_it(env):
    clock = Clock(OPEN_DAY + timedelta(minutes=10))
    env.set_desired("running", "test")
    w, client = make_worker(env, clock)
    ticks = []

    def sleep(s):
        ticks.append(s)
        clock.advance(max(s, 1))
        if len(ticks) == 3:
            env.set_desired("stopped", "test")
    assert w.run(sleep=sleep) == 0
    assert env.worker()["state"] == "stopped" and env.worker()["exit_reason"] == "stop requested"
    assert len(client.calls) == 1                                    # one poll; next poll not yet due


def test_pause_makes_no_calls_and_resume_polls(env):
    clock = Clock(OPEN_DAY + timedelta(minutes=10))
    w, client = make_worker(env, clock)
    assert w.start()
    env.set_desired("paused", "test")
    for _ in range(5):
        w.step()
        clock.advance(60)
    w.step()                                     # heartbeat at the time we read the status
    assert client.calls == [] and env.worker()["state"] == "paused"
    assert env.status(clock())["symbols"][0]["freshness"] == "PAUSED"
    env.set_desired("running", "test")
    w.step()
    assert len(client.calls) == 1 and env.worker()["state"] == "running"


# ---- calendar ------------------------------------------------------------------------

@pytest.mark.parametrize("when, reason", [
    (datetime(2026, 11, 7, 15, 0, tzinfo=UTC), "weekend or exchange holiday"),       # Saturday
    (datetime(2026, 11, 26, 15, 0, tzinfo=UTC), "weekend or exchange holiday"),      # Thanksgiving
    (datetime(2026, 11, 4, 13, 0, tzinfo=UTC), "before the open"),
])
def test_market_closed_makes_no_api_calls(env, when, reason):
    clock = Clock(when)
    env.set_desired("running", "test")
    w, client = make_worker(env, clock)
    w.start()
    for _ in range(3):
        w.step()
        clock.advance(30)
    w.step()
    assert client.calls == [] and env.worker()["state"] == "market_closed"
    s = env.status(clock())
    assert s["market"]["open"] is False and s["market"]["reason"] == reason
    assert all(r["freshness"] == "MARKET CLOSED" for r in s["symbols"])


def test_one_catch_up_poll_after_close_then_idle(env):
    clock = Clock(datetime(2026, 11, 4, 20, 50, tzinfo=UTC))        # 15:50 ET
    env.set_desired("running", "test")
    w, client = make_worker(env, clock)
    w.start()
    w.step()
    clock.t = datetime(2026, 11, 4, 21, 5, tzinfo=UTC)              # 16:05 ET, after the close
    for _ in range(5):
        w.step()
        clock.advance(60)
    assert len(client.calls) == 2                                    # the 15:50 poll + one catch-up
    assert client.calls[1]["end"] == "2026-11-04T20:59:59+00:00"     # nothing after the close
    assert env.last_bar("SPY", "iex")["t_utc"] == "2026-11-04T20:59:00+00:00"
    assert env.worker()["state"] == "market_closed"


def test_early_close_session_window(env):
    clock = Clock(datetime(2026, 11, 27, 18, 30, tzinfo=UTC))       # day after Thanksgiving, closed 13:00 ET
    env.set_desired("running", "test")
    w, client = make_worker(env, clock)
    w.start()
    w.step()
    assert client.calls and client.calls[0]["end"] == "2026-11-27T17:59:59+00:00"


# ---- polling, duplicates, freshness ---------------------------------------------------

def test_poll_excludes_partial_minute_and_ignores_duplicates(env):
    clock = Clock(OPEN_DAY + timedelta(minutes=5, seconds=30))
    env.set_desired("running", "test")
    overlap = FakeClient(clock)
    w, client = make_worker(env, clock, client=overlap)
    w.start()
    w.step()
    assert client.calls[0]["start"] == "2026-11-04T14:30:00+00:00"
    assert client.calls[0]["end"] == "2026-11-04T14:34:59+00:00"     # 14:35 minute still in progress
    assert env.count_session("SPY", "iex", "2026-11-04") == 5
    # The provider repeats already-stored bars (e.g. after a reconnect): nothing is duplicated.
    repeat = {"bars": {s: [synthetic_bar(OPEN_DAY + timedelta(minutes=m)) for m in range(7)]
                       for s in mst.DEFAULT_SYMBOLS}, "pages": 1}
    client.script = [repeat]
    clock.advance(90)
    w.step()
    assert env.count_session("SPY", "iex", "2026-11-04") == 7
    wk = env.worker()
    assert wk["duplicates_ignored"] == 15 and wk["bars_inserted"] == 21
    n = env.db.execute("SELECT COUNT(*), COUNT(DISTINCT symbol||t_utc) FROM bars").fetchone()
    assert n[0] == n[1]


def test_freshness_fresh_then_stale_with_iex_note(env):
    clock = Clock(OPEN_DAY + timedelta(minutes=10, seconds=5))
    env.set_desired("running", "test")
    w, _ = make_worker(env, clock)
    w.start()
    w.step()
    s = env.status(clock())
    assert all(r["freshness"] == "FRESH" for r in s["symbols"])
    assert s["symbols"][0]["last_bar_end_utc"] == "2026-11-04T14:40:00+00:00"
    # Ten minutes with no new bars while the worker is alive (heartbeat refreshed).
    clock.advance(600)
    env.update_worker(heartbeat_utc=mst.iso(clock()))
    s = env.status(clock())
    assert s["symbols"][0]["freshness"] == "STALE" and "not necessarily an outage" in s["symbols"][0]["freshness_detail"]


def test_dead_worker_shows_disconnected(env):
    clock = Clock(OPEN_DAY + timedelta(minutes=10))
    env.set_desired("running", "test")
    w, _ = make_worker(env, clock)
    w.start()
    w.step()
    clock.advance(mst.HEARTBEAT_DEAD_S + 5)                         # process died: no heartbeat
    s = env.status(clock())
    assert s["worker"]["alive"] is False and s["worker"]["effective_state"] == "not running"
    assert all(r["freshness"] == "DISCONNECTED" for r in s["symbols"])


# ---- failures, backoff, reconnection --------------------------------------------------

def test_connection_failures_back_off_and_reconnect(env):
    clock = Clock(OPEN_DAY + timedelta(minutes=10))
    env.set_desired("running", "test")
    boom = requests.ConnectionError("SYNTHETIC connection refused")
    client = FakeClient(clock, [boom, boom, None])
    made = []

    def factory(sleep):
        made.append(1)
        return client
    w = Worker(env, clock=clock, client_factory=factory, pid=1)
    w.quality = None
    w.start()
    w.step()
    assert env.worker()["state"] == "disconnected" and env.worker()["consecutive_failures"] == 1
    clock.advance(BACKOFF[0] - 1)
    w.step()
    assert len(client.calls) == 1                                    # still backing off
    clock.advance(1)
    w.step()
    assert len(client.calls) == 2 and env.worker()["consecutive_failures"] == 2
    clock.advance(BACKOFF[1])
    w.step()
    assert len(client.calls) == 3 and env.worker()["state"] == "running"
    assert env.worker()["consecutive_failures"] == 0 and len(made) == 3   # fresh session after each drop
    assert sum(e["kind"] == "disconnected" for e in env.events()) == 2


def test_backoff_is_capped():
    assert BACKOFF[-1] == 300 and all(a < b for a, b in zip(BACKOFF, BACKOFF[1:]))


@pytest.mark.parametrize("exc, state, wait", [
    (AlpacaAccessError(403, "SYNTHETIC subscription does not permit", "url"), "error", 600),
    (AlpacaAccessError(401, "SYNTHETIC unauthorized", "url"), "error", 600),
    (AlpacaAccessError(503, "SYNTHETIC unavailable", "url"), "disconnected", 5),
    (MissingCredentials("SYNTHETIC: keys not set"), "error", 300),
])
def test_access_errors_recorded_and_feed_never_switched(env, exc, state, wait):
    clock = Clock(OPEN_DAY + timedelta(minutes=10))
    env.set_desired("running", "test")
    w, client = make_worker(env, clock, client=FakeClient(clock, [exc]))
    w.start()
    w.step()
    wk = env.worker()
    assert wk["state"] == state
    assert mst.parse(wk["backoff_until_utc"]) - clock() == timedelta(seconds=wait)
    clock.advance(wait)
    w.step()
    assert [c["feed"] for c in client.calls] == ["iex", "iex"]


# ---- reserved periods, separation -----------------------------------------------------

def test_never_fetches_inside_reserved_periods(env):
    clock = Clock(datetime(2026, 10, 30, 15, 0, tzinfo=UTC))       # last day of the final period
    env.set_desired("running", "test")
    w, client = make_worker(env, clock)
    w.start()
    w.step()
    assert client.calls == [] and env.worker()["state"] == "refused"


def test_reserved_bars_in_a_response_are_discarded(env):
    received = OPEN_DAY + timedelta(minutes=2)
    res = env.insert_bars("SPY", "iex", [synthetic_bar(datetime(2026, 10, 30, 19, 0, tzinfo=UTC)),
                                         synthetic_bar(OPEN_DAY)], received)
    assert res == {"new": 1, "duplicates": 0, "reserved_discarded": 1}
    assert env.db.execute("SELECT MIN(session_date) FROM bars").fetchone()[0] == "2026-11-04"


def test_monitoring_data_is_separate_from_research_code():
    from pathlib import Path
    root = Path(mst.PROJECT_ROOT) / "trading"
    for f in root.rglob("*.py"):
        if "monitor" in f.parts:
            continue
        text = f.read_text(encoding="utf-8")
        assert "monitor.sqlite" not in text and "data/monitoring" not in text, f


# ---- controls and supervision ----------------------------------------------------------

def test_start_launches_once_and_supervisor_recovers_without_duplicates(env, _isolate_monitor):
    launched = _isolate_monitor
    now = OPEN_DAY + timedelta(minutes=10)
    msg = control.start(env, "test", now)
    assert "launched" in msg and len(launched) == 1 and env.desired() == "running"
    assert "less than 20 s" in control.start(env, "test", now + timedelta(seconds=5)) and len(launched) == 1
    env.update_worker(state="running", heartbeat_utc=mst.iso(now + timedelta(seconds=30)), pid=7)
    assert "already running" in control.start(env, "test", now + timedelta(seconds=31)) and len(launched) == 1
    # Worker died; supervisor restarts it (bounded), never more than 6 launches per hour.
    for i in range(10):
        control.launch(env, "supervisor", now + timedelta(minutes=2, seconds=25 * i))
    assert len(launched) == 6
    assert sum("launch limit" in e["message"] for e in env.events(50)) == 1      # logged once, not per check


def test_supervisor_only_acts_when_desired_running(env, _isolate_monitor):
    launched = _isolate_monitor
    sup = control.Supervisor(threading.Event())
    assert sup.check_once() is None and launched == []              # default desired: stopped
    env.set_desired("running", "test")
    assert "launched" in sup.check_once() and len(launched) == 1


# ---- dashboard endpoints and consistency ------------------------------------------------

@pytest.fixture
def server_base():
    from trading.dashboard import server
    httpd, _ctrl, stop = server.create_server(None, 0, speed=3600, run_jobs=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    stop.set()
    httpd.shutdown()
    httpd.server_close()


def _call(base, path, body=None, headers=None):
    h = {"Content-Type": "application/json", "X-Dashboard-Control": "1"} if body is not None else {}
    h.update(headers or {})
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_monitor_api_matches_store_and_controls_work(env, server_base, _isolate_monitor):
    now = mst.now_utc()
    env.insert_bars("SPY", "iex", [synthetic_bar(now.replace(second=0, microsecond=0) - timedelta(minutes=3))], now)
    code, api = _call(server_base, "/api/monitor")
    assert code == 200 and api["label"].startswith("MONITORING DATA")
    local = env.status()
    for a, b in zip(api["symbols"], local["symbols"]):
        for k in ("symbol", "feed", "last_bar_start_utc", "close", "received_utc", "freshness"):
            assert a[k] == b[k], k
    assert [r["t_utc"] for r in api["recent_bars"]["SPY"]] == [r["t_utc"] for r in env.bars("SPY", "iex")]
    code, res = _call(server_base, "/api/monitor/control", {"action": "start"})
    assert code == 200 and res["desired"] == "running" and len(_isolate_monitor) == 1
    assert _call(server_base, "/api/monitor/control", {"action": "pause"})[1]["desired"] == "paused"
    assert _call(server_base, "/api/monitor/control", {"action": "stop"})[1]["desired"] == "stopped"
    assert _call(server_base, "/api/monitor/control", {"action": "trade"})[0] == 400
    assert _call(server_base, "/api/monitor/control", {"action": "start", "symbols": "AAPL"})[0] == 400
    assert _call(server_base, "/api/monitor/control", {"action": "start"}, {"Origin": "https://evil.example"})[0] == 403
    assert _call(server_base, "/api/monitor/control", {"action": "start"}, {"X-Dashboard-Control": ""})[0] == 403
    assert env.desired() == "stopped"



def test_stopped_worker_is_labelled_stopped_not_disconnected(env):
    clock = Clock(OPEN_DAY + timedelta(minutes=10))
    env.set_desired("running", "test")
    w, _ = make_worker(env, clock)
    w.start()
    w.step()
    w.shutdown("stop requested")
    s = env.status(clock())
    assert all(r["freshness"] == "STOPPED" for r in s["symbols"]) and s["worker"]["effective_state"] == "stopped"
