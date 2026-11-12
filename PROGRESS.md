# Progress record

Last updated: 2026-11-08. The current-status summary below was written from the records listed
in it. The dated log further down is kept as history.

## Current status (2026-11-08)

**In one sentence:** the research system works and its data access is verified. Both strategies
tested so far failed at the development stage. No strategy is approved, and nothing here is
evidence of profit.

### Verified: run, and the result observed

| Area | What is verified | Evidence (dated log section) |
|---|---|---|
| Alpaca read-only access (paper) | Account read; SPY SIP daily and 1-minute bars; IEX real-time; delayed SIP at a 20-min boundary | "Alpaca read-only access VERIFIED" (2026-11-03), re-run 2026-11-04; monitoring sections |
| Order safety | Order guard blocks (`TRADING_MODE=paper`, `ORDER_SUBMISSION_ENABLED=false`); client is GET-only; host allowlist | Guard called directly; tests |
| Historical data store | 1,511 of 1,511 development sessions (2016-2021 SPY SIP) stored with provenance; validation and final never retrieved | "Development evaluation of 001" |
| Research pipeline | Locked experiments, period lock, variant budget, attempt log, closed-experiment refusal; engine accounting checked trade by trade for 001 | 001 and 002 results; tests |
| Risk controls (simulation) | Owner baseline limits enforced in the engine: per-trade, daily (within-day), drawdown halt, notional, exposure | "Owner risk baseline", "Spec v1.3 locked" |
| Research-job pipeline and control panel | Reconcile/report jobs, dedupe, cancel, restart; both experiments reconcile with 0 discrepancies | "Research-job control panel" |
| Read-only market monitoring | Separate worker, crash recovery, daily evidence reports, IEX vs delayed-SIP comparison | Monitoring sections (2026-11-04) |
| City dashboard | Real-record views (overview, monitor, jobs, research, dependencies) and DEMO replay views, kept separate; checked in the built-in browser | City sections (2026-11-05) |
| Offline tests | `pytest -q`: 311 passed, 4 warnings, 0 failed (run 2026-11-08, includes uncommitted working-tree changes) | This update |

### Failed experiments (closed; validation and final data untouched)

| Experiment | Result | Main reason | Record |
|---|---|---|---|
| 001 intraday momentum (v1.3, `001-fd13f1fdef`) | FAILED_DEVELOPMENT: net -1.41% at base costs; -0.50% even at zero cost; 10th percentile of random entry | No predictive relation: the signal picked slightly worse-than-average days | `research/001_intraday_momentum/RESULTS_development.md` |
| 002 opening-range breakout (v1.0, `002-895a4f9c5d`) | FAILED_DEVELOPMENT: net -0.014% at base, -2.19% at stress; 83rd percentile of random entry (95th required) | A small pre-cost edge (about +2.3 bp per trade), equal to the base cost (2.3 bp round trip) | `research/002_opening_range_breakout/RESULTS_development.md` |

A plain-English comparison and the recommended next task: `research/FAILURE_COMPARISON_001_002.md`.

### Blockers

- **Gap-down candidate: DEFERRED_DATA_SEMANTICS.** Not failed, and never evaluated.
  - The quote timestamp clock, the `?` condition code, the NBBO construction, locked/crossed
    meaning and known corrections are undocumented.
  - Downloads are blocked in code.
  - Resuming needs written answers to A1-A5 in
    `feasibility/execution_data/ALPACA_SUPPORT_REQUEST_DRAFT.md` (unsent; sending it is the owner's
    decision), then a new owner decision.
- **Trading costs are unmeasured.** The base, stress and severe models are guesses. 002's result
  hinged on them. The opening-minute quote checks (7 dates) are not a cost model.
- **Development data is partly contaminated** for late-day, morning-range/breakout and
  "buy after down mornings" ideas (`research/EXPLORATION_LOG.md`).
- **Model review: OPTIONAL / DISABLED.** The owner revoked paid calls on 2026-11-04.

### Unfinished or not built

- **No next hypothesis chosen.** The recommendation is an execution-cost measurement first (see the
  comparison file). A six-session pilot is pre-registered in `feasibility/spread_measurement/PLAN.md`
  (commit be2d9cd, 2026-11-08). Its limits are implemented and tested in `trading/spread_measurement.py`
  (19 synthetic tests; suite 330 passed). **Pilot run once on 2026-11-09 01:22 UTC.**
  - 60 of 60 windows were complete and measured, with no cap reached.
  - Usage: 135 of 600 requests, 7.9 of 75 MB.
  - **Provisional result:** the spread was 1 cent most of the time. The estimated spread component
    of execution cost (half-spread) was 0.12-0.25 bp per side, against 0.5 bp assumed at base. It is
    not what every order pays.
  - Every quote carries the unknown code `?`.
  - Details: `feasibility/spread_measurement/FINDINGS_pilot.md`.
  - The cost model is unchanged. The other 18 sessions are pending a separate decision.
- **Scenario simulation** (`docs/PRODUCT_SPEC.md` section 8): proposed, awaiting owner review.
- **Paper-account monitoring in the dashboard:** not implemented. Account access is verified from
  the command line only.
- **Multi-strategy account simulator:** not built.
- **Uncommitted working-tree changes:**
  - a city workspace switcher to the separate Website Agency board (`dashboard/README.md`,
    `dashboard/web/index.html`, `dashboard/web/public/`, `CityView.tsx`, `server.py` CSP,
    `tests/test_dashboard.py`)
  - not recorded in the log below, and not reviewed in this update
- **Monitoring runs only while** this computer, the city server and its worker are running. No
  unattended service is claimed.
- **Never done:** live trading, order submission, any use of validation or final data.

### How to read the log below

The sections below are dated history, oldest first. Statements later contradicted by newer
evidence are marked **[SUPERSEDED ...]** inline, with a pointer to the newer evidence. They were
true when written.

## Verified (ran it and saw the result) (2026-11-03)

