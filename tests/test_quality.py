"""Delayed-SIP vs IEX data-quality checker. ALL BARS HERE ARE SYNTHETIC (labelled fixtures, invented
prices): no network, no real market data, nothing here is evidence about either feed. Real access
is verified separately against the live provider."""

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest
import requests

from trading.alpaca_client import AlpacaAccessError
from trading.monitor import quality as q
from trading.monitor import store as mst

UTC = timezone.utc
OPEN = datetime(2026, 11, 4, 14, 30, tzinfo=UTC)          # Wed 4 Nov 2026, 09:30 ET
SYMS = ("SPY", "QQQ", "IWM")


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def bar(t, o=100.0, h=100.5, l=99.5, c=100.2, v=1000, **extra):
    """SYNTHETIC bar in Alpaca's shape."""
    return {"t": iso(t) if isinstance(t, datetime) else t, "o": o, "h": h, "l": l, "c": c, "v": v,
            "n": 10, "vw": c, **extra}


class FakeFeeds:
    """SYNTHETIC two-feed provider. data[feed][symbol] -> list of bars; filters by [start, end]."""

    def __init__(self, script=None):
        self.data = {"sip": {s: [] for s in SYMS}, "iex": {s: [] for s in SYMS}}
        self.script, self.calls = list(script or []), []

    def fill(self, feed, start, minutes, **kw):
        for m in range(minutes):
            for s in SYMS:
                self.data[feed][s].append(bar(start + timedelta(minutes=m), **kw))

    def get_bars_multi(self, symbols, timeframe, start, end, feed, adjustment):
        self.calls.append({"feed": feed, "start": start, "end": end})
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, Exception):
                raise step
        s, e = mst.parse(start), mst.parse(end)
        out = {}
        for sym in symbols:
            out[sym] = [b for b in self.data[feed][sym] if not _parses(b) or s <= mst.parse(b["t"]) <= e]
        return {"bars": out, "pages": 1}


def _parses(b):
    try:
        mst.parse(b["t"])
        return True
    except (TypeError, ValueError):
        return False


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def env():
    store = mst.MonitorStore()
    yield store
    store.close()


def checker(store, clock, monitored=True):
    """A checker whose session was monitored live (as the worker marks it while the market is open)."""
    qc = q.QualityChecker(store, SYMS, clock)
    if monitored:
        day = mst.session_date_et(clock())
        for sess in mst.sessions_between(day, day):
            if sess.date > mst.RESERVED_END:
                qc.mark_monitored(sess, sess.open_utc)
    return qc


def run_until_idle(qc, feeds, clock, limit=50):
    """Step the checker, advancing the fake clock past the backlog gap, until it has nothing to do."""
    results = []
    for _ in range(limit):
        qc.next_cycle = None
        r = qc.step(feeds, clock())
        if r is None:
            break
        results.append(r)
    return results


def latest_rows(store, sym):
    return {r["t_utc"]: dict(r) for r in store.db.execute(
        "SELECT * FROM q_compare WHERE symbol=? ORDER BY sip_rev, iex_rev", (sym,))}


# ---- delay boundary, bounded windows, restart -------------------------------------------

def test_never_requests_inside_the_delay_boundary(env):
    clock = Clock(OPEN + timedelta(minutes=30, seconds=40))              # 10:00:40 ET
    feeds = FakeFeeds()
    feeds.fill("sip", OPEN, 60)
    feeds.fill("iex", OPEN, 60)
    qc = checker(env, clock)
    res = qc.step(feeds, clock())
    assert res["ok"] and res["compared"] == 10 * 3                       # 14:30..14:39 only
    for call in feeds.calls:
        newest_end = mst.parse(call["end"]) + timedelta(seconds=1)
        assert clock() - newest_end >= q.SIP_DELAY + q.SAFETY_MARGIN
    assert [c["feed"] for c in feeds.calls] == ["sip", "iex"]           # never a substitute feed


