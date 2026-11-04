# Strategy City dashboard: DEMO REPLAY

A local browser dashboard that replays **synthetic data and simulated outcomes**.
It is not market data, not a backtest of real prices, and not broker results.
Order submission is disabled; the server contains no broker or order code.

## Launch

```powershell
# one-time: build the browser app (needs Node.js 20.19+)
cd dashboard\web
npm install
npm run build
cd ..\..

# start the local server (binds to 127.0.0.1 only)
.venv\Scripts\python -m trading.dashboard.server
# open http://127.0.0.1:8765
```

HISTORICAL REPLAY (needs Alpaca paper keys in `.env`; fetches read-only and stores
data under the git-ignored `data/history/`):

```powershell
.venv\Scripts\python -m trading.verify_data_access
.venv\Scripts\python -m trading.history --symbol SPY --feed sip --start 2016-01-04 --end 2016-06-30
.venv\Scripts\python -m trading.dashboard.server --mode historical
```

- Replay sessions come from `dashboard/historical_config.json`.
- Only development-period sessions are allowed by default; the final period is
  never replayable here.
- Without stored data the server refuses to start; it never falls back to demo.

Options:
- `--speed 1800` sets the starting replay speed.
- `--port 8766` uses a different port.
- `--config dashboard/empty_config.json` shows the empty state.
- Add `?3d=off` to the URL to skip WebGL and show the table view.

For frontend development with hot reload, run the server as above, then
`npm run dev` in `dashboard/web`. Vite proxies `/api` to the Python server.

## Architecture

```
trading/fixtures/synthetic.py   made-up bars on real NYSE dates
trading/backtest.py             existing experiment-001 engine (unchanged)
trading/dashboard/demo_replay.py   runs each configured instance through the engine and
                                   turns bars, signals, decisions, simulated fills, closed
                                   positions, risk blocks and data gaps into Events
trading/events.py               event schema v1
trading/dashboard/ledger.py     idempotent projection: account, strategies, sessions, leaderboard
trading/dashboard/server.py     replay clock, controls, server-sent events, static files
dashboard/web/                  React + TypeScript + Three.js; displays ledger output only
```

Every event has `event_id`, `ts_utc`, `source`, `mode`, `type`, `strategy_id`,
`instrument` and `payload`. The browser never computes P&L or risk:

- **Realized P&L** comes only from `position_closed` events, net of simulated costs.
- **Unrealized P&L** is the ledger's mark at the latest bar close against the
  entry fill, before exit costs.
- **Duplicates** are ignored by `event_id`, in both the ledger and the browser.
  The server deliberately resends an earlier event every
  `replay.duplicate_every` events to exercise this.
- **Mode mismatch:** events whose `mode` differs from the server's are rejected
  and counted, never mixed in.

Each tower has six tabs:
- Rules & version
- Scanner & news
- Historical replay
- Results
- Paper account
- Decisions & risk

Results come from `GET /api/strategies/<id>/evaluation`, which is built from
the same ledger records as the city. Mode availability comes from
`GET /api/research`. See `docs/PRODUCT_SPEC.md`.

Towers are configured in `dashboard/demo_config.json` (instruments, instances,
parameters, per-instance risk overrides). Adding an instance needs no code
change, and no AI agents or model calls are involved.

## Research jobs tab (REAL records, not demo)

The "Research jobs" tab is a control panel for `trading/jobs.py`. It reads saved artifacts of
the closed experiments 001 and 002 and never re-runs a trading evaluation or fetches data.
Job towers are teal cylinders tagged REAL JOB, unlike the purple DEMO strategy boxes. A Table
view shows the same records and controls.

Endpoints (localhost only):

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/experiments` | allowlisted experiments, artifact inventory |
| GET | `/api/pipelines/preview?experiment=` | what starting would do |
| POST | `/api/pipelines` | body `{experiment}`. 201 = created; 200 = already active, nothing new |
| POST | `/api/pipelines/<id>/cancel` | body `{}`. Returns `cancelled`, `cancel_requested` or `already <status>` |
| GET | `/api/reports/<id>` | report of a completed pipeline only |

Every POST must have:
- the header `X-Dashboard-Control: 1`
- `Content-Type: application/json`
- a same-origin `Origin` / `Sec-Fetch-Site`
- a Host of `127.0.0.1:<port>` or `localhost:<port>`

CLI equivalents: `python -m trading.jobs run --experiment ...`, `list`, `cancel <pipeline_id>`.

## Verification

```powershell
.venv\Scripts\python -m pytest -q tests\test_dashboard.py   # backend: totals, dedupe, records, states
cd dashboard\web; npm run typecheck; npm run build          # frontend types and build
```

## Connecting real Alpaca data (separate, not started)

Prerequisite: Alpaca paper keys in `.env`, and a successful
`python -m trading.verify_data_access`. That has not happened yet.

1. **Explicit mode switch.** Add a `--mode paper-data` server flag with its own
   mode value and banner.
   - If credentials or data are missing, the server refuses to start; it never
     falls back to demo.
   - The browser already rejects events from a mode it wasn't started in.
2. **Historical bars adapter.** Turn `ReadOnlyAlpacaClient.get_bars` (already
   paginated) into `bar` events. Record the feed (iex/sip), adjustment and
   retrieval time, and run `trading/validate.py` checks before emitting.
3. **Live stream adapter.** Use Alpaca's market-data WebSocket (check the current
   docs first; the free plan is IEX-only in real time). It needs:
   - wall-clock staleness detection
   - reconnect with backoff
   - `feed_status` events for disconnects
4. **Incremental strategy step.** The engine is batch-only today. A step function
   that consumes one bar at a time must reproduce `run_backtest` exactly on the
   same bars, which is testable.
5. **Read-only paper account panel.** Show `GET /v2/account` and `/v2/positions`
   as a separate "broker paper account" section, kept apart from the strategy
   simulation, plus reconciliation checks.
6. **Secrets.** Keys stay in the server process, loaded from `.env`. Add tests that
   keys never appear in API responses, server-sent events, logs or the bundle.
7. **Orders stay disabled.** Paper order submission is a later milestone needing
   explicit approval and its own failure, duplicate-order and reconciliation tests.