| Component | Evidence |
|---|---|
| Python 3.15.2 | `python --version`; venv at `.venv` reports `sys.prefix != sys.base_prefix` |
| Git 2.56.0, repo on `main` | `git --version`; first commit 6c7d1e4 |
| No sensitive files tracked | `git ls-files` checked against key/env/secret patterns: none |
| Ignore rules | `git check-ignore`: `.env`, `*.key`, `secrets/`, `data/...csv`, `logs/*.log`, `*.db`, `.venv/` ignored; `.env.example` and code tracked |
| Dependencies install on Python 3.15 | pandas 3.1.0, exchange_calendars 4.13.2, requests 2.34.2, pytest 9.2.0 (binary wheels) |
| Offline test suite | `pytest -q`: 22 passed (calendar holidays/early close/DST, validation on synthetic bars, client pagination, host guard, no order methods, secret hiding, order guard) |
| Missing-credential handling | `python -m trading.verify_data_access` prints BLOCKED and exits 2 without making a network call |
| Playwright MCP server | Connected in this Claude Code session (25 tools). Not used yet. **[SUPERSEDED: later sessions had no Playwright connector; the built-in browser was used instead]** |
| daytrading-starter skill | Listed as available in this session. Not invoked. |

## Implemented, not yet verified against the real API

**[SUPERSEDED: both were verified against the real paper API on 2026-11-03 23:51 UTC; see "Alpaca read-only access VERIFIED"]**

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
- **No backtest has been run on real data. There are no strategy results.** **[SUPERSEDED: experiments 001 and 002 were evaluated on real 2016-2021 development data on 2026-11-04; both failed]**
- Not built yet: a loader that downloads and stores 2016-2026 SPY bars; a spread
  measurement from historical quotes. **[SUPERSEDED in part: the loader `trading/history.py` was built and used for the development period. A spread measurement (cost model) is still not built; only access and opening-minute quote checks exist]**

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
- Not done: real Alpaca data or account in the dashboard (plan in `dashboard/README.md`). **[SUPERSEDED in part: historical replay builds from real stored data, and real monitoring data is shown (2026-11-04). The paper account is still not shown in the dashboard]**
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
- **[SUPERSEDED: Alpaca access verified 2026-11-03 23:51 UTC; real development data stored 2026-11-04]** **Unverified: real Alpaca access and historical replay with real data.** No credentials
  were available in this session: no `.env` file, no `APCA_*` variables, no Alpaca connector.
  `verify_data_access` exits 2 (BLOCKED) and historical mode refuses to start. The
  history code has only been exercised against fake API responses.

| Feature | Status | Evidence / reason |
|---|---|---|
| Trading City and tower panels | Verified (DEMO) | Built-in browser: selection, six tabs, chart, tables, no overflow |
| Shared event records, consistent totals | Verified (DEMO) | Tests plus a browser cross-check: label = snapshot = report; equity identity |
| Demo replay controls | Verified | Pause holds the cursor, resume advances, restart, speed |
| Historical data retrieval and validation | Implemented, unverified **[SUPERSEDED: verified 2026-11-04, 1,511 sessions]** | `trading/history.py` tested with fake API responses only; no keys |
| Historical session replay | Implemented, unverified **[SUPERSEDED: verified to build from real stored data, 2026-11-04]** | `--mode historical` refuses without stored data (checked); never run on real data |
| Strategy spec and evaluation | Verified on synthetic data **[SUPERSEDED: evaluated on real data; 001 failed]** | Spec v1.1 with hash; evaluation tests; not run on real data |
| Scenario simulation | Missing (proposed) | `docs/PRODUCT_SPEC.md` section 8 awaits review |
| Alpaca paper-account monitoring | Missing | Access not verified **[SUPERSEDED: access verified; dashboard account monitoring still missing]** |
| All dashboard numbers | Illustrative | DEMO fixtures |

## Journal and research workflow, milestone 4a+ (2026-11-03)

Fresh evidence this session:
- **Setup is reproducible:** a brand-new venv built from `requirements.lock` reports no
  broken requirements (`pip check`) and 103 tests passed, before this milestone's changes.
- **Tests:** `pytest -q`: 110 passed (7 new in `tests/test_journal.py`). `npm run build`:
  type check passed.
- **Alpaca:** still unverified. **[SUPERSEDED: verified 2026-11-03 23:51 UTC]**
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
- **[SUPERSEDED: fixed in spec v1.2, within-day check; see "Pre-evaluation hardening"]** **Daily loss limit:** it exists and is unit-tested, but the engine checks it once before
  each day's single trade, so in experiment 001 it can never trigger. It needs a
  within-day check before any multi-trade strategy.
- **Costs** are unmeasured guesses, until a spread measurement exists.
- **Risk limits** are placeholders (D1 unanswered). **[SUPERSEDED: owner baseline set 2026-11-03 and locked in v1.3]**
- **No real-data results exist** for any strategy. **[SUPERSEDED: 001 and 002 results, 2026-11-04]**

## Pre-evaluation hardening (2026-11-03, after 9064814)

- **First blocker unchanged:** secure data configuration. **[SUPERSEDED: credentials present and access verified later the same day]**
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
- **[SUPERSEDED: resolved by the v1.3 lock `001-fd13f1fdef` (long-only), next section]** **Lock** `001-eaa09c9d5a` is now MISMATCHED (new risk fields), as designed. It has not been
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
    exists. **[SUPERSEDED: model review is now OPTIONAL / DISABLED and marked `skipped`; see "Paid AI postponed"]**
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
  - **Model review:** reported as NOT IMPLEMENTED / UNAVAILABLE. A key alone changes nothing. **[SUPERSEDED: implemented with mocks, then OPTIONAL / DISABLED]**
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
- **[SUPERSEDED: owner chose a provider, then revoked paid calls on 2026-11-04]** **Waiting for the owner:** provider/model choice, a budget authorization file, the API key in
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
- **Still not done (owner steps):** **[SUPERSEDED: authorization revoked 2026-11-04; these steps are no longer pending]**
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