def test_backlog_is_worked_off_in_bounded_chunks_and_restart_resumes(env):
    clock = Clock(datetime(2026, 11, 4, 18, 0, tzinfo=UTC))              # started late: 13:00 ET
    feeds = FakeFeeds()
    feeds.fill("sip", OPEN, 300)
    feeds.fill("iex", OPEN, 300)
    qc = checker(env, clock)
    qc.step(feeds, clock())
    qc.next_cycle = None                                              # backlog gap elapsed
    qc.step(feeds, clock())
    spans = [(mst.parse(c["end"]) - mst.parse(c["start"])).total_seconds() for c in feeds.calls]
    assert all(s < q.MAX_CHUNK.total_seconds() for s in spans) and len(feeds.calls) == 4
    st_row = env.db.execute("SELECT compared_through_utc FROM q_state").fetchone()[0]
    assert st_row == "2026-11-04T17:40:00+00:00"                        # 18:00 - 20 min
    # Restart: a new checker on the same records requests nothing already compared.
    qc2 = checker(env, clock)
    calls_before = len(feeds.calls)
    assert qc2.step(feeds, clock()) is None and len(feeds.calls) == calls_before
    n = env.db.execute("SELECT COUNT(*), COUNT(DISTINCT symbol||t_utc) FROM q_compare").fetchone()
    assert n[0] == n[1] == 190 * 3


# ---- classification and differences ------------------------------------------------------

def test_categories_differences_and_volume_share(env):
    clock = Clock(OPEN + timedelta(minutes=30))
    t = [OPEN + timedelta(minutes=m) for m in range(7)]
    feeds = FakeFeeds()
    d = feeds.data
    # minute 0: consistent subset; IEX close 2 cents above SIP, IEX volume 200 of 1000
    d["sip"]["SPY"].append(bar(t[0], o=100, h=101, l=99, c=100.00, v=1000))
    d["iex"]["SPY"].append(bar(t[0], o=100, h=100.8, l=99.5, c=100.02, v=200))
    # minute 1: IEX missing -> expected coverage difference
    d["sip"]["SPY"].append(bar(t[1]))
    # minute 2: SIP missing, IEX present -> unresolved anomaly
    d["iex"]["SPY"].append(bar(t[2]))
    # minute 3: IEX high above SIP high -> unresolved anomaly
    d["sip"]["SPY"].append(bar(t[3], h=100.5))
    d["iex"]["SPY"].append(bar(t[3], h=100.6, v=10))
    # minute 4: malformed SIP bar (high below close) -> structural defect
    d["sip"]["SPY"].append(bar(t[4], h=100.0, c=100.4))
    d["iex"]["SPY"].append(bar(t[4], v=10))
    # minute 5: neither feed -> both absent
    # minute 6: SIP zero volume -> share not computed
    d["sip"]["SPY"].append(bar(t[6], v=0))
    d["iex"]["SPY"].append(bar(t[6], v=0))
    qc = checker(env, clock)
    qc.step(feeds, clock())
    rows = latest_rows(env, "SPY")
    cat = [rows[mst.iso(x)]["category"] for x in t]
    assert cat == ["consistent_subset", "expected_coverage_difference", "unresolved_anomaly", "unresolved_anomaly",
                   "structural_defect", "both_absent", "consistent_subset"]
    r0 = rows[mst.iso(t[0])]
    assert r0["d_c_usd"] == pytest.approx(0.02) and r0["d_c_bps"] == pytest.approx(2.0)
    assert r0["iex_volume_share"] == pytest.approx(0.2)
    assert rows[mst.iso(t[6])]["iex_volume_share"] is None
    rep = q.report(env, "2026-11-04", clock())
    spy = next(s for s in rep["symbols"] if s["symbol"] == "SPY")
    assert spy["zero_volume_sip_minutes"] == 1 and spy["iex_missing"] == 1 and spy["sip_missing"] == 1
    assert spy["categories"]["structural_defect"] == 1 and spy["categories"]["unresolved_anomaly"] == 2
    assert {f["category"] for f in rep["flagged"]} == {"unresolved_anomaly", "structural_defect"}


def test_unexpected_timestamps_and_conflicting_duplicates_are_defects(env):
    clock = Clock(OPEN + timedelta(minutes=30))
    feeds = FakeFeeds()
    feeds.data["sip"]["SPY"] += [bar("2026-11-04T14:31:30Z"),                     # not minute-aligned
                                 bar(OPEN + timedelta(minutes=2), c=100.2),
                                 bar(OPEN + timedelta(minutes=2), c=100.3),       # conflicting duplicate
                                 {"t": iso(OPEN + timedelta(minutes=3)), "o": "x"}]  # malformed
    feeds.data["iex"]["SPY"].append(bar(OPEN + timedelta(minutes=2)))
    qc = checker(env, clock)
    res = qc.step(feeds, clock())
    assert res["defects"] >= 3
    defects = [json.loads(r[0]) for r in env.db.execute("SELECT defects FROM q_obs WHERE defects IS NOT NULL")]
    flat = "; ".join("; ".join(d) for d in defects)
    assert "not minute-aligned" in flat and "conflicting duplicate" in flat and "missing field" in flat


