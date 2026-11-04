"""SYNTHETIC fixtures only: no network, no real keys, no market data."""

import pytest

from trading import execution_feasibility as ef
from trading.alpaca_client import AlpacaAccessError


class FakeResp:
    def __init__(self, code=200):
        self.status_code = code


class FakeInner:
    def __init__(self):
        self.calls = 0

    def get(self, url, headers, params, timeout):
        self.calls += 1
        return FakeResp()


def test_counting_http_enforces_cap_and_logs_no_headers():
    inner = FakeInner()
    http = ef.CountingHttp(inner, cap=2, gap=0)
    http.get("https://data.alpaca.markets/v2/stocks/quotes", {"APCA-API-KEY-ID": "SECRET"}, {"a": 1}, 1)
    http.get("https://data.alpaca.markets/v2/stocks/quotes", {"APCA-API-KEY-ID": "SECRET"}, {"page_token": "x"}, 1)
    with pytest.raises(ef.RequestCapReached):
        http.get("https://data.alpaca.markets/v2/stocks/quotes", {}, {}, 1)
    assert inner.calls == 2 and "SECRET" not in str(http.log)


def test_held_out_dates_refused():
    with pytest.raises(ValueError):
        ef.check_dates([("2022-01-04", "2022-01-03", "x")])
    with pytest.raises(ValueError):
        ef.check_dates([("2025-03-03", "2025-02-28", "x")])
    ef.check_dates()                                   # the pre-registered list is development only


class FakeClient:
    """Quotes refused (HTTP 403) on the first date; quotes must not be requested again."""

    def __init__(self):
        self.quote_calls = 0

    def get_corporate_actions(self, *a, **k):
        return {"corporate_actions": {"cash_dividends": [{"ex_date": "2019-06-21"}]}, "pages": 1, "complete": True}

    def get_bars(self, symbol, timeframe, start, end, feed, adjustment):
        assert feed == "sip" and adjustment == "raw"
        return {"bars": [], "pages": 1}

    def get_quotes(self, symbol, start, end, feed, max_pages):
        assert feed == "sip"
        self.quote_calls += 1
        raise AlpacaAccessError(403, "SYNTHETIC: subscription does not permit", "u")


def test_access_failure_stops_path_without_retry_and_no_substitution(tmp_path):
    c, http = FakeClient(), ef.CountingHttp(FakeInner(), gap=0)
    res = ef.fetch(c, http, tmp_path)
    assert c.quote_calls == 1 and "quotes" in res["stopped_paths"]
    statuses = [r["quotes"]["status"] for r in res["dates"].values()]
    assert statuses[0] == "access failure" and set(statuses[1:]) == {"not requested"}
    assert all(r["minute_raw"]["status"] == "ok" for r in res["dates"].values())   # other paths continue


def test_quote_validation_flags_crossed_and_disorder():
    d = "2019-06-21"
    rows = [  # SYNTHETIC
        {"t": "2019-06-21T13:30:00.100Z", "bp": 100.0, "ap": 100.01, "bs": 1, "as": 1, "c": ["R"], "z": "B"},
        {"t": "2019-06-21T13:30:00.050Z", "bp": 100.0, "ap": 99.99, "bs": 1, "as": 1, "c": ["R"], "z": "B"},
        {"t": "2019-06-21T13:30:01.000Z", "bp": 100.0, "ap": 100.03, "bs": 1, "as": 1, "c": ["R"], "z": "B"},
    ]
    v = ef.validate_quotes(rows, d)
    assert v["crossed"] == 1 and v["out_of_order"] == 1 and v["outside_window"] == 0
    assert v["by_minute_et"]["09:30"]["valid"] == 2
