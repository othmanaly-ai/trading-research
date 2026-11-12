# Automatic market-session operation: audit and roadmap

**Status:**
- **Written** 2026-11-09 from an inspection of the code, records and running processes.
- **Update 2026-11-09:** the owner approved Milestone 1 (decisions: records in
  `%LOCALAPPDATA%\TradingProject`, manual start, five consecutive sessions).
  - **Implemented and tested with synthetic fixtures:** `trading/operations/`
  - **How to run it:** `docs/OPERATIONS.md`
  - **Pass/fail rules:** `docs/DRY_RUN_ACCEPTANCE.md`
  - **Real-session evidence:** not yet collected.
- **Everything below Milestone 1 is a plan only.**
- No order path exists, order submission is disabled, and no strategy is approved.
- Nothing here is evidence that any strategy is profitable.

**Status words used below (never mixed):**
1. **Proposed:** written down only.
2. **Implemented:** code exists.
3. **Tested (synthetic):** offline tests with labelled fake data pass.
4. **Verified (real):** exercised against Alpaca or real market data, with the result recorded.
5. **Running:** a process is alive now and its records show it healthy.

---

## A. Goal and present blockers (plain English)

**The goal:** a program (operated and explained by "JARVIS") that, on every trading day:
1. starts before the open
2. checks that data, broker, records and risk state are healthy
3. looks for opportunities **only with a strategy you have approved**
4. manages trades within your risk limits
5. reports what happened, including "no trade today, and why"

Starting automatically must never mean trading automatically: most days, the correct output may be
"no trade".

**Why it cannot trade today, in order of importance:**

| # | Blocker | What it means |
|---|---|---|
| 1 | **No qualified strategy.** | Experiments 001 and 002 failed development and are closed. The gap-down candidate is deferred. There is nothing the system would be allowed to trade, and automation cannot fix that. |
| 2 | **No execution layer.** | The broker client can only read (HTTP GET). No order lifecycle, broker reconciliation or kill switch exists. |
| 3 | **Costs are partly unknown.** | The spread pilot suggests the spread component of SPY's cost is smaller than modelled, but it is provisional (unknown quote semantics, calm days only). Slippage and fills are unmeasured. |
| 4 | **Data for execution is unproven.** | The verified real-time feed is IEX: one exchange, about 1.5-4% of volume. Real-time consolidated (SIP) data is refused on the current free plan. Monitoring has never captured a full session live, unattended. |
| 5 | **Operation depends on an open desktop app.** | The monitoring worker runs only while the dashboard server runs. There is no scheduled start, and risk state (drawdown halt) lives in memory, so it would be lost on restart. |

**So the plan has two tracks:**
- **Track A** (research) decides whether anything ever becomes tradable.
- **Track B** (operations) builds the automatic, **order-incapable** machinery now, so that if
  Track A ever succeeds, the operating side is already proven.

---

## B. Evidence table

