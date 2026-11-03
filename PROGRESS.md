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

## Status audit (2026-11-03, after milestone 4a)

- **DEMO checks passed** in the built-in browser:
  - tower selection, the six tabs, chart, tables and mode labels
  - pause, resume, restart and speed
  - city-vs-report consistency for all four towers
  - error responses (404 and 403)
  - the console showed only those deliberate errors and stream resets from server restarts
- **Tests:** `pytest -q`: 103 passed (9 new in `tests/test_history.py`). `npm run build`: type check passed.
- **Implemented:** historical storage (`trading/history.py`) and HISTORICAL REPLAY mode
  (`trading/dashboard/historical_replay.py`, `server --mode historical`).
- **Unverified: real Alpaca access and historical replay with real data.** No credentials
  were available in this session: no `.env` file, no `APCA_*` variables, no Alpaca connector.
  `verify_data_access` exits 2 (BLOCKED) and historical mode refuses to start. The
  history code has only been exercised against fake API responses.

| Feature | Status | Evidence / reason |
|---|---|---|
| Trading City and tower panels | Verified (DEMO) | Built-in browser: selection, six tabs, chart, tables, no overflow |
| Shared event records, consistent totals | Verified (DEMO) | Tests plus a browser cross-check: label = snapshot = report; equity identity |
| Demo replay controls | Verified | Pause holds the cursor, resume advances, restart, speed |
| Historical data retrieval and validation | Implemented, unverified | `trading/history.py` tested with fake API responses only; no keys |
| Historical session replay | Implemented, unverified | `--mode historical` refuses without stored data (checked); never run on real data |
| Strategy spec and evaluation | Verified on synthetic data | Spec v1.1 with hash; evaluation tests; not run on real data |
| Scenario simulation | Missing (proposed) | `docs/PRODUCT_SPEC.md` section 8 awaits review |
| Alpaca paper-account monitoring | Missing | Access not verified |
| All dashboard numbers | Illustrative | DEMO fixtures |

## Journal and research workflow, milestone 4a+ (2026-11-03)

Fresh evidence this session:
- **Setup is reproducible:** a brand-new venv built from `requirements.lock` reports no
  broken requirements (`pip check`) and 103 tests passed, before this milestone's changes.
- **Tests:** `pytest -q`: 110 passed (7 new in `tests/test_journal.py`). `npm run build`:
  type check passed.
- **Alpaca:** still unverified.
  - There is no `.env` file, and `APCA_*` is not set in this shell or at the Windows user level.
  - There is no Alpaca connector in this session.
  - `verify_data_access` exits 2 (BLOCKED).

Implemented:
- `trading/journal.py`: one row per strategy per session, including skips, risk blocks and
  sessions in progress, built from the ledger records the city uses.
- `trading/research_run.py`: one command that runs the stored data, versioned strategy,
  chronological replay, modeled fills and costs and risk checks, and writes the journal,
  evaluation and provenance to `results/research/`.
  - Historical runs are appended to `research/001_intraday_momentum/inspection_runs.csv`.
  - A historical run refuses without stored data, with no synthetic substitute.
- Dashboard: a seventh tower tab (Journal) with CSV download.

Verified on DEMO data, in tests and in the browser:
- journal net = city realized = engine = evaluation report, for every tower
- every session appears, and the equity chain is continuous
- the halted session is shown with its reason
- the historical path is tested only with fake API-shaped data

Known defects and limitations:
- **Daily loss limit:** it exists and is unit-tested, but the engine checks it once before
  each day's single trade, so in experiment 001 it can never trigger. It needs a
  within-day check before any multi-trade strategy.
- **Costs** are unmeasured guesses, until a spread measurement exists.
- **Risk limits** are placeholders (D1 unanswered).
- **No real-data results exist** for any strategy.

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
