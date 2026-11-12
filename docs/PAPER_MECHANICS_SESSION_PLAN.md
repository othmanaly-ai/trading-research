# Final test plan: one supervised paper-order mechanics session (PROPOSED; NOT AUTHORIZED; NOTHING SENT)

Written 2026-11-11 under owner decision **P0**: paper-order mechanics may be developed and tested independently of
strategy approval. That changes sequencing only. It approves **no** strategy, **no** live trading and **no** paper-order
submission. Every value below marked **[proposed]** is a proposal for the owner to accept or change.

This plan supersedes nothing in `docs/PAPER_TEST_PLAN_DRAFT.md`. It is the smallest practical session that plan
allows; its safety controls C1-C12 still apply.

## 1. Account and endpoint

**Endpoint: verified by construction.**
- Trading host `https://paper-api.alpaca.markets`, the only trading host allowed in this project (`CLAUDE.md`,
  `trading/alpaca_client.py`).
- The session controls refuse any other host (`trading/paper_adapter/controls.py::host_reasons`, tested).
- No live host is reachable: no network transport exists today, and the one to be built allows the paper host only.

**Account: observed, NOT yet confirmed.**
- The dry run's report for 2026-11-11 records, via the paper host and read-only requests:
  - account reference **`df0ca3cbd37a`** (a one-way hash, not the account number);
  - status ACTIVE, not trading-blocked;
  - no positions and no open orders at pre-open, 09:25 and 15:55 ET.
- That shows which account the keys reach. It is **not** your confirmation that this is the intended test account.
- **To confirm it,** you write `config/intended_paper_account.json` yourself:

  ```json
  {"schema": 1, "environment": "paper", "account_ref": "df0ca3cbd37a", "confirmed_by": "<you>", "confirmed_utc": "<time>"}
  ```

- **Every entry re-checks it:** the preflight and every entry require the answering account's reference to equal this
  value, with status ACTIVE and no block flags.
- **Same account, no bypass:** the session uses the same account the dry run uses, and runs only **after** Milestone 1
  is accepted. Five consecutive PASS sessions are required, unchanged. No other account is substituted to get around
  it.

## 2. Instruments, order types, quantities, exposure [proposed]

| Item | Proposed value |
|---|---|
| Instrument | **SPY only** |
| Order type | **limit, time in force `day`**, `order_class` simple. No market, stop, bracket, short, extended-hours or fractional orders. |
| Quantity per order | **1 share** |
| Maximum position at any moment | **1 share long** |
| Maximum open orders at any moment | **1** |
| Maximum total exposure | **1 share of SPY**, with a hard notional cap of **$1,000**. If one share costs more, the session refuses before sending anything. |
| Test-loss limit | **$5** realized plus marked. Breach = stop condition. |
| Maximum unprotected time | **The whole time the 1 share is held, at most 5 minutes.** No protective stop is placed (see section 7); over 5 minutes = stop condition and exit. |
| Limit price bound (marketable orders) | **at most 0.10% through the reference quote** (buy ≤ ask × 1.001; sell ≥ bid × 0.999) |
| Resting-order price (step 1) | **at least 5% below the last trade**, so it cannot fill in normal conditions |

These caps are separate from, and far below, `OWNER_BASELINE_2026_11_03` (unchanged). They are **not** your strategy
risk limits; I have not chosen those.

## 3. Order count and duration [proposed]

- **Planned orders:** 3. **Absolute maximum:** 4 orders and 3 cancel requests. The fourth order exists only as a
  single contingency exit (step 6).
- **Window:** one regular session, from **10:30 ET**, ending by **11:30 ET** at the latest. This avoids the open and
  the close. Nothing new is sent after 11:15 ET except cleanup.
- **When:** on a trading day **after Milestone 1 is accepted**, on which you have **not** started the dry run (C1:
  never during a dry-run session). Acceptance is recorded permanently once reached; one day without a run after
  acceptance does not undo it.

## 4. The session script (the only allowed actions)

| Step | Action | Expected and recorded |
|---|---|---|
| 0 | Preflight (`session_preflight`), read-only. All 9 checks must pass: paper host, confirmed account, account ACTIVE/unblocked/matching, account flat, market open, kill switch off, Milestone 1 accepted, policy approved for this session, write permission for this one process. | Any failure: stop, nothing sent |
| 1 | Submit order 1: buy 1 SPY, limit ≥ 5% below the last trade, `day`. Ledger first, deterministic client order id. | Acknowledgement recorded. An acknowledgement is not a fill. |
| 2 | Look it up by client order id; list open orders. | Visible; lookup delay measured |
| 3 | Cancel request for order 1 (DELETE) → 204 expected. Poll until the status is `canceled`. | Request ≠ confirmation; time to confirmation measured |
| 4 | Submit order 2: buy 1 SPY, marketable limit within the 0.10% bound. | Fill via REST activities; execution id recorded once even across repeated polls |
| 5 | Submit order 3: sell 1 SPY, marketable limit within the 0.10% bound (an explicit exit, `exit_position`). | Fill; position 0 |
| 6 | **Only if order 3 has not filled within 60 s:** cancel request for order 3, wait for confirmation, then one contingency exit (order 4) at the same bound against a fresh quote | Position 0 |
| 7 | Final reconciliation: orders, fills, position and cash against the broker. Write permission returns to off. | See section 6 |

**Not tested at the broker (covered offline instead):**
- duplicate or out-of-order updates;
- partial fills;
- cancel/fill races;
- crashes and restarts at each crash point;
- unknown outcomes;
- wash-trade rejection;
- inactive bracket legs;
- client order id reuse;
- manual-account mismatches.

