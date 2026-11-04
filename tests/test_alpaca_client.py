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
    assert public == {"get_account", "get_bars", "get_bars_multi"}
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