| Capability | Existing code / evidence | Verified status (as of 2026-11-09) | Missing work |
|---|---|---|---|
| Exchange calendar, DST, early closes | `trading/sessions.py` (XNYS, `America/New_York`); monitoring calendar logic in `trading/monitor/worker.py` | Tested (synthetic: holidays, early close, DST in `tests/test_sessions.py`); verified (real) in monitoring | Session **phases** (pre-open, entry window, close, report), late-start rules |
| Read-only broker / data client | `trading/alpaca_client.py`: GET only; hosts limited to paper and data; no order methods (`tests/test_alpaca_client.py::test_client_has_no_order_methods`) | Verified (real): account read, SIP history, IEX real-time, delayed SIP, quotes (2026-11-03 to 11-09) | Read-only position/order queries for reconciliation (GET, later) |
| Order-submission guard | `trading/safety.py`: blocks unless `TRADING_MODE=paper` and `ORDER_SUBMISSION_ENABLED=true` | Tested; checked 2026-11-09: `TRADING_MODE=paper`, `ORDER_SUBMISSION_ENABLED=false`, guard reports disabled. **No code calls it yet, because no order code exists.** | An execution module that must call it (Milestone 3 only) |
| Credentials handling | `load_credentials()`: environment first, then `.env`. Checked by name only: Alpaca key names are set as environment variables; none in `.env` | Verified (real) by the successful reads | Pre-open check that keys are present and accepted, without printing them |
| Live market data | `trading/monitor/worker.py`: IEX 1-minute bars for SPY/QQQ/IWM, polling every 60 s; freshness labels; backoff; never switches feed | Verified (real) on 2026-11-04 to 11-06. **Running:** worker pid 3496 alive, state `market_closed`, but only because this session's dashboard server is running. | Feed suitability rules for decisions (not just freshness); a run that does not depend on the dashboard |
| Data-quality comparison | `trading/monitor/quality.py`, `reliability.py`: delayed SIP vs IEX, revisions kept, amend-only daily reports | Verified (real): reports finalized for 2026-11-04, 11-05 and 11-06 | Feeding quality results into entry permission (currently forbidden by design: "never derive signals") |
| Monitoring continuity | Supervisor thread in the dashboard (`trading/monitor/control.py`); OS lock (one worker); 6 launches per hour | Verified (real) crash recovery. **But stored live bars per symbol:** about 390 on 11-04 (much by catch-up), 130 on 11-05, 118 on 11-06. The worker ran only while the app was open. | An independent session runner; scheduled start; sleep handling |
| Strategy registry | `trading/strategies/registry.py`: spec path plus spec hash for 001 and 002 | Tested | An **approval** registry. Today nothing distinguishes "registered for research" from "approved to trade" except the experiments' `STATUS.json` (both CLOSED) |
| Strategy closure guards | `trading/experiment.py` / `orb_experiment.py` refuse closed experiments; `STATUS.json` CLOSED for 001 and 002 | Tested | The operations layer must refuse closed, failed, deferred or mismatched strategies itself |
| Risk sizing and limits | `trading/risk.py`: `size_position`, `RiskState`, `OWNER_BASELINE_2026_11_03` | Tested; used in real-data simulations (001, 002) | Persistent state, broker-based equity, partial fills, manual positions (section F, risk mapping) |
| Simulation engine | `trading/engine.py` (`SessionStrategy`, `execute_plan`), `trading/backtest.py` | Tested; verified on real development data | A forward (live-bar) adapter for shadow decisions (Milestone 2) |
| Cost model | `trading/costs.py` (base 2.3 bp, stress 6.6, severe 9.6 round trip) | Implemented. The spread component is provisionally conservative (`feasibility/spread_measurement/FINDINGS_pilot.md`). Slippage and fees are unmeasured. | Measured slippage, which needs real-money fills. Paper fills are simulated and cannot establish it (corrected 2026-11-11: paper fills test order handling and Alpaca's simulated execution; they cannot establish real-world slippage) |
| Event records and ledger | `trading/events.py` (modes DEMO_REPLAY, HISTORICAL_REPLAY); `trading/dashboard/ledger.py`; `trading/journal.py` | Tested; verified on demo and historical data | An operations record store with DRY_RUN / SHADOW / PAPER modes and source/receipt/decision/submit/fill timestamps |
| Dashboard | `trading/dashboard/server.py` (127.0.0.1 only; no broker code; no credentials); real-record views; depmap | Verified in the browser. **Running:** a listener on 127.0.0.1:8765 (this session) | An "Operations" table view: mode, approved strategy, feed, freshness, reconciliation, entry permission and reasons |
| Dependency map | `trading/dashboard/depmap.py`, `docs/DEPENDENCY_MAP.md`; "no execution path" by rule | Tested | Operations nodes (runner, gate), still with no execution node until Milestone 3 |
| Research jobs | `trading/jobs.py` | Tested; verified (real) reconcile of 001 and 002 | Not needed for operations |
| Model reviewer | `trading/reviewer/` | OPTIONAL / DISABLED; paid calls revoked 2026-11-04; never verified with a real provider | Not needed; must never gate trading |
| Scheduling / unattended start | None. `schtasks` shows no project task; `docs/MONITORING.md`: "There is no Windows startup task" | **Not implemented** | Session runner plus (later, approved) Task Scheduler entry |
| Kill switch | None for entries. A drawdown "kill switch" exists only inside a simulation (`RiskState.halted`) | **Not implemented** | Entry-blocking switch independent of JARVIS (file plus CLI plus dashboard) |
| Order lifecycle, reconciliation | None | **Not implemented** (correct for now) | Milestone 3 |
| JARVIS | No JARVIS code (repository search finds none) | **Not implemented** | Read-only assistant role (section F) |
| Notifications / calls | None | **Not implemented** | Optional outputs only |

**Stale documents found:**
- **`docs/PRODUCT_SPEC.md`:** sections 2 and 9 still say historical replay and paper-account
  access are "blocked: access unverified". Access was verified on 2026-11-03, and replay ran on
  real development data on 2026-11-04.
- **`PROGRESS.md`:** its uncommitted status summary already marks such statements as superseded.
- **This file:** its evidence above uses the newer, dated records.

**Risk baseline, verified against code:**
- `OWNER_BASELINE_2026_11_03` in `trading/risk.py` matches the owner decision recorded in
  `PROGRESS.md` (2026-11-03): 0.10% risk per trade including modelled costs, 0.50% daily, 3%
  drawdown, 5% notional, 10% gross, 2 positions, `placeholder=False`.
- The $100,000 is a **simulation start** (`trading/experiment.py` `start_equity`,
  `orb_experiment.py` `START_EQUITY`), not a real allocation.
- **Two things the user-facing list does not show:**
  - (a) the baseline also sets `participation=0.01` (at most 1% of median 1-minute volume)
  - (b) "no leverage" is not a separate check: it follows from the 10% gross cap in simulation,
    while the paper account itself reports 4x intraday buying power
- The `RiskLimits` class defaults (0.5% risk, 1% daily, 5% drawdown, 100% notional) are
  placeholders (`placeholder=True`) and must never be used.

---

## C. Architecture

```
                  ┌─────────────────────────────────────────────────────────────┐
 Windows Task     │ SESSION RUNNER (one process per trading day; no LLM inside) │
 Scheduler ──────►│  1 calendar & phase clock (XNYS, ET)                        │
 (later, approved)│  2 pre-open checks ──► entry permission = AND of all gates  │
                  └──────┬─────────────┬──────────────┬───────────────┬─────────┘
                         │             │              │               │
          ┌──────────────▼──┐  ┌───────▼────────┐ ┌───▼──────────┐ ┌──▼───────────────┐
          │ MARKET DATA     │  │ APPROVED       │ │ RISK GATE    │ │ KILL SWITCH      │
          │ monitor worker  │  │ STRATEGY       │ │ risk.py +    │ │ file + CLI +     │
          │ (IEX, labelled) │  │ approvals file │ │ persisted    │ │ dashboard button │
          │ + suitability   │  │ + fingerprint  │ │ RiskState    │ │ (blocks entries) │
          └──────────────┬──┘  └───────┬────────┘ └───┬──────────┘ └──┬───────────────┘
                         └──────┬──────┴──────────────┴───────────────┘
                                ▼
                  ┌───────────────────────────────┐   M1/M2: this box does not exist.
                  │ EXECUTION BOUNDARY (M3 only)  │   M3: separate module, paper host
                  │ require_order_submission_     │   only, persistent order intents,
                  │ allowed() ► intent ► submit   │   unique client order ids
                  └──────────────┬────────────────┘
                                 ▼
                  ┌───────────────────────────────┐
                  │ BROKER RECONCILIATION (GET)   │◄── read-only client (unchanged)
                  │ orders, positions, account    │    mismatch ► block new entries
                  └──────────────┬────────────────┘
                                 ▼
   ┌────────────────────────────────────────────────────────────────────────────┐
   │ RECORDS (SQLite, append-only): runs, config fingerprints, checks, data     │
   │ health, decisions incl. "no trade" reasons, risk checks, intents, broker   │
   │ responses, fills, reconciliations, end-of-day reports                      │
   └───────────────┬───────────────────────────────────────────┬────────────────┘
                   ▼                                           ▼
        ┌────────────────────────┐                ┌─────────────────────────────┐
        │ DASHBOARD (read-only)  │                │ JARVIS (read-only)          │
        │ Operations table view; │                │ explains, summarizes,       │
        │ no broker code, no keys│                │ proposes; cannot call the   │
        └────────────────────────┘                │ runner, gate or execution;  │
                                                  │ notifications optional      │
                                                  └─────────────────────────────┘
```

**Key separations:**
- **Deterministic code decides.** JARVIS only reads records.
- **The dashboard never holds credentials.** Only the worker and the runner do.
- **The execution box is absent** until Milestone 3 is separately authorized.

---

## D. Operating-state model

**Environments.** Every record and screen carries exactly one environment label.

| Environment | Orders possible? | Exists today? |
|---|---|---|
| DEMO | No (synthetic) | Yes |
| HISTORICAL_REPLAY | No (stored bars) | Yes |
| DRY_RUN (M1) | **No: no order code is importable** | No |
| SHADOW (M2) | No: "would-have" decisions with modelled fills | No |
| PAPER (M3) | Paper host only, behind the guard and an approval | No |
| LIVE | **Not defined anywhere.** Adding it needs a separate future proposal | No |

**Session phases** (times are for a regular day; early closes shift the close-relative phases):

```
OFF ─(scheduled start, trading day)─► PRE_OPEN_CHECKS (from ~08:45 ET)
      │                                   │ any check fails ─► ENTRIES_BLOCKED(reasons) ─┐
      │ not a trading day ─► NO_SESSION   ▼                                              │
      │  (record, exit)               WAITING (until the strategy's entry window)        │
      │                                   ▼                                              │
      │                               ENTRY_WINDOW (entries allowed only if the gate     │
      │                                   │          passes at each decision)            │
      │                                   ▼                                              │
      │                               MANAGE_ONLY (after cutoff, or any block: no new    │
      │                                   │          entries, manage existing exposure) ◄┘
      │                                   ▼
      │                               CLOSING (flat-by-close procedure, if any exposure)
      │                                   ▼
      └──────────────────────────────► AFTER_CLOSE_REPORT ─► DONE
```

**Entry permission** is evaluated at every decision point. It is the AND of:
1. the environment allows entries (DRY_RUN and SHADOW never do)
2. exactly one strategy version is approved, unrevoked, and its fingerprint matches
3. the phase is ENTRY_WINDOW and the decision time is not in the past (no late replays)
4. the data is suitable (section F, data rules)
5. the risk state allows (not halted, not daily-blocked, capacity available, including pending
   orders)
6. the broker is reconciled (PAPER only) with no unknown order outcomes
7. the kill switch is off
8. the clock is within tolerance, and disk and records are writable

Every denial is recorded with all failing reasons. **"No trade today" is a normal, recorded
outcome.**

**Overlay states and how they clear:**

| State | Set by | Clears by |
|---|---|---|
| ENTRIES_BLOCKED (data, clock, disk, reconciliation) | automatic check | automatic, when the condition passes again **and** the phase still permits entries; never back-fills missed decisions |
| DAILY_LOSS_BLOCKED | risk gate | the next session start (automatic); persisted across restarts |
| DRAWDOWN_HALTED | risk gate | **owner only** (manual reset with a written reason) |
| KILL_SWITCH_ON | owner, or an automatic severe fault | **owner only** |
| RECONCILE_REQUIRED (unknown order outcome, mismatch) | reconciliation | automatic, when broker and local records agree; **owner** if a manual change is detected |
| STRATEGY_REVOKED / MISMATCH | approvals file or fingerprint | owner re-approval |

**Monitoring recovery is not permission to trade.** A restarted worker may resume collecting data
automatically. A restarted runner always re-runs the pre-open checks, then reconciliation, before
entries can be considered. Halts, kill switches and owner-only blocks survive restarts.

**Late start or missed session:**
- If the runner starts after a strategy's decision time, that decision is recorded as
  `missed: started late` and **never executed**.
- A missed session produces a NO_SESSION_RECORD ("not run"), never a retroactive decision.
- Existing exposure found at a late start goes to MANAGE_ONLY after reconciliation.

---

## E. Failure-response matrix

"Entries" means new positions. "Exposure" means existing positions and pending orders.

| Failure | Detection | New entries | Open exposure | Automatic recovery when | Owner needed when |
|---|---|---|---|---|---|
| Missing / invalid credentials | key names absent; 401/403 on the account read | Blocked | PAPER: cannot reconcile, so RECONCILE_REQUIRED and the owner is alerted. Exposure stays under the broker-side stop orders placed at entry (M3 design) | keys present and a read accepted | always for invalid keys (keys are never handled by code or chat) |
| Broker outage | non-200 / timeouts on paper reads | Blocked | as above; no blind actions | reads succeed and reconcile clean | outage outlasts the entry window with exposure open |
| Data-provider outage | poll failures; backoff state in the monitor store | Blocked | manage via broker-side stops; **no exits based on stale data** | fresh, suitable data resumes | prolonged, with exposure |
| Stale feed | newest bar end older than the threshold (source time) | Blocked | as above | freshness passes for N consecutive minutes (decision) | no |
| Rate limiting (429) | HTTP 429 | Blocked while data is stale | unchanged | the bounded backoff succeeds | repeated daily: plan or polling change |
| Local disk full | free-space check before the session and hourly; write failure | Blocked (no record means no action) | PAPER: existing broker stops remain; no new orders | space restored and a write test passes | yes |
| Database unavailable / locked | SQLite error or busy timeout | Blocked | as above | a write succeeds; **OneDrive lock is suspected first** | if repeated |
| Process crash | heartbeat gap; supervisor or scheduler sees exit | Blocked until restart | broker-side stops only | restart: pre-open checks, then reconcile, then MANAGE_ONLY or ENTRY_WINDOW | crash loop (launch limit reached) |
| Machine sleep / restart | heartbeat gap; wall-clock jump; uptime | Blocked | as above | the same as a crash; missed decisions recorded, never replayed | if it happened during the session with exposure |
| Clock discrepancy | local UTC vs the broker/HTTP `Date` header beyond tolerance (decision; proposed 2 s) | Blocked | unchanged | within tolerance | persistent: Windows time sync |
| Submission timeout (M3) | no response within the timeout | Blocked | the order is **UNKNOWN**, counted as live exposure | a GET by client order id resolves it | unresolved after N attempts |
| Duplicate event | identical key (bar key, broker event id, client order id) | No effect | no effect | ignored and counted | conflicting duplicates: a structural defect, data blocked |
| Broker/local position mismatch | reconciliation diff | Blocked | **no automatic correction**; manual changes flagged | records agree again | always if unexplained or manual |
| Daily loss breach | the risk gate at each mark | Blocked for the rest of the session | **policy decision needed** (hold under stops, or flatten); not assumed | the next session | the policy choice itself |
| Drawdown breach | the risk gate | Halted | the same policy decision | **never automatic** | yes (reset with reason) |
| Market halt | no bars across feeds, or a halt status if available; calendar is still open | Blocked | cannot trade during a halt; a stop may fill far away after it | trading resumes **and** data freshness passes | no, unless exposure is affected |
| Notification failure | send error recorded | **No effect** | no effect | the next send | never: notifications are optional |

**Why a stop order is not a maximum-loss guarantee:**
- A stop becomes a market order once triggered. It fills at the next available price, which can be
  far beyond the stop after a gap, a halt or a fast market.
- It can fail to exist at all if submission or reconciliation failed.
- The 0.10% planned risk is a plan under modelled fills, not a cap on actual loss. The engine
  already models gap-through fills.

---

## F. Prioritized milestone plan

### Track A: how a strategy becomes eligible (research; runs in parallel)

1. **Hypothesis and versioned rules first:** a `research/<id>/SPEC.md`, approved by you before
   code, as for 001 and 002.
2. **Data that fits the strategy:**
   - Its timing: minute bars, or quotes for spread-sensitive entries.
   - Its liquidity: participation caps.
   - Its execution assumptions: the decision-to-fill delay.
   - If decisions need consolidated real-time prices, IEX is not enough (section I).
3. **A documented cost model:**
   - The spread component may be informed by the pilot only after the quote questions are answered.
   - Slippage stays an explicit assumption until fills exist.
4. **Acceptance rules fixed before evaluation**, with a lock file, as already enforced by
   `trading/experiment.py` and `experiment_lock.py`.
5. **Periods:**
   - Development is used for building.
   - Validation and final are held out (never retrieved so far).
   - **Development data is already contaminated** for late-day, morning-range/breakout and "buy
     after down mornings" ideas (`research/EXPLORATION_LOG.md`), so those ideas carry weaker
     evidence.
6. **Robustness:**
   - parameter neighbours
   - removal of the top trades
   - beating random-entry and always-in baselines
   - surviving stress costs
7. **Forward observation (SHADOW, Milestone 2):** a pre-declared number of sessions **and**
   trades, with a pre-declared rule for "consistent with the backtest". No profitable-day count is
   proof of an edge.
8. **A separate decision for paper orders** (Milestone 3), and **a separate decision for any real
   money** (a future proposal).

**Thresholds that need your decision** (none is universal):
- minimum trade count
- which cost level must pass
- the baseline percentile
- the maximum drawdown
- the forward-observation length
- the tolerance between shadow and backtest behaviour

### Track B milestones

#### Milestone 1: automatic no-order session dry run (DRY_RUN)

| Item | Content |
|---|---|
| **Deliverable** | A session runner (`python -m trading.operations run`) that, on a trading day: computes the phases from XNYS; runs the pre-open checks (calendar, clock skew, disk, records writable, monitor worker fresh, order guard disabled, approved-strategy registry); records entry permission at each phase boundary and every minute in the entry window (always **DENIED: no approved strategy**, plus any other failing gate); handles late start and missed sessions; writes an after-close report. Plus an Operations table view in the dashboard. |
| **Reuse** | `trading/sessions.py`; the monitor store and freshness labels (read only); `trading/safety.py`; the depmap status conventions; the dashboard server patterns; `STATUS.json` files for refusal |
| **Changes** | New package `trading/operations/` with no import of any write client and no network code of its own except reading the monitor store and one read-only clock/account check through the existing client. A new `config/approved_strategies.json` (empty). A new operations SQLite store. A new dashboard table view. |
| **Acceptance** | (1) Synthetic tests: DST weeks, an early close, a holiday, a weekend, a late start, a missed session, a crash and restart, a stale feed, disk full, a database lock, clock skew, kill switch, refusal of closed/deferred/mismatched strategies, and an import-graph test that no order-capable code is reachable. (2) `ORDER_SUBMISSION_ENABLED` stays false; the runner refuses to start if it is true. (3) A real run for a **pre-declared number of consecutive sessions** (recommended 5), each with a complete record and report, and every decision "no trade" with reasons. |
| **Rollback** | Stop the process (and, if installed later, disable the scheduled task). Nothing else is affected: the runner is read-only. |
| **Decisions** | Section G, items 1-4 |

#### Milestone 2: forward observation of an approved strategy without orders (SHADOW)

| Item | Content |
|---|---|
| **Deliverable** | The runner evaluates an **approved** strategy version on live bars and records "would-have" entries and exits with modelled fills and costs, labelled SHADOW. It never submits orders. |
| **Prerequisite** | A strategy that passed Track A steps 1-6 and that you approved for shadow observation. **None exists. This milestone is blocked until then.** |
| **Reuse** | `trading/engine.py` (`SessionStrategy`, `execute_plan`), `risk.py`, `costs.py`, the journal, the evaluation report |
| **Changes** | A live-bar adapter that feeds only completed bars; a persisted `RiskState`; approval fingerprint checks at each decision; a shadow-vs-backtest comparison report |
| **Acceptance** | The pre-declared observation length is completed; the decision rules reproduce offline from recorded bars (byte-identical); risk gates are tested with existing positions and pending (simulated) orders; reports reconcile with the records |
| **Rollback** | Revoke the approval (the runner returns to DRY_RUN behaviour) |
| **Decisions** | Strategy approval for shadow; observation length; the data plan (IEX vs consolidated real-time) for that strategy |

#### Milestone 3: separately authorized automatic paper trading (PAPER)

| Item | Content |
|---|---|
| **Deliverable** | An execution module that submits **paper** orders for the approved strategy only, with a persistent intent log, unique client order ids, reconciliation before every entry, and a kill switch. |
| **Reuse** | `safety.require_order_submission_allowed()`; the read-only client for reconciliation (new GET methods only); the Milestone 1-2 runner, gate and records |
| **Changes** | A **separate** write client, in a new file, limited to `paper-api.alpaca.markets`. The existing read-only client stays read-only. The order lifecycle is below. |
| **Order lifecycle** | Validate (approved version, gate, risk incl. pending, price sanity, size >= 1 share, long-only if required) → persist the intent with a deterministic `client_order_id` (strategy version + session + intent sequence) → submit → **ACKED / REJECTED / UNKNOWN** (timeout) → working → PARTIAL → FILLED / CANCELED / EXPIRED. UNKNOWN counts as live exposure until resolved by a GET. Restarts never re-submit an intent that already has an id; they reconcile first. Broker-side protective stops are placed per the strategy spec. Manual account changes are detected by reconciliation and block entries. Whether Alpaca rejects a reused `client_order_id` must be verified in the paper documentation, not assumed. |
| **Acceptance** | Failure-injection tests (timeout before or after broker acceptance, crash between intent and submit, duplicate fill events, partial fills, rejections, a manual position) prove no duplicate orders and correct exposure. A broker integration test, separately scoped, runs on paper with tiny size and a written test plan. Live endpoints are unreachable by construction (host allowlist test). |
| **Rollback** | Kill switch (blocks entries); set `ORDER_SUBMISSION_ENABLED=false`; revoke the approval; a defined, owner-chosen procedure for any open paper positions |
| **Decisions** | Explicit authorization; the paper equity base and allocation; the breach policy (flatten or hold under stops); maximum orders per day; the trading hours window |

#### Milestone 4: evidence review

| Item | Content |
|---|---|
| **Deliverable** | A written review: paper vs shadow vs backtest behaviour; paper order handling and simulated fill behaviour (not real-world slippage (corrected 2026-11-11: paper fills test order handling and Alpaca's simulated execution; they cannot establish real-world slippage)); operational incidents; unresolved limitations |
| **Acceptance** | Every figure is traceable to records. Paper results are never labelled real-money profit. |
| **Decisions** | Continue, revise (a new spec version, a new lock) or stop |

#### Any live pilot

A **separate future proposal**. It requires your explicit written authorization, a new host
allowlist entry, legal and account checks (including pattern-day-trader rules for small margin
accounts), and its own risk limits. Nothing in Milestones 1-4 creates it.

### Risk-limit mapping (for M2 and M3)

| Limit | Enforced by | Gap |
|---|---|---|
| $100,000 start | `experiment.py` / `orb_experiment.py` (simulation only) | Decision: paper uses broker equity or a fixed virtual allocation |
| 0.10% risk per trade incl. costs | `risk.size_position` (`risk_includes_costs=True`) and `engine.acceptance_limit` | Uses modelled costs; actual loss can exceed it (gaps) |
| 0.50% daily loss | `RiskState.observe` (mark-to-market after costs, from the session-start mark) | Not persisted. "Session-start equity" must be defined for paper (the broker's `last_equity`?). |
| 3% drawdown halt | `RiskState.halted` (permanent) | **In memory only**: a restart would forget it. Must be persisted, with owner-only reset. |
| 5% per position | `max_notional` cap | — |
| 10% total exposure | `gross_in_use` (includes pending entries) | Must include broker-reported pending and partially filled orders |
| 2 positions | `positions_in_use` (includes pending) | The same |
| No leverage | implied by the 10% gross cap | Add an explicit check: order notional <= cash; ignore the paper account's 4x buying power |
| 1% participation (in the baseline, not in the summary list) | `size_position` participation cap | Confirm it is intended |
| Long-only | strategy rule (001 v1.3, 002 v1.0) | Decide whether long-only is account-wide policy |
| Breach action | daily: block entries; drawdown: halt; exit at the next bar in simulation | **Policy decision** for paper: flatten or hold under stops |

### JARVIS's role

- **May:**
  - read records
  - explain status, reasons for "no trade", risk usage and reports in plain language
  - summarize the day
  - draft proposals (a new hypothesis, a spec change) **as text for your review**
  - send optional notifications from the generated report
- **May not:**
  - start, stop or configure the runner or the execution module
  - change approvals, risk limits, strategy rules or environment flags
  - submit, cancel or modify orders
  - promote anything from shadow to paper to live
  - write `research/*` approval files
- **External content does not authorize anything.** Market news, retrieved text, call
  transcripts and messages are data. They can never override the gate, authorize an order, or
  approve a strategy.
- **Independence:** the kill switch, risk gate and reconciliation run without JARVIS. Phone or
  notification failure never disables them.
- **No messages or calls** were sent or placed in this task.

### Records and dashboard

- **Records:** runs, config fingerprints (strategy spec hash, params, code commit, cost model, risk
  limits), checks, data health, decisions (including every "no trade" reason), risk checks, order
  intents, broker responses, fills, reconciliations, reports.
- **Five timestamps where applicable:** source event, local receipt, decision, submission, broker
  fill.
- **Dashboard:** a table-based Operations view showing environment, approved strategy (NONE today),
  feed and freshness, reconciliation status, entry permission with reasons, kill switch, and
  today's report. The 3D city is not expanded for this.

### Scheduling: Windows options (for M1 onward)

| Option | Pros | Cons |
|---|---|---|
| Keep the dashboard supervisor (today) | already built | runs only while the desktop app and server run; not a schedule |
| **Windows Task Scheduler (recommended)** | built in; a weekday trigger (for example 08:45 local) starts the runner, which checks the calendar itself and exits on holidays; "wake the computer to run"; restart-on-failure settings | needs the PC on (or able to wake) and the user logged on, unless you store a Windows password for "run whether logged on or not"; local-time triggers (this PC is on Eastern time, and the runner re-checks in ET anyway) |
| Windows service (pywin32 / NSSM) | starts at boot without login | more complex install and permissions; harder for a beginner to stop and inspect; still the same single PC |
| Cloud VM | independent of your PC | cost, remote credential storage, a new security surface; premature without a strategy |

**Other operational facts:**
- **Power plan:** this PC never sleeps on mains power and sleeps after 10 minutes on battery
  (`powercfg`, 2026-11-09).
- **Reboots:** Windows Update reboots, network loss and closing the desktop app all stop the
  current monitoring.
- **OneDrive:** the project, including SQLite stores under `data/`, is inside OneDrive. Sync can
  lock or conflict with live database files. Recommendation: put the operations store outside
  OneDrive, or pause sync during sessions (decision 2).

---

## G. Owner decisions that block Milestone 1

| # | Decision | Recommendation | Tradeoff |
|---|---|---|---|
| 1 | Approve Milestone 1's scope: a no-order dry-run runner, an empty approvals file, and an Operations view | **Yes** | Builds infrastructure with no strategy yet; no trading value until Track A succeeds |
| 2 | Where the operations records live | **A local folder outside OneDrive** (for example `%LOCALAPPDATA%\TradingProject\operations`), with daily reports copied into the project | Avoids sync locks; the data is not backed up by OneDrive automatically |
| 3 | How the runner starts during M1 | **Manually at first.** Install a Task Scheduler entry only after the tests pass, by a separate approval | Slower to "automatic", but nothing unattended runs before it is proven |
| 4 | How many consecutive real sessions pass M1 | **5** (matching the monitoring checklist) | Fewer finishes sooner but proves less; more catches rarer faults |

**Later decisions (not blocking M1):**
- the data plan for a real strategy
- the Track A thresholds
- the breach policy
- the paper equity base
- confirming the 1% participation cap and account-wide long-only
- the clock-skew tolerance (proposed 2 s)

---

## H. Smallest useful next task (after your approval)

**"Session clock and entry-permission gate", offline only.** No runner process, no scheduled task,
no network.

| File | Purpose |
|---|---|
| `trading/operations/__init__.py` | Package marker; a docstring stating DRY_RUN only, with no order code |
| `trading/operations/schedule.py` | For a date: trading day or not; phases in UTC and ET (pre-open, entry window per strategy, close, report), using `trading/sessions.py`; classifies "now" as before, during, late or missed |
| `trading/operations/approvals.py` | Loads `config/approved_strategies.json`; returns NONE or exactly one approved version; refuses CLOSED / FAILED_DEVELOPMENT / DEFERRED / missing / fingerprint-mismatch, using the experiments' `STATUS.json` and the registry's spec hash |
| `trading/operations/gate.py` | A pure function: inputs (environment, approval, phase, data health, risk state, reconciliation, kill switch, clock) → `EntryPermission(allowed, reasons[])`. DRY_RUN always denies. |
| `config/approved_strategies.json` | `{"approved": []}` |
| `tests/test_operations_schedule.py` | Synthetic: DST spring and autumn weeks, early close 2026-11-27, holiday 2026-11-26, a weekend, a late start at 10:05 ET, a missed day |
| `tests/test_operations_gate.py` | Synthetic: no approval denies; 001/002 (CLOSED) and gap-down (DEFERRED) refused; a fingerprint mismatch refused; each gate reason reported; DRY_RUN denies even with everything else green; an import-graph check that `trading.operations` imports no order-capable code and no `requests` write calls |

**Verification:**
- run only the two new test files, then the full offline suite once
- no network, no credentials, no scheduled task, no change to `trading/alpaca_client.py`,
  `safety.py`, risk limits or any strategy

---

## I. Costs and hosting

**Observed facts:**
- **Current Alpaca data plan in use:** Free.
  - Its access was verified in this project: IEX real-time bars accepted; recent SIP refused
    (HTTP 403); SIP 15 minutes delayed.
  - Alpaca's official data page (<https://alpaca.markets/data>, read 2026-11-09) lists:
    - **Free: $0/month.** IEX; 200 API calls/min; real-time via websocket, 15-minute delay via
      the API; websockets limited to 30 symbols.
    - **Algo Trader Plus: $99/month.** All US exchanges; unlimited API calls.
- **Paper account:** in use (balance $100,000 paper). No charge is recorded in this project.
- **Model review:** disabled. $0 spent; the one attempted call was rejected for credit and not
  billed.
- **Resource use observed:**
  - monitoring polls 1 request per minute while the market is open (the worker record shows 308
    requests in total)
  - the spread pilot used 135 requests and 7.9 MB
  - the development history is about 132 MB on disk
- **Machine:** this Windows PC. It never sleeps on mains power and sleeps after 10 minutes on
  battery.

**Estimates (not measured):**
- **Milestone 1:** no new data cost; a few MB of records per session; the runner's CPU use is
  negligible next to the dashboard.
- **Milestone 2 onward:** whether $99/month consolidated data is needed depends on the strategy.
  It is needed if decisions or cost checks rely on the consolidated real-time price or spread.
- **Hosting off this PC (cloud VM):** not priced here, because no official source was checked;
  premature until a strategy exists.
- **Real-money costs** (commissions, regulatory fees, borrow): out of scope until a live proposal.