# ---- corrections, duplicates, no look-ahead ----------------------------------------------

def test_late_correction_keeps_revision_history_and_duplicates_add_nothing(env):
    clock = Clock(datetime(2026, 11, 4, 21, 25, tzinfo=UTC))             # after close + 20 min, before the recheck
    feeds = FakeFeeds()
    feeds.fill("sip", OPEN, 390)
    feeds.fill("iex", OPEN, 390)
    qc = checker(env, clock)
    run_until_idle(qc, feeds, clock)
    assert env.db.execute("SELECT status FROM q_state").fetchone()[0] == "provisional"
    first_obs = env.db.execute("SELECT COUNT(*) FROM q_obs").fetchone()[0]
    clock.t = datetime(2026, 11, 4, 21, 50, tzinfo=UTC)                    # recheck now due (close + 15 + 30)
    # The provider later corrects one SIP minute; the end-of-day re-observation must notice it.
    t_fix = OPEN + timedelta(minutes=100)
    for b in feeds.data["sip"]["QQQ"]:
        if b["t"] == iso(t_fix):
            b["c"] = 100.25
    qc.next_cycle = None
    res = qc.step(feeds, clock())
    assert res["ok"] and res["corrections"] == 1 and res["duplicate_obs"] == 390 * 6 - 1
    revs = env.db.execute("SELECT revision, c FROM q_obs WHERE symbol='QQQ' AND feed='sip' AND t_utc=? ORDER BY revision",
                          (mst.iso(t_fix),)).fetchall()
    assert [(r[0], r[1]) for r in revs] == [(1, 100.2), (2, 100.25)]                # original kept
    assert env.db.execute("SELECT COUNT(*) FROM q_obs").fetchone()[0] == first_obs + 1
    cmp_ = env.db.execute("SELECT sip_rev FROM q_compare WHERE symbol='QQQ' AND t_utc=? ORDER BY sip_rev",
                          (mst.iso(t_fix),)).fetchall()
    assert [r[0] for r in cmp_] == [1, 2]                                           # both comparisons kept
    rep = q.report(env, "2026-11-04", clock())
    assert next(s for s in rep["symbols"] if s["symbol"] == "QQQ")["corrections"]["sip"] == 1
    assert next(s for s in rep["symbols"] if s["symbol"] == "QQQ")["minutes_compared"] == 390
    assert rep["eod_recheck_utc"] is not None
    # Finalized exactly once; repeating finalization stores nothing new.
    assert env.db.execute("SELECT status FROM q_state").fetchone()[0] == "finalized"
    assert env.db.execute("SELECT COUNT(*), MAX(status) FROM q_reports").fetchone()[:] == (1, "finalized")
    assert qc.finalize("2026-11-04") == {"stored": False, "version": 1}
    run_until_idle(qc, feeds, clock)
    assert env.db.execute("SELECT COUNT(*) FROM q_reports").fetchone()[0] == 1


def test_sip_is_labelled_delayed_and_never_changes_live_bars(env):
    clock = Clock(OPEN + timedelta(minutes=40))
    env.insert_bars("SPY", "iex", [bar(OPEN, c=100.1)], OPEN + timedelta(minutes=1, seconds=5))   # live capture
    before = [tuple(r) for r in env.db.execute("SELECT * FROM bars")]
    feeds = FakeFeeds()
    feeds.fill("sip", OPEN, 20)
    feeds.fill("iex", OPEN, 20, c=100.3)
    checker(env, clock).step(feeds, clock())
    assert [tuple(r) for r in env.db.execute("SELECT * FROM bars")] == before       # live evidence untouched
    obs = env.db.execute("SELECT provider_available_utc, retrieved_utc FROM q_obs WHERE feed='sip' AND symbol='SPY' "
                         "AND t_utc=?", (mst.iso(OPEN),)).fetchone()
    assert obs[0] == "2026-11-04T14:46:00+00:00"                                    # bar end + 15 min
    assert mst.parse(obs[1]) >= mst.parse(obs[0])
    row = latest_rows(env, "SPY")[mst.iso(OPEN)]
    assert row["live_iex_present"] == 1 and row["live_iex_received_utc"] == "2026-11-04T14:31:05+00:00"
    assert row["sip_provider_available_utc"] == "2026-11-04T14:46:00+00:00"