## Delayed-SIP vs IEX data-quality comparison (2026-11-04)

- **Access verified first:** delayed SIP was accepted at a 20-minute boundary (HTTP 200, 5/5 bars).
  Recent SIP is refused, as recorded earlier.
- **Implemented** (`trading/monitor/quality.py`), running in the monitoring worker:
  - 20-minute boundary (15 + 5 margin), 120-minute chunks, 5-minute cycles, one end-of-day
    re-observation
  - original observations with revision history and retrieval and availability times
  - deterministic categories, with no invented tolerances
  - backoff that never substitutes another feed
  - restart-safe watermark
  - a daily report in the city, with supporting records per minute and run, access and error states
- **Tested:** 13 labelled synthetic tests (boundary, chunking, restart, categories, bps and $
  differences, volume share, zero volume, timestamps, conflicting duplicates, corrections and
  revisions, labels, access failure, connection backoff, holiday, reserved date, early close,
  endpoints) and multi-symbol pagination.
- **Fixed:** the no-credentials history test now runs (isolated root; any read outside it fails
  the test); 0 skipped.
- **Real run:** 384 comparisons for 128 minutes. All consistent subsets; IEX volume share of
  4.1% (SPY), 1.5% (QQQ) and 3.7% (IWM). See `docs/MONITORING.md`.
- **Tests:** 267 pass, 0 skipped.

## Multi-session monitoring and daily evidence reports (2026-11-04)

- **Inspected:** comparisons had used the re-fetched IEX bars, recording the live capture only as
  present/absent, and only the current ET date was ever compared.
- **Fixed:**
  - comparisons now keep live IEX values next to re-fetched ones
  - reports separate live capture, later IEX revisions and delayed SIP
  - "consistent" now reads "IEX within the SIP range (prices can still differ; not identical, not a
    suitability check)"
- **Implemented:**
  - session states: in progress, provisional, finalized, incomplete
  - recovery of unfinished monitored sessions within 5 sessions, under a 120-requests-per-hour
    budget, with 120-minute chunks
  - incomplete reported, never success (beyond the lookback, or historical access refused 3 times)
  - idempotent finalization with versioned, amend-only reports
  - worker-run records with code version
  - downtime classed as planned, unplanned or unrecorded
  - normal vs catch-up latency, for live receipt and for SIP after eligibility
  - city session history, daily report and worker-health summary
  - supervisor launch-limit errors logged once per 10 minutes
- **Tested** (labelled fixtures, 14 new tests): shutdown before the post-close check, then restart
  the next day; both midnight boundaries; weekend; early close; repeated finalization and
  amendment; refused historical access; bounded backlog, lookback and request budget; reserved
  session; live, revision and SIP separation; downtime, restarts, failures; unrecorded intervals.
- **Real operation:** after the deploy, the current session stayed compared to the 20-minute
  boundary. Live receipts: 45 normal (median 22 s), 123 by catch-up (median about 65 min). No IEX
  revisions. Development restarts hit the supervisor's 6-per-hour launch limit, which blocked
  relaunch until the oldest launch aged out (it worked as designed, and the report shows it).
- **Tests:** 281 pass, 0 skipped.

## Execution-data access check (2026-11-04)

- **Pre-registered** (commit 883f7bb): 7 development dates, endpoints, caps.
- **Implemented:**
  - GET-only `get_quotes` and `get_corporate_actions` with hard page caps
  - `trading/execution_feasibility.py`, which counts every HTTP call, enforces a 240-request
    cap and stops a path after an access failure
- **Tested:** synthetic fixtures for the cap, held-out date refusal, path stopping without
  retry, and quote validation.
- **Verified in real use:** 57 requests, all HTTP 200, with no cap reached.
  - historical SIP quotes and raw bars are accessible
  - the dividend records are incomplete and not point-in-time
- **Recorded:** findings in `feasibility/execution_data/FINDINGS.md`; downloads git-ignored.
  This is not research evaluation.

## Distribution calendar, quote interpretation and exit coverage (2026-11-04)

- **Done:**
  - issuer (SSGA) SPY distribution history captured with provenance
  - 24 development ex-dates; reconciled with Alpaca (21 of 24, 0 extra)
  - archived schedules give point-in-time evidence for 7 of 24 ex-dates
- **Quote coverage:** checked through 10:01 (pre-registered, commit a67fc20); 195 requests,
  all HTTP 200, complete.
- **Locked/crossed treatment:** proposed.
- **Not established:** the quote timestamp clock and the 2016-2020 condition codes.
- **Verdict:** defer the gap-down candidate (`feasibility/execution_data/FINDINGS_2.md`).
  No returns computed, no experiment.

## Gap-down candidate deferred (2026-11-04)

- **State:** `gap_down_opening` marked DEFERRED_DATA_SEMANTICS
  (`research/candidates/gap_down_opening/STATUS.json`). It is not failed and not
  performance-rejected.
- **Downloads:** blocked in code; tested.
- **Support request:** an unsent draft, `feasibility/execution_data/ALPACA_SUPPORT_REQUEST_DRAFT.md`,
  with resume criteria A1-A5.
- **Corrections:** scope wording fixed in the feasibility records.
- **City:** the research jobs view lists the candidate, its blockers and its records, using the
  existing table component.

## City clarity and usability (2026-11-05)

- **Real vs demo views:** real views (Overview, Market monitor, Research jobs, Research) have their
  own banner. They show no replay clock, demo controls, simulated account, demo activity or demo
  risk alerts. Demo views keep all of these. The view tabs are grouped and labelled "Real records"
  and "Demo replay (synthetic)".
- **Overview (new; existing endpoints only):**
  - server and worker health, market status, latest IEX bar times
  - latest session state
  - research-job states, closed experiments, the deferred candidate and its blocker
  - paid review OPTIONAL / DISABLED; order-submission gate DISABLED
  - a table of what stops on sleep, app close and server stop. It claims no startup task and no
    follow-up.
