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

## Dashboard (DEMO REPLAY)

- See `dashboard/README.md`. Launch: build `dashboard/web` (`npm install && npm run build`),
  then `.venv\Scripts\python -m trading.dashboard.server` and open http://127.0.0.1:8765.
- Mode is DEMO_REPLAY: synthetic fixtures, simulated outcomes. Keep the banner and
  "simulated" labels; never present replay results as backtests or broker results.
- The browser displays ledger output only (`trading/dashboard/ledger.py`); P&L and risk
  logic stay in Python. The server must not import broker code or load credentials.
- Any real-data mode must be an explicit, separately labeled mode; never fall back silently.
- Historical data: `python -m trading.history` (read-only fetch into `data/history/`, with
  manifest provenance), then `python -m trading.dashboard.server --mode historical`.
  The dashboard replays development-period sessions only unless the owner decides otherwise.
- One inspectable research run (replay + journal + evaluation, outputs in git-ignored
  `results/research/`): `python -m trading.research_run --mode historical` (or `--mode demo`).
  Historical runs append to `research/001_intraday_momentum/inspection_runs.csv`.
- Product spec, modes, outcome rules and milestone checklist: `docs/PRODUCT_SPEC.md`.
  Don't implement scenario simulation until the owner approves its section 8.

## Market monitoring (read-only)

- `trading/monitor/` (see `docs/MONITORING.md`). The worker is a separate process; only it loads
  Alpaca credentials. The city server reads `data/monitoring/monitor.sqlite` and launches or
  supervises the worker, but never imports broker code.
- Daily evidence reports (`trading/monitor/reliability.py`): keep live capture, later IEX revisions and delayed SIP
  separate; never write re-fetched bars into the live record; finalization is amend-only.
- Data quality (`trading/monitor/quality.py`): compare only minutes whose end is >= 20 min old (15 min SIP
  delay + 5 min margin); keep every observation revision; never certify a feed or derive signals.
- Never request or store dates on or before the end of the reserved periods (2026-10-30). Never
  switch feeds silently. No signals or recommendations from monitoring data; it is not a research
  dataset.

## Automatic session dry run (Milestone 1, read-only)

- `trading/operations/` (see `docs/OPERATIONS.md`, `docs/DRY_RUN_ACCEPTANCE.md`, `docs/AUTO_TRADING_ROADMAP.md`).
  Environment DRY_RUN only: the gate always denies entries. The package must never contain or import order code
  (a static test enforces it). `config/approved_strategies.json` stays empty unless the owner edits it.
- Runtime records live in `%LOCALAPPDATA%\TradingProject\operations` (never OneDrive or the project). Started manually
  by the owner; never install a scheduled task or background startup without a new owner decision.
- Session classification rules are fixed in `docs/DRY_RUN_ACCEPTANCE.md`; missing evidence is never a pass. Changing
  the operations code restarts the five-session count (code fingerprint).
- Start operations, the runner and the city server from a normal PowerShell window, never from a Claude desktop terminal:
  inside a packaged app Windows redirects `%LOCALAPPDATA%` to a private copy (see `docs/OPERATIONS.md`). The operations CLI
  refuses there. A live runner process is not progress: readiness needs its run in the records.
- Daily start: `python -m trading.startup` (reuses healthy processes; never kills or restarts). Monitoring report
  corrections are amend-only (`python -m trading.monitor correct-reports`); never edit stored report versions.

## Model reviewer (automated second review)

- Status: OPTIONAL / DISABLED. The owner revoked paid calls on 2026-11-04; do not re-enable them without a new
  explicit owner authorization.
- `trading/reviewer/` (see `docs/MODEL_REVIEW.md`). It is a second opinion; deterministic checks
  stay the authority and a contradicting review is rejected.
- Never make a paid model call without the owner's explicit approval of provider, model and budget.
  Never write `research/MODEL_REVIEW_AUTHORIZATION.json` for the owner. Never ask for API keys in chat.
- Keep the review UNAVAILABLE until `python -m trading.reviewer verify ... --i-authorize-one-paid-call`
  has succeeded with a real provider. Mock results never count as verification.
- Never repeat a billable call after an uncertain or failed outcome without an acknowledgement.
- Paid calls only from the command line (`trading.jobs run`, `trading.reviewer verify`). The dashboard
  server never loads API keys (`review.server_env()` strips them); browser runs use cached reviews only.

## Experiments

- Spec first, code second: `research/<id>/SPEC.md` is approved by the owner before coding.
- `trading/experiment.py` enforces the period lock and variant budget. Never bypass it,
  never run the final period without explicit owner approval, and never edit
  `research/*/variants.csv` except by appending through the runner.
- Risk values in `trading/risk.py` are placeholders until the owner sets them (SPEC D1).
- Experiment lock: `research/001_intraday_momentum/EXPERIMENT_LOCK.json`
  (`python -m trading.experiment_lock` checks it).
  - Any change to the spec file, costs, periods, budget, pass rules or risk limits breaks the
    lock. Record it with `--supersede "reason"`, never by editing the lock.
  - Every evaluation attempt is logged in `experiment_attempts.csv`.

## Dependency map (read-only)

- `trading/dashboard/depmap.py` (`/api/depmap`, city "Dependencies" view). Declared, recorded and proposed connections stay
  separate; statuses come only from runtime records (UNKNOWN when missing); Graphify relations are code evidence only.
  Never add a trading or execution node; never let it start or change anything.

## Research candidates (not experiments)

- `research/candidates/<id>/STATUS.json`, shown read-only in the city's research jobs view; no pipeline runs on them.
- `gap_down_opening`: DEFERRED_DATA_SEMANTICS (not failed, never evaluated). Downloads are blocked in
  `trading/execution_feasibility.py`. Resuming needs written answers to
  `feasibility/execution_data/ALPACA_SUPPORT_REQUEST_DRAFT.md` and a new owner decision. Never send that draft yourself.

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
