# Execution lab: LOCAL EXECUTION SIMULATION

A rehearsal of the order lifecycle against a **fake, in-memory broker**, using synthetic scenarios. It is not a
broker integration, not a paper account and not a validated strategy. No order exists anywhere, and nothing leaves
this computer.

- Code: `trading/execution_lab/`
  - `ledger.py`: states, transitions, the append-only ledger, and `derive()`
  - `fake_broker.py`: the fake broker
  - `lab.py`: gates, submission, reconciliation and the emergency stop
  - `scenarios.py`: the 12 scenarios, the invariant checks, and the payload for `/api/execution-lab`
- City: the **Execution lab** tab, under its own group "Local execution simulation", with its own banner.
- Preview: launch config `execution-lab-preview`, a read-only server on port 8770. It serves the page from the
  git-ignored `dashboard/web/preview/dist`, so the production page (8765, `dashboard/web/dist`) is unchanged.
- Tests: `tests/test_execution_lab.py`.

## Isolation from the dry run

- **Acceptance-critical files untouched.** No file in `trading/operations/`, nor `sessions.py`, `safety.py`,
  `alpaca_client.py` or `config/approved_strategies.json`, was changed or references the lab. The operations
  fingerprint stays `461c31297c5a6c1e`.
- **Nothing network-capable in the lab.** It does not import the broker client, `requests`, `urllib`, `http`,
  `socket`, monitoring or operations code, and contains no credential names or broker hosts.
- **No project writes.** Tests fail on any non-loopback connection, and on any SQLite file outside memory or the
  system temp folder.
- **Reused definitions, unchanged:** `OWNER_BASELINE_2026_11_03` through `size_position` and `RiskState`, and the
  `BASE` cost model.

## Order lifecycle

CREATED → VALIDATED | BLOCKED → SUBMISSION_PENDING → ACCEPTED | REJECTED | UNKNOWN. From there an order moves to
PARTIALLY_FILLED, then FILLED. A cancellation request moves it to CANCEL_PENDING, which ends as CANCELLED or FILLED.

- **Client order ids** are deterministic: `<strategy version>:<session>:<sequence>`.
- **The ledger is the only record.** Orders, remaining quantities, positions, cash, fees and exposure are derived
  from it. Updates and deletes are refused by database triggers.
- **Broker updates are idempotent by id.** Fills are keyed by execution id, so a repeat is stored once and logged
  separately. States never move backwards.
- **UNKNOWN is not a rejection.** It counts as pending exposure, blocks new entries, and is never resubmitted. Only
  a lookup by client order id resolves it. If the broker doesn't find the order, it stays UNKNOWN.
- **CANCEL_PENDING is not cancelled.** Fills that arrive meanwhile count, and only a broker confirmation ends it.
- **After a restart** the ledger is rebuilt and entries stay blocked until reconciliation succeeds.
- **The emergency stop** records five steps: block entries, request cancellation, confirm cancellation,
  reduce/close exposure, confirm reconciliation. It reports COMPLETE only when nothing remains unresolved. It never
  liquidates: reducing exposure is reported as "NOT PERFORMED: no approved policy".

## Scenarios (all deterministic, seed 0)

| # | Scenario |
|---|---|
| s01 | Normal fill |
| s02 | Broker rejection |
| s03 | Partial fills |
| s04 | Duplicate and out-of-order updates |
| s05 | Connection lost after submission |
| s06 | Reconciliation after an unknown outcome (plus a never-received order) |
| s07 | Cancellation racing with fills |
| s08 | Restart with an outstanding order |
| s09 | Stale data |
| s10 | Exposure and daily-loss limits |
| s11 | Emergency stop with outstanding orders |
| s12 | Broker unavailable during the emergency stop |

## Open execution-policy decisions (the lab does not choose them)

See `POLICY_GAPS` in `trading/execution_lab/scenarios.py`. They cover:
- breach action and emergency-stop exposure handling;
- the stale-data threshold and recovery (the lab's 180 s is a LAB PARAMETER);
- unknown-outcome resolution, refuse versus resize, the cancel-pending timeout, and partial-fill remainders;
- orders per day and entry hours, order type and protective stops;
- emergency-stop reset, client order id reuse at the real broker, and manual positions.