- **Market monitor:**
  - a ticking Eastern-time clock (this computer), the server clock, and the newest live bar end
  - definitions of IEX live coverage vs the delayed SIP comparison
  - table columns for bar start to end, receipt time, receipt delay and data age
  - compact tower labels
- **Session history:**
  - per-symbol on-time (stored within 180 s of bar end), late catch-up, missing live and
    unrecorded worker time, each over the scheduled minutes, with written definitions
  - catch-up is never shown as on-time; on-time + catch-up + missing = scheduled
- **3D labels:**
  - overlapping labels are stacked and kept inside the view
  - the camera is fitted to the window width
  - narrow windows open the monitor on its table, with equivalent fields
- **Fixed while testing:**
  - comparison access refusals during recovery of an earlier session were not counted in that
    session's report (counted by time window); they now come from the session's own run records
  - quality events used the wall clock instead of the checker clock (behaviour-neutral in
    production; made a test depend on the time of day)
- **Verified:**
  - the displayed counts match the stored 2026-11-04 report (79 / 311 / 0; IWM 79 / 310 / 1;
    unrecorded 166 min)
  - labels did not overlap at desktop and 375 px widths (measured from the page), with no
    horizontal scroll
- **Deployment:** the server was restarted after the close to load the backend fields. The worker
  was down 2026-11-05 00:07:30 to 00:07:59 UTC, with the market closed and no live minutes
  affected. The supervisor relaunched it (pid 27136).

## City redesign: architectural district (2026-11-05)

- **Done:**
  - CityView rewritten as a procedural night district: seven building types, instanced scenery,
    plaza, ring road, groves, lamps, fog, sky glow, and bloom on High
  - the Overview gains a district of the project's real components
  - the job, monitor and demo cities use the same renderer
  - status accents, labels, halos and pulses come only from records; architecture is decorative
- **Verified in the browser:**
  - labels: no overlaps at the default camera, after Reset, or at 375 px (measured)
  - selection: the side panel, halo and camera move work; hover works on labels and meshes
  - Low and reduced motion render on demand; the `?3d=off` table fallback works
  - no console errors
  - geometry count stays stable across status polls
- **Performance:** 232 draw calls and 22k triangles; interaction frames 8.4 ms median.
- **Deployment:** frontend-only (static build), so no server restart and no monitoring interruption.
- **Notes:** `docs/CITY.md`.

## City ambient life and real-event effects (2026-11-05)

- **Decorative layer:** traffic, path and entrance lights, fountain, signage, district clock, window
  variation and distant light sweeps; the legend labels it decorative.
- **Real events:** arrival, start/handoff, completion, failure; steady warnings; event ids prevent
  duplicates (verified with synthetic specs in the browser).
- **Worker-floor panels:** real workers only.
- **Effects levels:** Low, Medium (default) and High; reduced motion and the hidden-tab pause respected.
- **Measured:** 254 draw calls on High vs 232 before; frame time unchanged (8.3 ms median).
- **Deployment:** frontend-only; no server restart and no monitoring interruption.

## Dependency-and-health map (2026-11-05)

- **Read-only map:** `trading/dashboard/depmap.py` via `/api/depmap`, shown in the city's new
  Dependencies view.
- **Separate layers:** declared (code/config with file and symbol), recorded (runtime tables with
  timestamps) and proposed (UNIMPLEMENTED_ROLES) connections; Graphify static relations shown apart.
  Statuses come only from records (UNKNOWN when missing).
- **Panel:** "Why blocked?", upstream issues, dependency impact (not proof of failure) and next action.
- **Tests:** 13 fixture tests plus an endpoint test; the synthetic failure view was checked in the
  browser.
- **Deployment:** two server restarts after the close, each about 30 s of worker downtime with the
  market closed:
  - 2026-11-05 01:14:50-01:15:25 UTC
  - 01:20:00-01:20:31 UTC
- **Notes:** `docs/DEPENDENCY_MAP.md`.

## SPY spread-measurement pilot: PROVISIONAL (2026-11-08 to 2026-11-09)

- **Pre-registered:** `feasibility/spread_measurement/PLAN.md`, commit `be2d9cd`, before any request.
  - 6 sessions: the first drawn date of each year, 2016-2021.
  - The quote windows match the closed 001 and 002 entry and exit times.
  - Limits: 600 requests, 75 MB, page caps per window.
  - The other 18 drawn sessions are refused in code, pending a separate owner decision.
- **Implemented and tested:** `trading/spread_measurement.py`, GET only.
  - It enforces the request, page and storage caps, and a gate that requires the committed plan.
  - 19 synthetic tests; the suite passed (330).
- **Run once:** 2026-11-09, 01:22:28 to 01:24:03 UTC.
  - **Completeness:** all 60 date-windows came back complete and measured (coverage at least 97.9%),
    with no cap reached and no access refusal.
  - **Usage:** 135 of 600 requests, 7.87 of 75 MB.
  - **Records:** 1,020,258. 0 invalid, 0 duplicates, 0 out of order. Locked records were 0.37% of
    the time, crossed 0.003%.
  - **Condition code:** every record carries the undocumented code `?`.
- **Provisional result:**
  - The quoted spread was 1 cent for 88-100% of the time in every window.
  - The estimated spread component of execution cost (half-spread, time-averaged) was 0.12-0.25 bp
    per side. The cost model assumes 0.5 bp per side at base.
  - This is not what every order pays: slippage, fees, fills inside the spread and latency are not
    measured.
  - The days are calm-looking, the quote semantics are unverified, and the pilot is a check, not a
    distribution.
- **Records:** `feasibility/spread_measurement/FINDINGS_pilot.md` and `findings_pilot.json`
  (statistics only). Raw quotes are in the git-ignored `data/feasibility/spreads_pilot_20261109T012228Z/`.
- **Unchanged:** `trading/costs.py`, the experiment locks, both closed verdicts, and the gap-down
  block. No validation or final data was requested.

## Automatic session dry run, Milestone 1: implemented (2026-11-09)

