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

## Pre-evaluation hardening (2026-11-03, after 9064814)

- **First blocker unchanged:** secure data configuration.
  - Checked again this session: no `.env` file, and `APCA_*` is not set in the shell or at
    the Windows user level.
  - `.env` and `.env.*` are git-ignored; only `.env.example` is tracked.
  - The missing-credential message now names both supported mechanisms.
- **Data provenance (`trading/history.py`):** for the first real sample, it now
  - keeps the unmodified API bars (`raw/`)
  - records requested vs received ranges and pagination completeness
  - records missing minutes per session, daily-bar checks, the transformations applied, and
    known limitations
  - tested with fake API-shaped data only
- **Daily loss limit now enforced (spec v1.2, section 17 item 7):**
  - marked to market after each completed bar, so unrealized losses count
  - exits at the next bar's open; a stop inside the same bar takes priority
  - tests cover the breach timing, stop priority, end-of-session flat, and per-trade
    accounting identities
- **Experiment lock** `001-eaa09c9d5a` (`research/001_intraday_momentum/EXPERIMENT_LOCK.json`):
  - records the hypothesis, spec v1.2 and its hash, costs, periods, budget, pass rules and
    placeholder risk limits
  - records zero real sessions stored or inspected in any period at lock time
  - `run_experiment` refuses when the definition differs from the lock
  - every attempt (completed, refused, failed) is appended to `experiment_attempts.csv`
  - reports state whether validation or final sessions were already inspected
- **Dashboard:** the Rules tab shows the lock id and status; the Historical tab shows stored
  data provenance once data exists.
- **Tests:** `pytest -q`: 118 passed. `npm run build`: type check passed. Checked in the
  browser: the Rules tab lock display, the honest Historical tab, the mode strip, and no
  overflow.
- **No evaluation was run:** there is no real data. Nothing here is evidence about the strategy.

## Alpaca read-only access VERIFIED (2026-11-03, 23:51 UTC)

- **Credentials:** `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` are present as environment
  variables. Values were never displayed; the Key ID has the paper-style `PK` prefix.
  `TRADING_MODE=paper` and `ORDER_SUBMISSION_ENABLED=false`, so the order guard blocks
  submission (checked by calling it).
- **Held-out guard added:** the default check (last 5 sessions, Oct 28 – Nov 3 2026) overlaps
  the final period, so `verify_data_access` now refuses held-out samples (exit 3) and takes
  `--as-of` / `--symbol`.
- **Command run:**
  `python -m trading.verify_data_access --symbol SPY --as-of 2016-02-01 --feed sip`, exit 0.
- **Paper account read (`GET /v2/account`):** passed. Status ACTIVE; equity, cash and portfolio
  value $100,000; buying power $400,000 (the paper default of 4x intraday margin; this
  project does not use leverage unless the owner chooses it); trading not blocked. No `id`
  or `account_number` saved.
- **SPY daily bars, SIP, raw, 2016-01-26 to 2016-02-01:** passed. 5 of 5 sessions, 1 page,
  structural checks clean.
- **SPY 1-minute bars, SIP, regular session 2016-02-01:** passed. 390 of 390 minutes, 1 page,
  no gaps, no bars outside the session.
- **Observation:** the official daily close (193.65) differs from the last 1-minute bar's
  close (193.69). That is the closing auction, relevant to decision D4 (exit at 15:59 vs
  market-on-close).
- **Not checked:** the IEX feed, multi-page pagination against the real API, the
  `trading.history` bulk store, and historical replay on real data.
- Saved under `data/alpaca/20261103T235104Z/` (git-ignored).

## Owner risk baseline implemented, lock pending a D6 decision (2026-11-03)

- **Owner limits** are recorded as `trading/risk.py: OWNER_BASELINE_2026_11_03`:
  $100,000 start; 0.10% risk per trade including modeled costs; 0.50% daily; 3% drawdown from
  the high-water mark; 5% position notional; 10% gross exposure; 2 positions; no leverage.
- **Engine changes** (`trading/backtest.py`):
  - Sizing takes the most restrictive cap and rounds down: risk with round-trip costs,
    notional, gross exposure including pending entries, position count, participation.
  - Equity is marked after every bar as realized + net-if-closed after modeled costs.
  - A daily breach exits at the next bar's open (gaps and costs included) and blocks the rest
    of the session.
  - A drawdown breach exits the same way and halts permanently.
