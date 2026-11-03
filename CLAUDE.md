# TradingProject

Paper-trading research system for US stocks (day trading). The current goal is
verified data access, reproducible research, and software-enforced risk
controls. No strategy has been chosen. Nothing here promises profit.

The owner is a beginner: explain terms in plain language, and keep proposed,
implemented, tested, and verified behavior clearly separate (see PROGRESS.md).

## Execution boundary (hard rules)

- Never submit, replace, cancel, or close broker orders or positions, and never
  change account settings, unless the owner explicitly approves a later
  milestone that allows it.
- Never enable live trading. Only `https://paper-api.alpaca.markets` and
  `https://data.alpaca.markets` are allowed hosts (`trading/alpaca_client.py`).
- `trading/alpaca_client.py` is read-only (HTTP GET only). Do not add write methods to it.
- Any future order code must call `trading.safety.require_order_submission_allowed()`
  first. It blocks unless `TRADING_MODE=paper` and `ORDER_SUBMISSION_ENABLED=true`.
- The daytrading-starter skill is for planning and analysis only; it does not
  authorize orders.
- Do not claim monitoring or unattended operation unless a running service is verified.

## Credentials

- Keys live only in `.env` (git-ignored) or environment variables:
  `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`. Template: `.env.example`.
- Never print, log, screenshot, or commit keys. Never read keys from the Claude
  desktop configuration, and never ask for them in chat.
- Saved account snapshots exclude `id` and `account_number`.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
copy .env.example .env    # then add paper keys yourself
```

`requirements.txt` lists direct pins; `requirements.lock` is the full `pip freeze`.

## Verification

```powershell
.venv\Scripts\python -m pytest -q                       # offline tests, synthetic fixtures
.venv\Scripts\python -m trading.verify_data_access      # live read-only check (feed=sip)
.venv\Scripts\python -m trading.verify_data_access --feed iex
```

Exit codes for the data check: 0 = success, 1 = API refused or failed, 2 = no credentials.

## Experiments

- Spec first, code second: `research/<id>/SPEC.md` is approved by the owner before coding.
- `trading/experiment.py` enforces the period lock and variant budget. Never bypass it,
  never run the final period without explicit owner approval, and never edit
  `research/*/variants.csv` except by appending through the runner.
- Risk values in `trading/risk.py` are placeholders until the owner sets them (SPEC D1).

## Data conventions

- Exchange calendar: `exchange_calendars` XNYS (holidays, early closes). Market
  timezone `America/New_York`; timestamps stored as UTC plus a converted ET column.
- A session is "completed" 15 minutes after its close (Alpaca free-plan SIP delay).
- Feeds: `sip` = consolidated, all US exchanges; `iex` = one exchange, partial
  volume. Always request a feed explicitly and record it. Never switch feeds
  silently on an error.
- Default adjustment: `raw` (no split/dividend adjustment). Record it.
- 1-minute bars cover the regular session only, `[open, close)`. Alpaca creates
  a bar only when a trade occurred, so a missing minute can mean "no trades on
  this feed" rather than lost data. IEX has far more empty minutes than SIP.
- Output goes to `data/alpaca/<UTC retrieval time>/`: CSV bars, `provenance.json`,
  `validation.json`, `account.json`. `data/`, `logs/`, `results/` etc. are git-ignored.
- Test fixtures are synthetic and labeled as such. They are never evidence of
  market behavior or performance.