- **Owner decisions (2026-11-09):**
  - no order code
  - runtime records in `%LOCALAPPDATA%\TradingProject`
  - manual start, with no scheduled task or background startup
  - five consecutive scheduled sessions must PASS (operation, not profitability)
- **Rules written before any session evidence:** `docs/DRY_RUN_ACCEPTANCE.md`. It defines PASS,
  FAIL, INTERRUPTED and INCOMPLETE; missing evidence is never a pass.
- **Implemented:** `trading/operations/`
  - session clock
  - empty approvals registry (`config/approved_strategies.json`)
  - entry-permission gate (DRY_RUN always denies)
  - kill switch
  - read-only checks (one new GET, `get_clock`)
  - runner
  - records store
  - classification and acceptance
  - CLI
  - the dashboard "Operations" view (`/api/operations`)
- **How to run it:** `docs/OPERATIONS.md`
- **Tested (synthetic):** new tests `test_operations_schedule.py`, `test_operations_gate.py`,
  `test_operations_runner.py` and `test_operations_boundary.py`; the full suite passed (368).
  - **Calendar:** DST, early close, holiday, weekend, late start.
  - **Approvals:** refusal of closed, failed, deferred, unknown, mismatched and multiple strategies.
  - **Runner:** whole simulated sessions for on-time PASS, late start, machine sleep, operator stop,
    same-day restart (no duplicates), broker outage (bounded retries), monitor down, unsafe
    configuration, holiday, and injected violations.
  - **Static checks:** no order code; dashboard-side modules load no broker code.
- **A real test caught a fix:** the runner had hard-coded the monitoring database path. It now uses
  the monitor's own constant.
- **The boundary is now checked by imports and by the data read, not by path strings**
  (`tests/test_operations_boundary.py`):
  - research code imports no monitoring or operations code
  - only `data_health.py` opens the monitoring database (read-only), and it reads only worker
    liveness and the newest bar *time*
  - decisions record health only, never prices
- **Every run records its git commit**, and whether the operations code exactly matched it. The
  session report shows this under `code_version`. A session on uncommitted operations code is
  INCOMPLETE (I5, added before any session evidence).
- **Verified (real, read-only), 2026-11-09 ~21:43 ET:**
  - the `preflight` checks passed: order guard disabled; records outside OneDrive; approvals NONE;
    kill switch off; monitor worker alive; credentials present (names only); broker clock skew
    -1.1 s (tolerance 2 s); calendar agrees; paper account ACTIVE and not blocked
  - `run` on a non-session day exited cleanly
  - the Operations view rendered in the browser with no console errors
- **Not yet verified:** any real market session. The five-session evidence starts with the next
  manual run.

## Market readiness panel and incident history (2026-11-09)

- **Already existed:**
  - worker heartbeat and freshness labels, OS lock (one polling worker), supervisor relaunch
    (6 per hour)
  - `m_workers` run records, amend-only daily evidence reports with live / catch-up / downtime /
    failures / refusals
  - session states, and the 5-consecutive-session checklist in `docs/MONITORING.md`
- **Added:**
  - **`trading/monitor/readiness.py`:** 11 deterministic checks (PASS / WARNING / FAIL /
    UNKNOWN; missing evidence is UNKNOWN).
    - The latest result per check is stored in `readiness`, with checked and changed times.
  - **Incidents:** a persistent, deduplicated incident history (`incidents`), with acknowledge vs
    resolve.
    - "service recovered" is recorded in events.
    - A storage failure seen during a database outage is written once the database works again.
  - **Session reliability:** a summary using **only** the existing criterion.
  - **Server:** `GET /api/monitor/readiness` and `POST /api/monitor/incidents/ack` (same control
    protections). The supervisor records readiness every 60 s.
  - **Start-up:** a second server start detects an existing one and exits instead of duplicating.
  - **City:** a "Market readiness" panel at the top of Market monitor.
  - **Docs:** `docs/MONITORING.md` covers start-up and recovery for browser close, app exit,
    sleep and restart.
- **Found while building:**
  - A venv `python.exe` launcher plus its child interpreter looked like two workers. The check now
    groups process trees.
  - Without this, real readiness would have reported a false duplicate.
- **Tested:** `tests/test_readiness.py`, 12 tests on isolated temporary databases:
  - missing and stale heartbeat
  - duplicate workers
  - refusal and recovery
  - database failure
  - restart with an unfinished session
  - closed and early-close calendar states
  - unmonitored sessions breaking the streak
  - start-up detection
  - API = stored records

  Full suite: 380 passed.
- **Verified with real records (read-only, 2026-11-09 ~23:26 ET):**
  - a separate verification instance (no supervisor, no job runner, port 8767) showed 10 PASS and
    1 WARNING (uncommitted code); 0 incidents
  - API checks = the stored `readiness` table, and the reliability figures = the stored reports
    for 11-04, 11-05 and 11-06
  - desktop and 375 px layouts with no console errors and no page overflow
  - a second `trading.dashboard.server` start against the running server exited 0, leaving one
    listener
- **Reliability under the existing criterion:** 3 of 5 consecutive qualifying sessions
  (11-04, 11-05 and 11-06 FINALIZED).
  - **Gap:** that criterion has no capture-quality threshold, while live on-time capture was only
    79, 130 and 109 of 390 minutes.
  - Owner decision needed; no threshold invented.
- **Not done (approval needed):** restarting the running city server, so it serves the new panel.
- **Fix (2026-11-09, during the session):**
  - **The bug:** `reliability_summary` raised a TypeError on today's in-progress session, whose
    per-symbol "missing" count is unavailable (null). The readiness endpoint dropped the
    connection, and the supervisor logged the error every minute.
  - **The fix:**
    - The aggregates (on-time, late catch-up, missing, outstanding comparisons, anomalies,
      revisions) now return **unknown** (null) when any input is unavailable, never 0.
    - The panel shows "unknown".
    - The endpoint answers HTTP 500 with a JSON UNKNOWN on any evaluation error, instead of
      dropping the connection; the panel shows that as "server responding, evaluation failed".
  - **Tests:** 4 regression tests.
  - **Verified on a separate instance (port 8767, no supervisor, no job runner):** valid JSON; the
    in-progress "missing" count shows as unknown; 375 px layout without overflow; no console
    errors.
