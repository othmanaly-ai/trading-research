"""SYNTHETIC fixtures only: no network, no real keys, no market data. Numbers here are invented to
exercise the pilot's limits and quote rules; they are not evidence of real spreads."""

import gzip
import json
import random
import subprocess
from datetime import time as dtime

import pytest

from trading import spread_measurement as sm
from trading.alpaca_client import ReadOnlyAlpacaClient
from trading.execution_feasibility import CountingHttp, et_utc


# ---------------------------------------------------------------- fakes

class FakeResp:
    def __init__(self, body, code=200):
        self.status_code, self._body, self.text = code, body, json.dumps(body)

    def json(self):
        return self._body


class FakeData:
    """Serves synthetic quote pages through the real read-only client, so CountingHttp counts
    every page. pages(window_start_utc) -> number of pages that window has."""

    def __init__(self, pages=lambda start: 2, quote_status=200, rows_per_page=3):
        self.pages, self.quote_status, self.rows = pages, quote_status, rows_per_page
        self.quote_calls = self.condition_calls = 0

    def get(self, url, headers, params, timeout):
        assert url.startswith("https://data.alpaca.markets/")
        if url.endswith("/v2/stocks/meta/conditions/quote"):
            self.condition_calls += 1
            return FakeResp({"R": "Regular Market Maker Open (SYNTHETIC)"})
        assert url.endswith("/v2/stocks/quotes")
        assert params["symbols"] == "SPY" and params["feed"] == "sip"
        self.quote_calls += 1
        if self.quote_status != 200:
            return FakeResp({"message": "SYNTHETIC refusal"}, self.quote_status)
        n, i = self.pages(params["start"]), int(params.get("page_token") or 0)
        rows = [{"t": params["start"], "bp": 100.0, "ap": 100.01, "bs": 1, "as": 1, "c": ["?"]}] * self.rows
        return FakeResp({"quotes": {"SPY": rows}, "next_page_token": str(i + 1) if i + 1 < n else None})


def run(tmp_path, data, cap=sm.PILOT_MAX_REQUESTS, max_bytes=sm.PILOT_MAX_BYTES):
    http = CountingHttp(data, cap=cap, gap=0)
    client = ReadOnlyAlpacaClient("SYNTHETIC-KEY", "SYNTHETIC-SECRET", http=http, sleep=lambda s: None)
    return sm.fetch_pilot(client, http, tmp_path / "run", max_bytes=max_bytes), http


# ---------------------------------------------------------------- dates, windows, limits

