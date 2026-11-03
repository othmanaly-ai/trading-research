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

Towers are configured in `dashboard/demo_config.json` (instruments, instances,
parameters, per-instance risk overrides). Adding an instance needs no code
change, and no AI agents or model calls are involved.

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