- The dashboard ledger's unrealized P&L now uses the same after-cost definition.
- **Tests:** `pytest -q`: 130 passed (new risk, engine and lock tests).
- **Lock** `001-eaa09c9d5a` is now MISMATCHED (new risk fields), as designed. It has not been
  superseded yet because the requested long-only constraint conflicts with accepted decision
  D6 (long and short). Candidate ids: `001-dea482a7be` (long and short) and `001-872d4e72b4`
  (long-only).
- **Not built:** a multi-strategy account simulator. Experiment 001 has one strategy, so
  account-level and per-strategy limits coincide; the demo dashboard's four towers still use
  separate demo allocations.

## Spec v1.3 locked as experiment 001-fd13f1fdef (2026-11-04 00:11 UTC)

- **Owner decisions:** long-only (D6 changed); the owner risk baseline (D1); halt-affected
  sessions kept.
- **Involuntary overnight carry:** only when no bar remains to exit on. Labeled
  "unresolved: halt or missing data", because bars cannot tell a halt from missing feed data.
  The carry exit's P&L counts against the next session's daily and drawdown limits. No
  end-of-day fill is ever invented: the old "last earlier bar" fill rule was removed.
- **Verified by tests:**
  - equity = start + realized + net liquidation P&L, with each cost counted once
  - daily losses accumulate across trades and marks
  - a gap through the daily limit exits at the next open with a real loss above the threshold
  - the drawdown halt never resets
  - carry blocks the next session when its loss breaches the limit
- **Clarification:** the earlier "10% / 60% move" figures were a simplified single-position
  illustration, not an account-risk assessment. The $100 stop-risk figure is a planned loss
  under modeled fills; gaps can exceed it.
- **Baselines for long-only:** always-long trades every signal session (about twice the
  exposure). The random baseline is long or flat at the strategy's own long rate.
- **History download:** monthly chunks; refuses validation and final dates without explicit flags.
- **Lock history:** `001-eaa09c9d5a` was archived in `locks/` with the reason.
- **Tests:** `pytest -q`: 136 passed.

## Development evaluation of 001-fd13f1fdef: FAILED (2026-11-04)

- **Data:** `python -m trading.history --start 2015-11-02 --end 2021-12-31`. 74 monthly chunks,
  146 pages, complete. 1,511 of 1,511 development sessions usable; 99.983% of minutes present.
  - Alpaca returned nothing before 2016-01-04.
  - No validation or final data was retrieved.
- **Run:** `python -m trading.evaluate --period development`.
  - Net -1.41% after base costs and -0.50% even at zero cost. Mean per-trade move before
    costs -1.24 bp (SE 1.08); Sharpe CI [-2.72, -0.59].
  - Every year was negative.
  - It reached only the 10th percentile of random long/flat entries.
  - It failed pass rules 1, 2, 4 and 5.
  - Details: `research/001_intraday_momentum/RESULTS_development.md`.
- **Also added:** a bounded HTTP 429 retry in the read-only client (2 tests); `trading/evaluate.py`.
- **Recommendation:** reject the hypothesis; do not run validation for this variant.

## Experiment 001 CLOSED; experiment 002 candidates proposed (2026-11-04)

- `research/001_intraday_momentum/STATUS.json` now reads CLOSED. `run_experiment` refuses
  runs for a closed experiment (tested). The real refusal is logged in `experiment_attempts.csv`.
- `research/EXPLORATION_LOG.md` records every look at historical data, including the
  development-only trigger-frequency counts (no returns computed).
- `research/NEXT_HYPOTHESES.md` holds two speculative candidates:
  - **A:** long-only 30-minute opening-range breakout (recommended for testability)
  - **B:** long-only gap-down reversal
  - Owner to choose; nothing implemented.
- **Tests:** `pytest -q`: 139 passed.

## Experiment 002-895a4f9c5d: development FAILED (2026-11-04)

- **Spec and build:** spec v1.0 approved; implemented behind `trading/engine.py`
  (SessionStrategy interface). The tested code commit is `33fede4`; the lock is committed in
  `4ba245d`.
- **Experiment 001 reproduces exactly** at base, stress and severe costs, and is still CLOSED.
- **Development run `20261104T034149Z`:** base -0.014%, stress -2.19%, intraday max drawdown 0.82%.
  - D1, D4, D5 and D6 fail; D2 and D3 pass.
  - 0 unresolved cases; 2 M2 sessions; 3 incomplete opening ranges (March 2020).
  - Details: `research/002_opening_range_breakout/RESULTS_development.md`.
