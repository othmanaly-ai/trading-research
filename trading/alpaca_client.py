"""Read-only Alpaca client for the paper account and historical market data.

This class can only send HTTP GET requests, and only to the paper trading host
and the market-data host. It has no method that submits, replaces, cancels or
closes orders or positions, or changes account settings.
"""

import os
import time
from pathlib import Path

import requests

PAPER_TRADING_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"
ALLOWED_HOSTS = (PAPER_TRADING_URL, DATA_URL)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RATE_LIMIT_RETRIES = 5
RATE_LIMIT_WAIT_SECONDS = 15

# Account fields worth recording. Identifiers such as id and account_number
# are deliberately left out of anything we save.
ACCOUNT_FIELDS = (
    "status", "currency", "cash", "equity", "last_equity", "buying_power",
    "portfolio_value", "pattern_day_trader", "daytrade_count",
    "trading_blocked", "account_blocked", "transfers_blocked",
)


class MissingCredentials(RuntimeError):
    pass


class AlpacaAccessError(RuntimeError):
    def __init__(self, status_code: int, message: str, url: str):
        super().__init__(f"HTTP {status_code} from {url}: {message}")
        self.status_code = status_code


def _read_dotenv(path: Path) -> dict[str, str]:
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_credentials(env_file: Path | None = None) -> tuple[str, str]:
    """Environment variables first, then the project's .env file."""
    dotenv = _read_dotenv(env_file or PROJECT_ROOT / ".env")
    key = os.environ.get("APCA_API_KEY_ID") or dotenv.get("APCA_API_KEY_ID", "")
    secret = os.environ.get("APCA_API_SECRET_KEY") or dotenv.get("APCA_API_SECRET_KEY", "")
    if not key or not secret:
        raise MissingCredentials(
            "APCA_API_KEY_ID and APCA_API_SECRET_KEY are not set. Set your Alpaca PAPER keys "
            "as Windows user environment variables (then open a new terminal), or in a .env "
            "file in the project folder (see .env.example; .env is git-ignored)."
        )
    return key, secret


class ReadOnlyAlpacaClient:
    def __init__(self, key_id: str, secret_key: str, http=None, timeout: float = 30, sleep=time.sleep):
        self._http = http or requests.Session()
        self._sleep = sleep
        self._headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret_key}
        self._timeout = timeout

    def __repr__(self) -> str:
        return "ReadOnlyAlpacaClient(<credentials hidden>)"

    def _get(self, base: str, path: str, params: dict | None = None) -> dict:
        if base not in ALLOWED_HOSTS:
            raise ValueError(f"host not allowed: {base}")
        url = base + path
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            resp = self._http.get(url, headers=self._headers, params=params, timeout=self._timeout)
            if resp.status_code != 429 or attempt == RATE_LIMIT_RETRIES:
                break
            # Rate limited (HTTP 429): wait and retry the same GET, a bounded number of times.
            self._sleep(RATE_LIMIT_WAIT_SECONDS * (attempt + 1))
        if resp.status_code != 200:
            try:
                message = resp.json().get("message", resp.text)
            except ValueError:
                message = resp.text
            raise AlpacaAccessError(resp.status_code, str(message)[:300], url)
        return resp.json()

    def get_account(self) -> dict:
        raw = self._get(PAPER_TRADING_URL, "/v2/account")
        return {k: raw.get(k) for k in ACCOUNT_FIELDS}

    def get_bars(self, symbol: str, timeframe: str, start: str, end: str,
                 feed: str, adjustment: str, limit: int = 10000) -> dict:
        """All bars for one symbol, following next_page_token until exhausted."""
        params = {
            "symbols": symbol, "timeframe": timeframe, "start": start, "end": end,
            "feed": feed, "adjustment": adjustment, "limit": limit, "sort": "asc",
        }
        bars, pages = [], 0
        while True:
            body = self._get(DATA_URL, "/v2/stocks/bars", params)
            pages += 1
            bars.extend((body.get("bars") or {}).get(symbol, []))
            token = body.get("next_page_token")
            if not token:
                break
            params = {**params, "page_token": token}
        return {"bars": bars, "pages": pages, "currency": body.get("currency")}