- **Observed in real records that day:**
  - The city server and monitoring worker stopped at about 13:00 ET (last heartbeat 18:00:31 UTC),
    with no stop request recorded. The worker was also down 10:24-11:58 ET.
  - The dry-run runner process started at 09:13 ET but recorded nothing: no run, no checks, no
    decisions. It never acquired its single-runner lock, so it stalled before starting.
  - Under the acceptance rules, that day is not a PASS.

## Reporting fixes and reliability diagnosis (2026-11-09 evening)

- **Fixed: request-failure count.**
  - Request failures now come only from explicit request outcomes (live-poll `error` /
    `disconnected` events, and failed comparison runs).
  - Incident, supervisor, crash and quality events are "other errors", by kind.
  - Before: anything not on an exclusion list counted, so incident events were counted as API
    failures.
- **Fixed: stale "pending" wording.** `finalize()` built the report before updating the session
  description, so finalized reports said "comparison … pending". `_state` now derives the wording
  from the computed state.
- **Corrections stored (amend-only):** Nov 5 v2, Nov 6 v2 and Nov 9 v2.
  - Wording corrected on all three; Nov 9's request failures corrected from 2 to 0 (the 2 were
    incident events).
  - Derived from each stored report only; reason recorded in the report and in
    `q_report_corrections`.
  - Versions 1 are unchanged. Nov 4 v2 needed no change.
  - `finalize()` now names its insert columns.
- **Diagnosis from records (no cause asserted beyond the evidence):**
  - **Windows System log:**
    - no sleep or wake events between 08:30 and 18:10 ET
    - an **unexpected shutdown at 15:04:13 ET** (event 6008)
    - a reboot at 17:34:46 ET without a clean shutdown (Kernel-Power 41: crash, hang or power
      loss)
    - **sleep did not cause the gaps**
  - **Outages at 10:24-11:58 and 13:00-15:04 ET:** both happened while Windows was running. The
    city server and the worker ended together: the supervisor's per-minute log stopped, and there
    is no stop request and no Python crash or hang report. **Cause unknown.** Before this fix the
    server recorded no lifecycle evidence.
  - **Dry-run stall:** the process (pid 22352, launched from Windows Terminal at 09:13 ET) stayed
    alive with about 7 s of CPU and 13 threads until the 15:04 crash.
    - It never took its single-runner lock, and wrote no record, so it stopped before or during
      start-up.
    - The module's heavy imports ran before any output, so the step is **unknown**.
    - It was checked whether venv or code files were OneDrive online-only placeholders (a known
      blocking hazard); none were, so that hypothesis is not supported.
- **Fixed / added for visibility:**
  - **Runner start-up:** each step is printed and written to `runner_startup.json` before it runs;
    heavy imports moved after the first step.
  - **Runner files:** `runner.log` (a copy of the output), and `runner_status.json` refreshed every
    15 s by the lock holder.
  - **Watchdog:** a faulthandler watchdog writes stack traces to `runner_faults.log` if start-up
    exceeds 60 s or a loop step exceeds 5 min.
  - **Readiness:** a "Dry-run runner" check reports FAIL "STALLED" with the last step.
  - **Server lifecycle:** `server_runs` records start, last alive (15 s) and clean stop.
- **Start-up:** `python -m trading.startup`, one procedure with OK/WAIT/WARN/FAIL output and
  READY / NOT READY. It reuses healthy processes, never duplicates or kills, and opens missing
  parts in visible windows.
- **Relabelled:** the historical count is now "Report completion" (rule unchanged, 4 of 5).
  - A prospective reliability gate is proposed in `docs/RELIABILITY_GATE_PROPOSAL.md`; not active.
  - The persistent server option is proposed in `docs/OPERATIONS.md`; not installed.
- **Tests:** `tests/test_reliability_fixes.py`, 17 synthetic tests in isolated folders.
- **Note:** the dry-run code changed, so it must be committed before the next run, or that session
  is INCOMPLETE (I5).

## Research desk and evidence trace (2026-11-10)

- **Implemented:**
  - `trading/monitor/evidence_trace.py`: one session through capture inventory, structural validation, IEX/SIP
    comparison, revisions, reliability assessment and the stored-report check. Task records go to
    `data/jobs/desk.sqlite`, one run at a time. Reports are recomputed at their evidence cutoff, and every
    difference is classified.
  - `trading/dashboard/desk.py`: six departments and the Command Centre, served at `/api/desk`.
  - City view "Research desk". See `docs/RESEARCH_DESK.md`.
- **Tested (synthetic fixtures only):** `tests/test_evidence_trace.py` (15) and `tests/test_desk.py` (8). Cases:
  - missing and stale inputs, duplicate requests, upstream failure, invalid output
  - an interrupted run and its recovery, reused versus recomputed results, changed handler source
  - report tampering, the cutoff and later evidence, correction counts
  - API agreement with the stored records
- **Verified on real records (read-only):** traces for 11-04, 11-05, 11-06, 11-09 and 11-10 COMPLETED (11-10 after its
  finalization); a repeat run reused all six results. The monitoring store was not modified. After the controlled restart,
  production on port 8765 serves `/api/desk`, and the page, tables, building labels and API agree.
  - Phone width: no sideways page scroll.
  - Effects play once per recorded event.
- **Report differences, classified:** later evidence and code changes on 11-04 to 11-06; a recorded amendment plus one
  defect (an `other_errors` undercount) on 11-09; 11-10 is identical at its cutoff.
- **Not done:** the reliability gate stays PROPOSED and model assistance DISABLED.
## Dry-run records split by Windows app virtualization; report reproducibility (2026-11-10)