These are covered by the scenarios s01-s18, 14 fresh-process drills (7 through the real adapter over a simulated
Alpaca API) and 30 session-control tests. None is deliberately triggered at the broker.

## 5. Stop conditions (any one ends new orders immediately; then cleanup only)

1. Any preflight check fails, or a re-check before an entry fails: kill switch on, wrong or unverifiable account,
   non-paper host.
2. Any response that is not documented, or any unsupported order status.
3. Any **UNKNOWN** outcome: no response, a timeout, or an unexpected HTTP status on a write.
4. Any reconciliation discrepancy: position, cash, a foreign order, an order missing at the broker.
5. Position above 1 share, more than 1 open order, or notional above $1,000.
6. Test-loss limit reached ($5), or the 1 share held unprotected for more than 5 minutes.
7. 11:30 ET reached, or the owner says stop.
8. Any error in the ledger or the process; the kill switch turned on.

## 6. Cleanup and reconciliation

**Normal end:** step 7 must show:
- 0 positions and 0 open orders at the broker;
- every ledger order terminal (FILLED, CANCELLED, REJECTED or BLOCKED), with none UNKNOWN or CANCEL_PENDING;
- broker cash equal to ledger cash, or every difference listed (fees included), never forced to balance;
- a reconciliation-complete event as the last ledger entry.

**After a stop condition:**
- No new entries.
- Cancel any open order (request, then confirmation).
- If 1 share is held: one exit within the 0.10% bound.
- Reconcile.

**Uncertain outcome (UNKNOWN):**
- Never resubmit.
- Look the order up by client order id every 5 s for up to 2 minutes. Then:
  - **Found and open:** cancel request, then wait for confirmation.
  - **Found and filled:** exit 1 share; this counts against the 4-order maximum.
  - **Not found:** it stays UNKNOWN. Absence is not proof.
- Turn the kill switch on, send nothing more, and you review the account in Alpaca's own dashboard.
- The session ends **INCOMPLETE** until every order is resolved by broker evidence.

**Afterwards:**
- The write-permission flags existed only in the test process's environment, and the process exits.
- A session report states which documented behaviours held, which did not, and the measured values: lookup delay,
  cancel-confirmation delay, fill and execution-id semantics.

## 7. Deliberate omissions (smallest scope)

- **No protective stop.** The share is held for seconds to minutes. Placing a stop next to the planned exit would
  trigger the wash-trade rule, an edge case already modelled offline. Instead, the 5-minute unprotected limit and the
  $5 loss limit bound the exposure. Testing broker-side stops (bracket legs, stop after fill) would be a separate,
  later session.
- **No slippage claim.** Paper fills test order handling and Alpaca's simulated execution. They cannot establish
  real-world slippage.

## 8. The narrow permission required

You would write `config/paper_order_test_authorization.json` yourself (it does not exist; I never write it):

```json
{"schema": 1, "scope": "paper order mechanics, one supervised session",
 "plan": "docs/PAPER_MECHANICS_SESSION_PLAN.md", "plan_sha256": "<hash of this file at approval>",
 "account_ref": "df0ca3cbd37a", "host": "https://paper-api.alpaca.markets",
 "session_date": "<YYYY-MM-DD>", "window_et": "10:30-11:30", "symbol": "SPY",
 "order_types": ["limit/day"], "max_qty_per_order": 1, "max_position": 1, "max_orders": 4, "max_cancels": 3,
 "max_notional": 1000, "test_loss_limit": 5, "max_unprotected_seconds": 300,
 "authorized_by": "<you>", "authorized_utc": "<time>", "expires_utc": "<end of window>"}
```

**What it permits:**
- `ORDER_SUBMISSION_ENABLED=true` and `TRADING_MODE=paper`, set in **one** test process's environment for that window
  only;
- the orders in section 4, nothing else.

**What it does not permit:**
- any strategy;
- any other account or host;
- any other day;
- live trading;
- changes to the dry run or the risk limits.

## 9. Built offline today, and what must still be built before the session

**Built and tested offline, no order path enabled:**
- **Kill switch:** connected to the execution core. It is checked at validation **and** again immediately before
  sending. Unreadable means blocked. It blocks entries only; cancels, exits, protective orders and reconciliation
  still run.
- **Paper-only account checks:** host, the owner-confirmed account reference, ACTIVE, and no block flags. Checked
  before every entry.
- **Session preflight:** 9 read-only checks.
- **An explicit exit for cleanup:** risk-reducing; it needs the policy's order type and time in force; never
  automatic.
- **A simulated Alpaca paper transport, and restart recovery through the adapter:** 7 fresh-process drills. A fresh
  adapter relearns our order ids from the ledger.

**Still missing, each a separate approval:**
1. The paper-only **network transport**, with a host allowlist and a live-host-unreachable test.
2. A **session runner** that hard-codes the section 2-6 limits, checks the authorization file and its plan hash, and
   implements the stop conditions, the test-loss limit and the unprotected-time limit.
3. **A session policy:** the execution-policy values for this one session (order type limit, `day`, the caps above).
   Today every field is UNSET.

## 10. Remaining decisions

| # | Decision | Status |
|---|---|---|
| S1 | Accept or change the section 2-3 values (SPY, 1 share, limit/day, $1,000 cap, $5 loss limit, 5 min unprotected, 0.10% bound, ≤ 4 orders, 10:30-11:30 ET) | open |
| S2 | Confirm the intended account (write `config/intended_paper_account.json`) | open |
| S3 | Approve building the paper network transport and the session runner (no orders) | open |
| S4 | Milestone 1 accepted: five consecutive PASS sessions | 1 of 5 (stored reports) |
| S5 | Choose a test day on which the dry run is not started (after acceptance) | open |
| S6 | Write the authorization file (section 8) for that day | open |