def test_pilot_dates_reproduce_the_preregistered_draw():
    """Calendar only: re-run the selection and check pilot = first date of each year, pending = the rest."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import exchange_calendars as xc
        cal = xc.get_calendar("XNYS")
    s = cal.sessions_in_range("2016-01-04", "2021-12-31")
    closes = cal.closes[s].dt.tz_convert("America/New_York")
    prior = {"2016-10-19", "2017-01-19", "2017-03-27", "2019-05-07", "2020-12-02", "2021-07-20", "2019-06-21"}
    elig = [d for d in s if closes[d].strftime("%H:%M") == "16:00" and d.strftime("%Y-%m-%d") not in prior]
    rng, drawn = random.Random(20261108), []
    for y in range(2016, 2022):
        drawn.append(sorted(d.strftime("%Y-%m-%d") for d in rng.sample([d for d in elig if d.year == y], 4)))
    assert sorted(sm.PILOT_DATES) == [yr[0] for yr in drawn]
    assert sorted(sm.PENDING_DATES) == sorted(d for yr in drawn for d in yr[1:])
    order = [d for yr in drawn for d in yr]
    random.Random(20261109).shuffle(order)
    assert list(sm.PILOT_DATES) == [d for d in order if d in sm.PILOT_DATES]


def test_only_pilot_dates_allowed():
    sm.check_pilot_dates()
    with pytest.raises(ValueError, match="pending"):
        sm.check_pilot_dates(["2016-06-17"])
    for d in ("2022-01-04", "2025-03-03", "2019-05-07"):      # validation, final, unregistered development
        with pytest.raises(ValueError):
            sm.check_pilot_dates([d])


def test_early_close_and_held_out_refused_even_if_listed(monkeypatch):
    monkeypatch.setattr(sm, "PILOT_DATES", ("2019-11-29", "2022-01-04"))
    with pytest.raises(ValueError, match="early-close"):
        sm.check_pilot_dates(["2019-11-29"])
    with pytest.raises(ValueError, match="development"):
        sm.check_pilot_dates(["2022-01-04"])


def test_windows_and_caps_match_the_plan():
    assert [w.id for w in sm.WINDOWS] == ["B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "E1", "X1"]
    assert {w.id: w.page_cap for w in sm.WINDOWS} == {"B0": 60, "B1": 10, "B2": 10, "B3": 10, "B4": 10,
                                                      "B5": 10, "B6": 10, "B7": 15, "E1": 45, "X1": 40}
    assert sum(w.page_cap for w in sm.WINDOWS) == 220
    w = sm.WINDOW_BY_ID
    assert (w["E1"].start, w["E1"].end) == (dtime(15, 29), dtime(15, 34))
    assert (w["X1"].start, w["X1"].end) == (dtime(15, 57), dtime(16, 0))
    assert (w["B0"].start, w["B0"].end) == (dtime(10, 0), dtime(10, 16))
    assert sum((x.end.hour * 60 + x.end.minute) - (x.start.hour * 60 + x.start.minute) for x in sm.WINDOWS) == 39
    assert sm.PILOT_MAX_REQUESTS == 600 and sm.PILOT_MAX_BYTES == 75_000_000 and sm.MIN_GAP_S >= 0.4


# ---------------------------------------------------------------- fetch limits

def test_fetch_counts_every_page_and_records_usage(tmp_path):
    res, http = run(tmp_path, FakeData(pages=lambda s: 2))
    assert res["http_requests"] == http.count == 1 + 6 * 10 * 2
    assert res["stop_reason"] is None and all(e["status"] == "ok" for e in res["windows"].values())
    assert len(res["windows"]) == 60 and all(e["pages"] == 2 and e["bytes"] > 0 for e in res["windows"].values())
    assert res["bytes_total"] > 0 and res["elapsed_s"] >= 0 and res["http_status_counts"] == {200: 121}
    assert "SYNTHETIC-SECRET" not in (tmp_path / "run" / "requests_log.json").read_text(encoding="utf-8")


def test_page_cap_marks_incomplete_coverage_and_run_continues(tmp_path):
    b1 = {et_utc(d, dtime(10, 45)) for d in sm.PILOT_DATES}
    res, _ = run(tmp_path, FakeData(pages=lambda s: 11 if s in b1 else 1))
    e = res["windows"][f"{sm.PILOT_DATES[0]} B1"]
    assert e["status"] == "INCOMPLETE COVERAGE" and e["pages"] == 10 and not e["complete"]
    assert res["windows"][f"{sm.PILOT_DATES[0]} B2"]["status"] == "ok" and res["stop_reason"] is None


def test_total_request_cap_stops_run(tmp_path):
    data = FakeData(pages=lambda s: 2)
    res, http = run(tmp_path, data, cap=25)            # 1 condition request + 12 full windows = 25
    statuses = [e["status"] for e in res["windows"].values()]
    assert statuses[:12] == ["ok"] * 12 and statuses[12] == "INCOMPLETE"
    assert set(statuses[13:]) == {"NOT FETCHED"} and "request cap" in res["stop_reason"]
    assert http.count == data.quote_calls + data.condition_calls == 25


def test_cli_uses_the_600_request_cap(monkeypatch):
    seen = {}
    monkeypatch.setattr(sm, "plan_gate", lambda: {"plan_commit": "SYNTHETIC"})
    import trading.alpaca_client as ac
    monkeypatch.setattr(ac, "load_credentials", lambda: ("SYNTHETIC-KEY", "SYNTHETIC-SECRET"))

    def fake_fetch(client, http, out, gate=None):
        seen.update(cap=http.cap, gap=http.gap, gate=gate, out=out)
        return {"http_requests": 0, "bytes_total": 0, "elapsed_s": 0, "stop_reason": None, "stopped_paths": {}, "windows": {}}
    monkeypatch.setattr(sm, "fetch_pilot", fake_fetch)
    assert sm.main(["fetch-pilot"]) == 0
    assert seen["cap"] == 600 and seen["gap"] >= 0.4 and seen["out"].name.startswith("spreads_pilot_")


def test_storage_guard_refuses_window_without_reserve(tmp_path):
    data = FakeData()
    res, _ = run(tmp_path, data, max_bytes=60 * sm.RESERVE_BYTES_PER_PAGE - 1)   # B0 needs 60 pages of reserve
    assert data.quote_calls == 0 and "storage guard" in res["stop_reason"]
    assert {e["status"] for e in res["windows"].values()} == {"NOT FETCHED"}


def test_storage_cap_exceeded_after_write_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "RESERVE_BYTES_PER_PAGE", 0)
    sizes = iter([0, 10**9])                 # guard check passes, then the write overshoots
    monkeypatch.setattr(sm, "dir_bytes", lambda p: next(sizes, 10**9))
    data = FakeData(pages=lambda s: 1)
    res, _ = run(tmp_path, data, max_bytes=1000)
    statuses = [e["status"] for e in res["windows"].values()]
    assert statuses[0] == "ok" and set(statuses[1:]) == {"NOT FETCHED"}
    assert "storage cap exceeded" in res["stop_reason"] and data.quote_calls == 1


def test_access_failure_stops_quotes_without_retry(tmp_path):
    data = FakeData(quote_status=403)
    res, _ = run(tmp_path, data)
    statuses = [e["status"] for e in res["windows"].values()]
    assert statuses[0] == "access failure" and set(statuses[1:]) == {"NOT REQUESTED"}
    assert data.quote_calls == 1 and res["stopped_paths"]["quotes"]["http_status"] == 403


# ---------------------------------------------------------------- pre-registration gate

def _git(cwd, *a):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *a], cwd=cwd, check=True,
                   capture_output=True)


def test_plan_gate_requires_committed_unchanged_plan(tmp_path):
    _git(tmp_path, "init", "-q")
    rel = "feasibility/spread_measurement/PLAN.md"
    p = tmp_path / rel
    p.parent.mkdir(parents=True)
    p.write_text("SYNTHETIC plan\n", encoding="utf-8")
    with pytest.raises(sm.PlanNotCommitted, match="not committed"):
        sm.plan_gate(tmp_path, rel)
    _git(tmp_path, "add", rel)
    _git(tmp_path, "commit", "-q", "-m", "plan")
    g = sm.plan_gate(tmp_path, rel)
    assert len(g["plan_commit"]) == 40 and len(g["plan_sha256"]) == 64
    p.write_text("SYNTHETIC plan, edited\n", encoding="utf-8")
    with pytest.raises(sm.PlanNotCommitted, match="uncommitted"):
        sm.plan_gate(tmp_path, rel)


def test_fetch_refused_before_credentials_when_plan_not_committed(monkeypatch):
    def boom():
        raise AssertionError("credentials must not be loaded")
    monkeypatch.setattr(sm, "plan_gate", lambda: (_ for _ in ()).throw(sm.PlanNotCommitted("SYNTHETIC")))
    import trading.alpaca_client as ac
    monkeypatch.setattr(ac, "load_credentials", boom)
    assert sm.main(["fetch-pilot"]) == 4


# ---------------------------------------------------------------- quote rules (hand-computed)

D = "2019-01-31"            # EST: 10:45 ET = 15:45Z


def q(t, bp, ap, c=("?",), bs=3, as_=5):
    return {"t": f"2019-01-31T15:{t}Z", "bp": bp, "ap": ap, "bs": bs, "as": as_, "c": list(c)}


def rule_rows():
    r8 = q("45:20", 100.0, 100.03)
    return [
        q("45:01", 100.0, 100.01),                    # normal 1c        1.5 s
        q("45:03", 100.0, 100.02, ("R",)),            # normal 2c        1 s
        q("45:04", 100.0, 100.0, ("R",)),             # locked           1 s
        q("45:05", 100.02, 100.0, ("R",)),            # crossed          1 s
        q("45:06", 0.0, 100.0, ("R",)),               # one-sided        1 s
        q("45:07", 100.0, 100.01, ("Z",)),            # other condition  1 s
        q("45:08", 100.0, 100.01),                    # normal 1c        5 s + 7 s stale
        r8, dict(r8),                                 # normal 3c 1 s, then an identical duplicate
        q("45:21", 100.0, 100.01),                    # normal 1c        5 s + 94 s stale
        q("45:02.500", 100.0, 100.01),                # out of order: normal 1c 0.5 s
        q("47:30", 100.0, 100.01),                    # invalid: after the window end
        {"t": "garbage", "bp": 100.0, "ap": 100.01, "c": ["?"]},          # invalid timestamp
        {"t": "2019-01-31T15:45:30Z", "ap": 100.01, "c": ["?"]},          # invalid: no bid
    ]


W = sm.Window("T", dtime(10, 45), dtime(10, 47), 10, (dtime(10, 45, 3), dtime(10, 45, 4), dtime(10, 46)))


def test_quote_rules_counts_and_time_shares():
    s = sm.window_stats(rule_rows(), D, W)
    assert s["records_received"] == 14 and s["duplicates"] == 1 and s["excluded_invalid"] == 3
    assert s["out_of_order"] == 1 and s["ordering_issue"]
    assert s["excluded_counts"] == {"invalid": 3, "duplicate": 1, "locked": 1, "crossed": 1,
                                    "one-sided": 1, "other condition": 1}
    assert s["condition_codes"] == {"?": 5, "R": 4, "Z": 1}
    ts = s["time_share"]
    assert ts["normal"] == round(14 / 120, 6) and ts["stale"] == round(101 / 120, 6) and ts["no quote"] == round(1 / 120, 6)
    assert ts["locked"] == ts["crossed"] == ts["one-sided"] == ts["other condition"] == round(1 / 120, 6)
    assert abs(sum(ts.values()) - 1) < 1e-5
    assert s["coverage"] == round(14 / 120, 6) and not s["measured"]


def test_spread_statistics_hand_computed():
    s = sm.window_stats(rule_rows(), D, W)
    c = s["spread"]["cents"]
    assert c["tw_mean"] == round(17 / 14, 4) and c["tw_median"] == 1.0 and c["max"] == 3.0
    assert s["time_share_by_spread"] == {"1_cent": round(12 / 14, 6), "2_cents": round(1 / 14, 6),
                                         "3_cents_or_more": round(1 / 14, 6)}
    assert s["sensitivity_locked_as_zero_tw_mean_cents"] == round(17 / 15, 4)
    assert abs(s["spread"]["bp"]["tw_mean"] - (17 / 14) / 100.01 * 100) < 1e-3     # cents / mid * 100 = bp
    assert s["half_spread_bp_tw_mean"] == round(s["spread"]["bp"]["tw_mean"] / 2, 4)
    assert s["displayed_size_shares_median"] == {"bid": 300.0, "ask": 500.0}
    assert s["wide_spreads"]["count"] == 0
    assert set(s["spread_bp_tw_mean_by_code"]) == {"?", "R", "Z"}


def test_snapshots_ok_ambiguous_unresolved():
    sn = sm.window_stats(rule_rows(), D, W)["snapshots"]
    assert sn["10:45:03"]["state"] == "ok" and sn["10:45:03"]["cents"] == 2.0 and sn["10:45:03"]["quote_age_s"] == 0
    assert sn["10:45:04"]["state"] == "AMBIGUOUS" and sn["10:45:04"]["cents"] == 2.0   # locked quote is later
    assert sn["10:46:00"] == {"state": "unresolved"}                                   # newest normal is 39 s old


def test_dense_window_is_measured_and_wide_spreads_listed():
    rows = [q(f"{45 + i // 60}:{i % 60:02d}", 100.0, 100.01) for i in range(120)]
    rows[10] = q("45:10", 100.0, 100.15)
    s = sm.window_stats(rows, D, W)
    assert s["measured"] and s["coverage"] == 1.0
    assert s["wide_spreads"]["count"] == 1 and s["wide_spreads"]["listed"][0]["cents"] == 15.0
    assert sm.window_stats([], D, W)["time_share"]["no quote"] == 1.0


def test_group_summary_pools_by_time_and_excludes_partial():
    def st(cents, secs, measured=True):
        return {"fetch_status": "ok", "stats": {"measured": measured, "headline_seconds": secs,
                                                "spread": {"cents": {"tw_mean": cents}, "bp": {"tw_mean": cents * 0.4}}}}
    pw = {}
    for d, partial in (("2019-01-31", False), ("2020-01-02", True)):
        for wid in ("B1", "B2", "B3", "B4", "B5", "B6", "B7"):
            pw[f"{d} {wid}"] = st(2.0 if wid == "B7" else 1.0, 180 if wid == "B7" else 120, measured=not (partial and wid == "B3"))
    g = sm.summarize_groups(pw)["B1_B7"]
    assert g["coverage_counts"] == {"measured": 1, "partial": 1, "incomplete_or_not_fetched": 0}
    assert g["by_date"]["2019-01-31"]["tw_mean_cents"] == round((6 * 120 * 1.0 + 180 * 2.0) / (6 * 120 + 180), 4)
    assert g["dates_with_half_spread_above"] == {"base": 0, "stress": 0, "severe": 0}
    assert sm.summarize_groups(pw)["E1"]["coverage_counts"]["incomplete_or_not_fetched"] == 2


def test_analyze_end_to_end_offline(tmp_path):
    res, _ = run(tmp_path, FakeData(pages=lambda s: 1))
    f = sm.analyze(tmp_path / "run")
    assert f["resource_usage"]["http_requests"] == 61 and f["resource_usage"]["bytes_total_all_files"] > 0
    assert len(f["windows"]) == 60 and set(f["groups"]) == {"E1", "X1", "B0", "B1_B7", "B7"}
    assert "PROVISIONAL" in f["label"]
    with gzip.open(tmp_path / "run" / f"quotes_{sm.PILOT_DATES[0]}_B0.json.gz", "rt") as fh:
        assert json.load(fh)                                       # raw records kept unmodified
