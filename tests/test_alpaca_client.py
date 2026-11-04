"""Client tests use a fake HTTP object; no network calls and no real keys."""

import pytest

from trading import alpaca_client
from trading.alpaca_client import (
    AlpacaAccessError, MissingCredentials, ReadOnlyAlpacaClient, load_credentials,
)

FAKE_KEY, FAKE_SECRET = "TESTKEYID", "TESTSECRET-not-real"


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


class FakeHttp:
    """Only implements get(); any other HTTP verb would raise AttributeError."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers, params, timeout):
        self.calls.append({"url": url, "params": dict(params or {})})
        return self.responses.pop(0)


def test_pagination_follows_tokens():
    http = FakeHttp([
        FakeResponse(200, {"bars": {"AAPL": [{"t": "a"}]}, "next_page_token": "P2"}),
        FakeResponse(200, {"bars": {"AAPL": [{"t": "b"}]}, "next_page_token": None}),
    ])
    client = ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=http)
    out = client.get_bars("AAPL", "1Min", "s", "e", feed="iex", adjustment="raw")
    assert [b["t"] for b in out["bars"]] == ["a", "b"]
    assert out["pages"] == 2
    assert "page_token" not in http.calls[0]["params"]
    assert http.calls[1]["params"]["page_token"] == "P2"
    assert all(c["params"]["feed"] == "iex" for c in http.calls)


def test_feed_refusal_raises_and_is_not_substituted():
    http = FakeHttp([FakeResponse(403, {"message": "subscription does not permit"})])
    client = ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=http)
    with pytest.raises(AlpacaAccessError) as err:
        client.get_bars("AAPL", "1Day", "s", "e", feed="sip", adjustment="raw")
    assert err.value.status_code == 403
    assert len(http.calls) == 1
    assert FAKE_SECRET not in str(err.value)


def test_account_keeps_only_listed_fields():
    raw = {"id": "uuid", "account_number": "PA123", "cash": "1000", "status": "ACTIVE"}
    client = ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=FakeHttp([FakeResponse(200, raw)]))
    acct = client.get_account()
    assert "id" not in acct and "account_number" not in acct
    assert acct["cash"] == "1000"


def test_only_paper_and_data_hosts_allowed():
    client = ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=FakeHttp([]))
    with pytest.raises(ValueError):
        client._get("https://api.alpaca.markets", "/v2/account")   # live trading host


def test_client_has_no_order_methods():
    public = {n for n in dir(ReadOnlyAlpacaClient) if not n.startswith("_")}
    assert public == {"get_account", "get_bars", "get_bars_multi", "get_quotes", "get_corporate_actions", "get_quote_conditions"}
    assert all(n.startswith("get_") for n in public)          # read-only: GET methods only


def test_repr_hides_credentials():
    assert FAKE_SECRET not in repr(ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=FakeHttp([])))


def test_missing_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    with pytest.raises(MissingCredentials):
        load_credentials(tmp_path / "absent.env")


def test_credentials_from_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text(f"# comment\nAPCA_API_KEY_ID={FAKE_KEY}\nAPCA_API_SECRET_KEY='{FAKE_SECRET}'\n")
    assert load_credentials(env) == (FAKE_KEY, FAKE_SECRET)


def test_verify_refuses_held_out_sample_before_network(monkeypatch, capsys):
    from trading import verify_data_access
    monkeypatch.setenv("APCA_API_KEY_ID", FAKE_KEY)
    monkeypatch.setenv("APCA_API_SECRET_KEY", FAKE_SECRET)

    def no_network(*a, **k):
        raise AssertionError("network call attempted")
    monkeypatch.setattr(alpaca_client.ReadOnlyAlpacaClient, "_get", no_network)
    assert verify_data_access.main(["--as-of", "2025-03-03"]) == 3        # final period
    assert verify_data_access.main(["--as-of", "2023-03-01"]) == 3        # validation period
    out = capsys.readouterr().out
    assert "REFUSED" in out and FAKE_SECRET not in out


def test_paper_url_is_paper():
    assert alpaca_client.PAPER_TRADING_URL == "https://paper-api.alpaca.markets"


def test_rate_limit_is_retried_then_succeeds():
    http = FakeHttp([FakeResponse(429, {"message": "too many requests"}),
                     FakeResponse(200, {"bars": {"AAPL": [{"t": "a"}]}, "next_page_token": None})])
    waits = []
    client = ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=http, sleep=waits.append)
    assert client.get_bars("AAPL", "1Day", "s", "e", feed="sip", adjustment="raw")["bars"] == [{"t": "a"}]
    assert len(http.calls) == 2 and waits == [alpaca_client.RATE_LIMIT_WAIT_SECONDS]


def test_rate_limit_gives_up_after_bounded_retries():
    http = FakeHttp([FakeResponse(429, {"message": "slow down"})] * (alpaca_client.RATE_LIMIT_RETRIES + 1))
    client = ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=http, sleep=lambda s: None)
    with pytest.raises(AlpacaAccessError) as err:
        client.get_account()
    assert err.value.status_code == 429 and len(http.calls) == alpaca_client.RATE_LIMIT_RETRIES + 1


def test_multi_symbol_pagination_merges_pages_and_keeps_feed():
    """SYNTHETIC responses: symbols can be split across pages; nothing is dropped or merged."""
    http = FakeHttp([
        FakeResponse(200, {"bars": {"SPY": [{"t": "1"}], "QQQ": [{"t": "1"}]}, "next_page_token": "P2"}),
        FakeResponse(200, {"bars": {"QQQ": [{"t": "2"}], "IWM": [{"t": "1"}]}, "next_page_token": None}),
    ])
    client = ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=http)
    out = client.get_bars_multi(["SPY", "QQQ", "IWM"], "1Min", "s", "e", feed="sip", adjustment="raw")
    assert out["pages"] == 2 and [b["t"] for b in out["bars"]["QQQ"]] == ["1", "2"]
    assert len(out["bars"]["IWM"]) == 1 and http.calls[0]["params"]["symbols"] == "SPY,QQQ,IWM"
    assert all(c["params"]["feed"] == "sip" for c in http.calls)


def test_quotes_page_cap_marks_incomplete():
    """SYNTHETIC: a remaining page token at the cap means incomplete, never complete."""
    http = FakeHttp([FakeResponse(200, {"quotes": {"SPY": [{"t": str(i)}]}, "next_page_token": f"P{i}"})
                     for i in range(3)])
    client = ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=http)
    out = client.get_quotes("SPY", "s", "e", feed="sip", max_pages=2)
    assert out["pages"] == 2 and out["complete"] is False and len(out["quotes"]) == 2
    assert len(http.calls) == 2 and http.calls[1]["params"]["page_token"] == "P0"
    assert all(c["params"]["feed"] == "sip" and c["url"].endswith("/v2/stocks/quotes") for c in http.calls)


def test_quotes_complete_when_no_token():
    http = FakeHttp([FakeResponse(200, {"quotes": {"SPY": [{"t": "a"}]}, "next_page_token": None})])
    out = ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=http).get_quotes("SPY", "s", "e", "sip", max_pages=5)
    assert out["complete"] is True and out["pages"] == 1


def test_corporate_actions_merge_and_cap():
    """SYNTHETIC records."""
    http = FakeHttp([
        FakeResponse(200, {"corporate_actions": {"cash_dividends": [{"ex_date": "2019-06-21"}]}, "next_page_token": "P2"}),
        FakeResponse(200, {"corporate_actions": {"cash_dividends": [{"ex_date": "2019-09-20"}]}, "next_page_token": None}),
    ])
    out = ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=http).get_corporate_actions(
        ["SPY"], ["cash_dividend"], "2016-01-04", "2021-12-31", max_pages=3)
    assert out["complete"] is True and len(out["corporate_actions"]["cash_dividends"]) == 2
    assert http.calls[0]["url"].endswith("/v1/corporate-actions")


def test_access_refusal_on_quotes_raises_without_retry():
    http = FakeHttp([FakeResponse(403, {"message": "SYNTHETIC: subscription does not permit"})])
    with pytest.raises(AlpacaAccessError) as err:
        ReadOnlyAlpacaClient(FAKE_KEY, FAKE_SECRET, http=http).get_quotes("SPY", "s", "e", "sip", max_pages=5)
    assert err.value.status_code == 403 and len(http.calls) == 1
