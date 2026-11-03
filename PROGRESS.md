# Progress record

Last updated: 2026-11-03 (checks run around 21:30 UTC; strategy spec drafted later the same day).

## Verified (ran it and saw the result)

| Component | Evidence |
|---|---|
| Python 3.15.2 | `python --version`; venv at `.venv` reports `sys.prefix != sys.base_prefix` |
| Git 2.56.0, repo on `main` | `git --version`; first commit 6c7d1e4 |
| No sensitive files tracked | `git ls-files` checked against key/env/secret patterns: none |
| Ignore rules | `git check-ignore`: `.env`, `*.key`, `secrets/`, `data/...csv`, `logs/*.log`, `*.db`, `.venv/` ignored; `.env.example` and code tracked |
| Dependencies install on Python 3.15 | pandas 3.1.0, exchange_calendars 4.13.2, requests 2.34.2, pytest 9.2.0 (binary wheels) |
| Offline test suite | `pytest -q`: 22 passed (calendar holidays/early close/DST, validation on synthetic bars, client pagination, host guard, no order methods, secret hiding, order guard) |
| Missing-credential handling | `python -m trading.verify_data_access` prints BLOCKED and exits 2 without making a network call |
| Playwright MCP server | Connected in this Claude Code session (25 tools). Not used yet. |
| daytrading-starter skill | Listed as available in this session. Not invoked. |

## Implemented, not yet verified against the real API

- `trading/alpaca_client.py`: read-only paper account and historical bars, with pagination.
  Written from Alpaca's official docs (historical bars reference, market data overview), but
  it has never been run with real keys.
- `trading/verify_data_access.py`: fetches AAPL daily bars for 5 completed sessions and 1-minute
  bars for the latest completed session, then saves data, provenance and validation results.

## Implemented and tested on synthetic data only (no real market data yet)

- Experiment 001 spec: `research/001_intraday_momentum/SPEC.md`. D2-D10 accepted
  2026-11-03; D1 (risk limits, setup answers) still open, so risk values are placeholders.
- Backtest engine `trading/backtest.py`, signal `trading/strategies/intraday_momentum.py`,
  costs `trading/costs.py`, sizing and loss limits `trading/risk.py`, metrics
  `trading/metrics.py`, runner with period lock and variant budget `trading/experiment.py`.
- Evidence: `pytest -q`: 56 passed. The 34 engine/risk/experiment tests use labeled synthetic bars:
  - fills, costs, stops, gap-through stops, the stop on the entry bar
  - future bars cannot change the decision
  - early close, missing and invalid data, halts, MOC
  - kill switch, stress options, sizing caps
  - period lock, budget, and reuse flag
- Speed: about 0.75 s per synthetic year, so roughly 50 s for a full development run.
- **No backtest has been run on real data. There are no strategy results.**
- Not built yet: a loader that downloads and stores 2016-2026 SPY bars; a spread
  measurement from historical quotes.

## DEMO REPLAY dashboard (synthetic data, simulated outcomes)

- Implemented and verified locally on 2026-11-03:
  - **Pieces:** event schema `trading/events.py`, replay builder and ledger in
    `trading/dashboard/`, standard-library server, and React + TypeScript + Three.js app
    in `dashboard/web/`.
  - **Tests:** `pytest`: 18 dashboard tests pass, checking that totals match the engine,
    duplicates don't double-count, records stay per strategy, the halt and data outage
    show, the empty config works, controls behave, and no broker code is loaded.
    `npm run build`: the type check passes.
  - **In-browser checks (built-in browser):**
    - selecting a tower shows that instance's records and chart
    - pause, resume, restart and speed work
    - open positions show unrealized P&L that sums to the account figure
    - the table, sessions and leaderboard views render
    - the empty, reconnecting and `?3d=off` fallback states render
    - reduced motion works, and there are no console errors
    - browser storage is empty, and the bundle has no credential references
- Not done: real Alpaca data or account in the dashboard (plan in `dashboard/README.md`).
  The Playwright connector was disconnected in this session, so the built-in browser was used instead.

## Research & Simulation Lab, milestone 3a (2026-11-03)

- **Spec:** `docs/PRODUCT_SPEC.md` contains the product spec, the four modes
  (never blended) and the milestone checklist. The simulation method in its
  section 8 is **PROPOSED, awaiting review**.
- **Implemented:**
  - versioned strategy specs (`trading/strategies/registry.py`: spec version plus file hash)
  - responsibilities config (`research/responsibilities.json`: all deterministic, manual or
    not implemented; no AI agents; the eleven-skill package is not installed)
  - outcome classification rules (`trading/outcomes.py`)
  - an evaluation report from the shared ledger records (`trading/evaluation.py`)
  - six tower tabs, a mode strip and a Research view in the dashboard
- **Tested:** `pytest`: 94 pass. The 20 new tests check:
  - classification rules, including ambiguous bars and short trades
  - classifier agreement with the engine's stop exits
  - cost accounting and cost sensitivity
  - reports matching the city for every strategy
  - identical result hashes on a rebuilt replay
  - signals recomputed only from bar events that had already arrived
  - spec hash, and honest mode status
- **Browser-checked:**
  - all six tabs render
  - mid-replay, report net equals city realized for all four towers
  - live updates during playback
  - fixed horizontal overflow; no new console errors
- **Still illustrative (DEMO):** every number in the dashboard. Scanner/news,
  historical replay, simulation and paper account show "not available" with the reason.

## Missing

- **alpaca-paper connection:** not present in this Code session (connector list has no Alpaca
  server). No `APCA_*` environment variables are set and there is no `.env` file.
- **Real market data:** none retrieved. No prices, balances or fills have been observed.
- **Risk controls:** only the order-submission switch exists. There is no position sizing and
  no loss limits yet.
- **Python Playwright package:** not installed; not needed yet.

## Known limitations

- `exchange_calendars` emits a pandas 3.1 deprecation warning internally (harmless today).
- Project lives in OneDrive; `.venv` sync can be slow or lock files.
- The bars API does not echo which feed served the data; the record notes "request accepted".