- **Confirmed cause:**
  - Inside the Claude desktop app, `%LOCALAPPDATA%\TradingProject\operations\operations.sqlite` resolves to the app's
    private copy (`Packages\Claude_…\LocalCache`). An operations command run from a Claude terminal on 11-08 created
    that copy.
  - The runner, started outside the app, writes the real file. A reader launched outside the app (read-only) saw
    the real data: the 11-09 run (335 decisions, classified INTERRUPTED: stopped 15:05 ET, no after-close step) and the
    11-10 run (`20261110T145038Z-9496`, about 160 decisions and 615 heartbeats by 17:24 UTC).
  - The city server and Claude Code saw a 45 KB copy frozen on 11-08. So "11-09 INCOMPLETE, no run record" was wrong
    about the reason; 11-09 is INTERRUPTED.
- **Fixed (code; tests on synthetic fixtures):**
  - Operations CLI refuses inside an app container (exit 3).
  - Readiness requires recorded progress, not just liveness, plus a stored report after the close.
  - The operations snapshot reports "records NOT VISIBLE" (the research desk does too).
  - Tests in `tests/test_reliability_fixes.py`: an alive runner without recorded progress stays FAIL for hours, and
    a simulated private copy is detected.
- **Reproducibility:**
  - Reports now record their evidence cutoff, calculation version, code and configuration.
  - `reliability.daily_report(..., as_of=)` recomputes a report at its evidence cutoff. Classifying each difference is
    done in the research-desk evidence trace (`docs/RESEARCH_DESK.md`), committed separately.
  - One defect found: the 11-09 v2 correction dropped 2 reclassified events from `other_errors` (116, should be 118).
    The code is fixed; the v3 correction is previewed, not applied.
- **Note:** operations code changed (`paths.py`, `__main__.py`, `snapshot.py`), so the operations fingerprint changed.
  Dry-run sessions count only on a committed version (I5).
## Milestone status (2026-11-10, after the close)

- **Report completion (monitoring checklist): COMPLETE.** Rule (docs/MONITORING.md, unchanged): 5 consecutive scheduled
  sessions, each FINALIZED or INCOMPLETE with a reason. Evidence: Nov 4, 5, 6, 9, 10, all FINALIZED (`readiness.reliability_summary`:
  5 of 5). It measures report completion, not capture quality.
- **Dry-run acceptance (Milestone 1): 0 of 5.** Rule (docs/DRY_RUN_ACCEPTANCE.md, owner decision 2026-11-09): 5 consecutive
  PASS sessions, one committed operations fingerprint.
  - Nov 9 INTERRUPTED (N1, N3, N5): Windows logged an unexpected shutdown at 15:04:13 ET.
  - Nov 10 INCOMPLETE (I2, I3, N1): the computer booted at 09:49 ET and the runner started at 09:50 ET.
  - Neither is a software fault.
- **Reliability gate G1-G6:** PROPOSED (docs/RELIABILITY_GATE_PROPOSAL.md), not approved, not applied.

## Execution rehearsal lab: LOCAL EXECUTION SIMULATION (2026-11-10)

- **Implemented:** `trading/execution_lab/`, an order-lifecycle rehearsal with a fake in-memory broker and 12
  deterministic synthetic scenarios. Order states, the append-only ledger and the emergency-stop report are derived
  from records.
- **Reused unchanged:** `OWNER_BASELINE_2026_11_03`, `size_position`, `RiskState`, `costs.BASE`.
- **City:** "Execution lab" tab, previewed read-only on port 8770 from `dashboard/web/preview/dist`. The production
  server (8765) and its page are unchanged. See `docs/EXECUTION_LAB.md`.
- **Tested (synthetic only):** `tests/test_execution_lab.py`, 25 tests. All 12 scenarios meet their expectations and
  invariants. Network and project-file guards are in force.
- **Dry run unaffected:** fingerprint `461c31297c5a6c1e`, and no acceptance-critical file changed.
- **Not done:** no broker connection, no order capability, no strategy. The open policy decisions are listed in
  `docs/EXECUTION_LAB.md`.

## Dry-run "no exposure" check made truthful (2026-11-10, owner-authorized correction)

- **Defect:**
  - The 15:55 ET closing check `exposure_none` was recorded as passed without asking the broker. The note read
    "DRY_RUN holds no positions and contains no order code".
  - The session classification ignored closing checks.
  - The runner's description and `docs/OPERATIONS.md` claimed it "confirms no exposure".
- **Correction:** read-only broker evidence covering the paper account identity (host plus a one-way account
  reference), positions, and open orders including partially filled ones, with the observation time.
  - It runs at 08:45, 09:25 (and late start) and 15:55 ET.
  - New reasons for sessions from 2026-11-11: F9 (exposure found), I6 (closing exposure unverified), N4 extended.
  - The client gained three GET-only methods: `get_account_identity`, `get_positions`, `get_open_orders`.
  - Earlier sessions are not relabelled.
- **Tests:** `tests/test_exposure_check.py`, 31 tests on synthetic fixtures, covering:
  - an empty account;
  - a position;
  - open and partially filled orders;
  - the broker unavailable;
  - malformed and incomplete responses;
  - a wrong environment or account;
  - stale evidence;
  - a local assertion plus a fresh heartbeat, which does not pass.
- **Verified (real, read-only):** 2026-11-11 00:21:43 UTC, paper account `df0ca3cbd37a`: VERIFIED_NONE, 0 positions,
  0 open orders.
- **Fingerprint:** before `461c31297c5a6c1e` (no session ran on it); after, see the commit.
  - Acceptance before the correction: 0 of 5 (11-09 INTERRUPTED, 11-10 INCOMPLETE), so no counted session is lost.
  - The count starts with the first session on the committed corrected code.
- **Also identified:** `calendar_agreement` skips comparison within 5 s of the open or close and still counts as
  ok. It is now labelled `compared: false`; its result is unchanged, pending an owner decision.

## Calendar agreement and closing evidence clarified (2026-11-11)

