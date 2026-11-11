# Execution lab: LOCAL EXECUTION SIMULATION

A rehearsal of the order lifecycle against a **fake, in-memory broker**, using synthetic scenarios. It is not a
broker integration, not a paper account and not a validated strategy. No order exists anywhere, and nothing leaves
this computer.

- Code: `trading/execution_lab/`
  - `ledger.py`: states, transitions, the append-only ledger, and `derive()`
  - `fake_broker.py`: the fake broker
  - `lab.py`: gates, submission, reconciliation and the emergency stop
  - `scenarios.py`: the 18 scenarios (s01-s18), the invariant checks, and the payload for `/api/execution-lab`
- City: the **Execution lab** tab, under its own group "Local execution simulation", with its own banner.
- Preview: launch config `execution-lab-preview`, a read-only server on port 8770. It serves the page from the
  git-ignored `dashboard/web/preview/dist`, so the production page (8765, `dashboard/web/dist`) is unchanged.
- Tests: `tests/test_execution_lab.py`.

## Isolation from the dry run

- **Acceptance-critical files untouched.** No file in `trading/operations/`, nor `sessions.py`, `safety.py`,
  `alpaca_client.py` or `config/approved_strategies.json`, was changed or references the lab. The operations
  fingerprint stays `6cc6999855edd4f1`.
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
| s13 | Bracket entry partly filled: stop leg held, shares unprotected |
| s14 | Stop after fill: protect only after a confirmed cancel |
| s15 | Missing policy and unapproved strategy refuse entries |
| s16 | Manual account activity: discrepancies shown, not corrected |
| s17 | An acknowledgement is not a fill |
| s18 | Live order missing at the broker: a discrepancy, not completion (added 2026-11-11) |

## Open execution-policy decisions (the lab does not choose them)

See `POLICY_GAPS` in `trading/execution_lab/scenarios.py`. They cover:
- breach action and emergency-stop exposure handling;
- the stale-data threshold and recovery (the lab's 180 s is a LAB PARAMETER);
- unknown-outcome resolution, refuse versus resize, the cancel-pending timeout, and partial-fill remainders;
- orders per day and entry hours, order type and protective stops;
- emergency-stop reset, client order id reuse at the real broker, and manual positions.

## Execution core (2026-11-10, offline)

The lab is now a reusable execution core with an injected broker port. The path is:
intent → validation → policy and risk decision → durable journal → broker port → order updates → reconciliation →
account ledger → city.

- **Policy (`policy.py`):** every field is UNSET (`APPROVED`). A missing required field **blocks** entries and
  protective orders; it never picks a default. Cancel, reconcile and the emergency stop always run, and anything
  depending on an unset field is shown as "UNSET: owner decision". Scenarios run under `LAB_TEST_POLICY`, which is
  synthetic, labelled everywhere, and not a proposal.
- **Intents (`intents.py`):** the interface a later approved strategy would use. Strategy intents are refused, because
  the approved registry is empty ("NO APPROVED ACTIVE STRATEGY").
- **Protection:**
  - Filled shares are protected only by an ACTIVE broker-side stop. A bracket leg is HELD (inactive) until the entry
    is completely filled (documented Alpaca behaviour, simulated).
  - stop_after_fill protects only after the entry is final; a stop sell next to an open buy is wash-trade rejected.
  - Unprotected quantity and the time since it became unprotected are derived from the ledger. Beyond the policy
    time, entries are blocked. "close_exposure" is NOT IMPLEMENTED: no automatic liquidation exists.
- **Reconciliation:**
  - Orders (by client order id), fills (by execution id), positions, foreign or manual open orders, and cash are
    compared.
  - Discrepancies are recorded and keep entries blocked; nothing is forced to balance.
  - An intent validated but never sent before a crash is closed as EXPIRED UNSENT. So is an intent recorded but
    never validated or blocked (a crash during the checks; fixed 2026-11-11).
  - This happens **only with durable proof:** no submission record and no broker event for that order exist in the
    ledger. The submission record is committed before any broker call. Any such evidence makes it a blocking
    discrepancy instead, and a recorded-but-unconfirmed submission stays UNKNOWN.
  - An order the ledger shows as live, but the broker has no record of, is a discrepancy that blocks entries. It is
    never treated as reconciled (fixed 2026-11-11).
  - Cancel-request evidence is numbered from the ledger, so a request repeated after a restart is recorded, not
    filed as a duplicate (fixed 2026-11-11).
  - A submission recorded but not found becomes UNKNOWN; it is never resubmitted.
- **Fresh-process recovery (`crashdrill.py`, `tests/test_execution_recovery.py`):** seven drills, each step a separate
  Python process killed at a named point:
  - before the intent;
  - after the intent record, before its check outcome is recorded (added 2026-11-11);
  - after the intent, before sending;
  - after recording the submission, before the broker call;
  - after a possible send, before the acknowledgement;
  - during partial fills;
  - during cancellation.

  State is rebuilt only from the ledger file and the fake broker's durable file. Evidence:
  `python -m trading.execution_lab.crashdrill run-all --out results/execution_lab/crash_drills.json`.
- **Proposed paper adapter (`trading/paper_adapter/`):** offline only.
  - It uses documented Alpaca request formats, and a `FixtureTransport` is its only transport; no network transport
    exists.
  - Every write calls `require_order_submission_allowed()`, which refuses by default.
  - It is not imported by the dashboard, the dry run or the lab (tests enforce this). Undocumented behaviour is
    marked UNVERIFIED in its module text.
- **Readiness (`trading/dashboard/execution_readiness.py`):** a supervised paper test stays NOT READY until each
  prerequisite has a record: dry-run acceptance, approved policies, an owner-confirmed intended account, safety
  controls tested against paper, an approved test plan, and a written authorization.