- **Reporting defect:** B1 mean hold and stop distance were NaN; fixed with a test and
  recomputed, and the gate fields were verified identical.
- **Validation and final:** untouched. **Tests:** `pytest -q`: 161 passed.

## Experiment 002 closed; research-job workflow; city restarted (2026-11-04)

- **Experiment 002** is CLOSED (FAILED_DEVELOPMENT, commit 827a62c). The runner refuses all
  new evaluations of closed experiments (tested); `--inspect` is read-only.
- **Research jobs** (`trading/jobs.py`, commits b4d08e8 and d9c9783):
  - a persisted SQLite store (`data/jobs/jobs.sqlite`, git-ignored)
  - the pipeline ingest -> reconcile -> analysis -> rule_checks -> model_review -> report
  - **Results:** both experiments reconcile with 0 discrepancies (9 and 13 checks).
    model_review is **blocked** (no ANTHROPIC_API_KEY and no authorization); no model output
    exists.
  - **Tests:** success, missing and corrupt artifacts, failure recovery, retry/restart duplicate
    prevention, tamper detection, cancel, dashboard/store consistency, strict JSON (171 pass).
- **City:** "Research jobs" tab (real, not demo). The mode strip text was corrected: paper
  account access verified via CLI (monitoring not implemented); simulation awaiting review;
  historical replay verified to build from real stored data.
- **Server:** restarted via the documented `demo-dashboard` launch configuration. One listener
  on 127.0.0.1:8765 (this project, DEMO mode).
- **Alpaca:** read-only verification re-run 2026-11-04 04:01 UTC with the current user-level
  credentials (session values match): account ACTIVE, SPY SIP development sample complete.

## Research-job control panel in the city (2026-11-04)

Workflow, all in the browser at http://127.0.0.1:8765, "Research jobs" tab:
select a saved experiment -> inspect its artifacts -> preview the task -> start the one allowed
pipeline -> watch progress -> cancel if needed -> open the report.

- **Implemented and tested:**
  - **Allowlist:** experiments 001 and 002; the single pipeline `reconcile_report`. The server
    accepts only `{experiment, pipeline}` and has no command, path or shell input.
  - **Backend validation:** cross-site requests are refused. The server checks the Host header,
    requires the X-Dashboard-Control header (forces a CORS preflight), checks Origin and
    Sec-Fetch-Site, requires JSON content-type, and caps body size.
  - **Execution:** one background thread executes jobs, outside the web request.
  - **Deduplication:** check-and-insert runs in one SQLite `BEGIN IMMEDIATE` transaction, so
    simultaneous clicks create one pipeline (regression test: 8 parallel requests). Completed
    steps are reused, never redone.
  - **Cancellation:** a queued pipeline is cancelled at once. A running pipeline gets
    "cancellation requested"; the current step finishes, and the remaining steps become
    cancelled. Completed evidence is kept.
  - **Restart:** running work becomes FAILED "interrupted", never completed.
  - **Model review:** reported as NOT IMPLEMENTED / UNAVAILABLE. A key alone changes nothing.
- **Fixed during verification:**
  - Concurrent first opens of a new job database could report "database is locked". Schema
    setup is now serialized, and the server answers database errors with 503.
  - Stale 3D labels stayed on screen after switching experiments.
- **Verified in the built-in browser** (Playwright is not installed):
  - **Real server:** start, duplicate clicks and 6 parallel requests (no new job rows), 8
    invalid requests refused, report opens. Database, table and 3D towers agree.
  - **Throwaway harness:** a separate process with copied artifacts, a temporary database and
    4-second steps. Live progress, cancellation (3 steps kept, 3 cancelled), a failure (missing
    run file: ingest failed, rest blocked), and a hard kill plus restart (pipeline FAILED
    "interrupted").
- **Tests:** 190 pass.

## Model-powered reviewer: implemented, UNAVAILABLE pending owner decision (2026-11-04)

- **Implemented and tested with MOCKED responses only** (`trading/reviewer/`, `tests/test_reviewer.py`,
  33 tests). No real model has been called. No money has been spent. The Anthropic SDK is not installed.
- **What it is:** an automated second review of a closed experiment.
  - **Input:** a selected, sanitized evidence package (34–39 items, about 18k characters per experiment).
  - **Output:** explanations of the failed gates, limitations and discrepancies. Every fact and
    deduction cites an evidence item. Each finding is labelled fact, deduction or suggestion.
  - **Authority:** deterministic checks stay in charge. A review that contradicts them, approves
    anything, or asks for held-out data is rejected.