- **Calendar:**
  - My 2026-11-10 note was wrong. The real records hold 26 calendar checks (11-09, 11-10), all compared, none
    skipped; the first periodic check is 30 minutes after the 09:25 final check.
  - A comparison that can't be made (within 5 s of the open or close) is now recorded as not compared and
    **ok=false**, not as agreement. On-time sessions are unaffected.
- **Closing exposure:**
  - The 15:55 ET observation proves no positions and no open orders at its recorded time only. It does not cover
    after the close, or activity between snapshots.
  - The approved Milestone 1 rules require an after-close report, not an after-close account reconciliation (that is
    Milestone 3), so acceptance keeps the 15:55 pre-close observation.
  - An after-close account check would be a new requirement, for the owner to decide.
- **Tests:** four more in `tests/test_exposure_check.py`, synthetic fixtures.
- **Fingerprint:** changed again, from `7625e4a30914ef98`, on which no session has run; see the commit. The count was 0
  of 5.

## Offline execution core completed; paper-test decisions and proposal (2026-11-11)

- **Scope:** OFFLINE SIMULATION ONLY.
  - Fake broker, synthetic instrument SYN, synthetic clock.
  - No network transport exists, and no order exists anywhere.
  - **NO APPROVED ACTIVE STRATEGY.**
- **Verified (offline):**
  - **18 scenarios**, all EXPECTED, with invariants recomputed from the ledger: partial fills, duplicate and
    out-of-order updates, unknown outcomes, reconciliation, cancellation races, restart, emergency stop, manual
    activity, and a live order missing at the broker.
  - **7 fresh-process crash drills**, all passing (`results/execution_lab/crash_drills.json`, git-ignored).
  - **Offline paper-adapter fixture tests.**
- **Fixed (confirmed by probes, then by regression tests):**
  1. A live order the broker had no record of was treated as reconciled, and entries were allowed again. It is now
     an `order_missing_at_broker` discrepancy that blocks entries, and the order is not assumed cancelled.
  2. A cancel request repeated by a fresh process was filed as a duplicate. Request evidence is now numbered from
     the ledger.
  3. An intent orphaned by a crash during the checks stayed CREATED forever. It now expires as never sent, with a
     new crash point and drill.
  4. The dashboard's readiness text named the adapter module, which the boundary test forbids.
- **City (Execution lab):**
  - **Operational board per step:** working, partially filled, uncertain, held legs (not protection) and blocked.
  - **Protection per step:** protected / unprotected / held-inactive, with the time since unprotected.
  - **Evidence links** from an order's history to its ledger event.
  - **A controls table:** ENFORCED (with evidence) vs PROPOSED / UNSET / NOT IMPLEMENTED / NOT CONNECTED.
  - **Verified** in the read-only preview on port 8770, using a preview build only. Production's `dist` and
    production server are unchanged.
- **Documents:**
  - `docs/PAPER_TEST_DECISION_SHEET.md`: six minimum decisions, nothing approved.
  - `docs/PAPER_TEST_PLAN_DRAFT.md`: corrected stale statements, a control-status table (7 rows block a first
    order), and an exact unexecuted session script with stop conditions and final account checks.
- **Dry-run fingerprint:** `6cc6999855edd4f1` measured before and after; unchanged; commit `1ed518e`.
- **Missing or blocked:**
  - the paper network transport (not built; needs authorization)
  - the kill switch, NOT CONNECTED to the execution core
  - the test-loss limit, NOT DEFINED
  - all 11 execution-policy fields UNSET
  - the intended account and written authorization, absent
  - Milestone 1 acceptance not met

## Milestone 1 acceptance record and version freeze (2026-11-11, after the close)

- **Authoritative acceptance output.**
  - Run by the owner in a normal PowerShell window with `python -m trading.operations acceptance`; output reported in
    chat on 2026-11-11.
  - **Result:** 2026-11-11 = **PASS**; `current_streak` = **1**; `accepted` = **false**; fingerprint
    `6cc6999855edd4f1`.
  - It agrees with the stored report `reports/2026-11-11.json`: PASS, 385 of 385 decision minutes, broker-verified
    no exposure, code commit `34cd713`. 2026-11-10 stays INCOMPLETE, as recorded.
  - No rule, threshold or historical result was changed to record this.
- **Version frozen for the remaining sessions.**
  - The dry run runs operations fingerprint `6cc6999855edd4f1` (commit `34cd713`) for the four sessions still
    needed: 2026-11-12, 11-13, 11-16 and 11-17. All four must PASS.
  - No change to the fingerprinted files (`trading/operations/*.py`, `config/approved_strategies.json`,
    `trading/sessions.py`, `trading/safety.py`, `trading/alpaca_client.py`) until Milestone 1 is accepted, or the
    owner decides otherwise. Any change would restart the count.
  - Work elsewhere (the execution lab, the paper adapter, docs) does not touch the fingerprint; re-measure it before
    each session rather than assuming it.
- **Also recorded today:**
  - **Intended paper account:** `config/intended_paper_account.json` holds account reference `df0ca3cbd37a`, confirmed
    by the owner at 2026-11-12T01:30:27Z (the account ending 4KLR). This is **identification only**: no policy, no
    write networking, no orders.
  - **Monitor worker:** one worker. PID 15180 is the venv launcher, and PID 9680 is its child interpreter running
    `trading.monitor run`.
  - **City server (8765):** down. The owner restarts it with `python -m trading.startup` in a normal PowerShell
    window (`docs/OPERATIONS.md`, "Recovering the production city server").
- **Still blocked:**
  - every execution-policy value (UNSET);
  - the paper network transport (not built);
  - order submission (guard refuses);
  - paper-test limits (owner choices);
  - written authorization (absent).

## Missing (written 2026-11-03)

**[SUPERSEDED: see the current-status summary at the top. Alpaca access is verified, real
development data is stored, and the owner's risk limits are enforced in the simulation engine.
Only the Playwright line still holds.]**

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