# ---- failures, calendar ------------------------------------------------------------------

def test_access_failure_is_recorded_backs_off_and_does_not_substitute(env):
    clock = Clock(OPEN + timedelta(minutes=40))
    feeds = FakeFeeds([AlpacaAccessError(403, "SYNTHETIC subscription does not permit", "url")])
    feeds.fill("sip", OPEN, 30)
    feeds.fill("iex", OPEN, 30)
    qc = checker(env, clock)
    res = qc.step(feeds, clock())
    assert not res["ok"] and res["status"] == "access_failure"
    h = qc.health()
    assert h["state"] == "access_failure" and "not replaced" in h["detail"]
    assert mst.parse(h["backoff_until_utc"]) - clock() == timedelta(seconds=q.ACCESS_REFUSED_WAIT)
    assert env.db.execute("SELECT COUNT(*) FROM q_compare").fetchone()[0] == 0
    assert [c["feed"] for c in feeds.calls] == ["sip"]                              # IEX not used instead
    run = env.db.execute("SELECT status, http_status FROM q_runs").fetchone()
    assert tuple(run) == ("access_failure", 403)
    assert qc.step(feeds, clock() + timedelta(seconds=10)) is None                  # still backing off
    clock.t += timedelta(seconds=q.ACCESS_REFUSED_WAIT)
    assert qc.step(feeds, clock())["ok"]


def test_connection_error_backs_off(env):
    clock = Clock(OPEN + timedelta(minutes=40))
    feeds = FakeFeeds([requests.ConnectionError("SYNTHETIC drop")])
    qc = checker(env, clock)
    assert qc.step(feeds, clock())["status"] == "error"
    assert mst.parse(qc.health()["backoff_until_utc"]) - clock() == timedelta(seconds=q.BACKOFF[0])


def test_holiday_and_reserved_dates_make_no_requests(env):
    for when in (datetime(2026, 11, 26, 16, 0, tzinfo=UTC), datetime(2026, 10, 30, 18, 0, tzinfo=UTC)):
        feeds = FakeFeeds()
        qc = checker(env, Clock(when))
        assert qc.step(feeds, when) is None and feeds.calls == []


def test_early_close_compares_only_to_the_early_close(env):
    clock = Clock(datetime(2026, 11, 27, 18, 40, tzinfo=UTC))           # early close 13:00 ET = 18:00 UTC
    feeds = FakeFeeds()
    feeds.fill("sip", OPEN.replace(day=27), 240)
    feeds.fill("iex", OPEN.replace(day=27), 240)
    qc = checker(env, clock)
    run_until_idle(qc, feeds, clock)
    assert env.db.execute("SELECT compared_through_utc FROM q_state").fetchone()[0] == "2026-11-27T18:00:00+00:00"
    assert env.db.execute("SELECT MAX(t_utc) FROM q_compare").fetchone()[0] == "2026-11-27T17:59:00+00:00"
    rep = q.report(env, "2026-11-27", clock())
    assert rep["session"]["early_close"] is True and rep["session"]["minutes"] == 210


# ---- dashboard endpoints -------------------------------------------------------------------

def test_quality_endpoints_and_validation(env):
    from trading.dashboard import server
    clock = Clock(OPEN + timedelta(minutes=40))
    feeds = FakeFeeds()
    feeds.fill("sip", OPEN, 20)
    feeds.fill("iex", OPEN, 20)
    checker(env, clock).step(feeds, clock())
    httpd, _c, stop = server.create_server(None, 0, speed=3600, run_jobs=False, supervise_monitor=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def get(path):
        try:
            with urllib.request.urlopen(base + path, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    try:
        code, rep = get("/api/quality?date=2026-11-04")
        assert code == 200 and rep["label"].startswith("DATA QUALITY") and len(rep["symbols"]) == 3
        assert rep["symbols"][0]["minutes_compared"] == 20             # 40 min after open - 20 min boundary
        code, rec = get("/api/quality/minute?symbol=SPY&t=2026-11-04T14:30:00%2B00:00")
        assert code == 200 and {o["feed"] for o in rec["observations"]} == {"sip", "iex"} and rec["comparisons"]
        for bad in ("/api/quality?date=../x", "/api/quality/minute?symbol=spy;&t=x", "/api/quality/minute?symbol=SPY&t=2026"):
            assert get(bad)[0] == 400
    finally:
        stop.set()
        httpd.shutdown()
        httpd.server_close()