- **Safeguards (tested, mocked):**
  - all blockers reported at once
  - worst-case reservation before the call, checked atomically against per-run and monthly caps
  - provider-reported usage recorded with its cost
  - uncertain timeouts charged and never auto-repeated; retries only for unbilled 429/529, at most 3 attempts
  - cache by evidence + prompt + model
  - artifact instruction injection flagged and unable to flip gates
  - secrets and local paths redacted; oversized input refused
  - real provider error mapping checked against a mock SDK module
- **City:**
  - the review panel shows MOCK and second-review labels, provenance, usage, cost and validation
    errors, plus clickable citations that open the cited evidence item
  - a readiness section lists the five gates, proposed limits and prices
- **Verified in the built-in browser:**
  - real server: the model_review job BLOCKED with all four missing items, the report states it,
    and deterministic steps were reused
  - throwaway harness with a MOCK provider: the review panel and evidence links render, and
    injected text is flagged
- **Waiting for the owner:** provider/model choice, a budget authorization file, the API key in
  your own environment, SDK install, then one approved verification call. See `docs/MODEL_REVIEW.md`.
- **Tests:** 223 pass.

## Owner chose Anthropic Opus 5.5, $5/month (2026-11-04)

- **Done:**
  - `anthropic==2.4.0` installed and pinned (`requirements.txt`, `requirements.lock`). Only new
    packages were added; nothing else was upgraded.
  - **Credential separation:** paid reviews run only from the command line
    (`trading.jobs run`, `trading.reviewer verify`), which read `ANTHROPIC_API_KEY` from the
    environment or `.env`. The dashboard server strips credential variables before any job runs.
    Browser-started pipelines reuse cached reviews or report that the review must run from the
    command line; a click can never cause a charge.
  - The authorization file may contain a byte-order mark (Notepad).
- **Tested:**
  - the separation, `.env` reading and the byte-order-mark case
  - real SDK error mapping against a closed local port (no request left this machine)
  - 229 tests pass
- **Still not done (owner steps):**
  - write `research/MODEL_REVIEW_AUTHORIZATION.json`
  - set the API key in your environment or `.env`
  - run the verification call
- **No paid call has been made.** Model review remains UNAVAILABLE.

## Paid AI postponed; read-only market monitoring in the city (2026-11-04)

- **Model review: OPTIONAL / DISABLED.**
  - The owner revoked the paid-call authorization. `MODEL_REVIEW_AUTHORIZATION.json` is marked
    REVOKED, and every paid path refuses it.
  - The one attempted call (16:09:56 UTC) was rejected for insufficient credit: not billed, not
    retried. The record is kept.
  - Pipelines mark model_review as `skipped`. An optional step can never fail the pipeline.
    Reports state that no model review was performed.
  - The key in `.env` was not read or changed.
- **Monitoring (`trading/monitor/`, `docs/MONITORING.md`):**
  - a separate worker process over the read-only Alpaca client (one new GET method: multi-symbol bars)
  - exchange-calendar aware, polling every 60 s
  - freshness labels from source timestamps
  - bounded backoff, duplicate-proof storage
  - persistent status and events
  - Start/Pause/Stop in the city, plus the command line
  - single-instance lock, supervisor restart recovery
  - 3D towers and a matching table
  - never fetches or keeps dates on or before 2026-10-30
- **Verified with real data (2026-11-04, 16:36–16:42 UTC):**
  - **Access:** IEX real-time accepted; recent SIP refused (403, free plan).
  - **Live run:** the worker launched from the city stored today's session: 130 bars per symbol,
    0 duplicates.
  - **Controls:** Pause made no calls; Start resumed; a duplicate worker exited.
  - **Crash recovery:** after a hard kill, the supervisor relaunched it in 22 s and it resumed
    without gaps.
  - **Dashboard restart:** one listener and one worker afterwards.
  - **Stop:** clean exit, no relaunch.
  - **Consistency:** the 3D labels, the table, the API and SQLite agree.
- **Fixed during this work:**
  - refused POSTs now drain the request body; it caused an intermittent connection reset
  - dashboard tests disable the monitor supervisor
- **Tests:** 254 pass, 1 skipped (a no-credentials test skips because a real `.env` exists).

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
