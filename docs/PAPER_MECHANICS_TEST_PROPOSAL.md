# Proposal: test paper-order mechanics independently of any strategy (PROPOSED, nothing approved or built)

Written 2026-11-11.

**Status:** this proposal implements nothing, enables nothing and authorizes nothing:
- order submission stays disabled;
- no network order transport exists, by design;
- no order may be placed until every step in section 5 is done.

It frames the existing detailed plan, `docs/PAPER_TEST_PLAN_DRAFT.md` (safety controls C1-C12, the session script
and stop conditions). Decisions are in `docs/PAPER_TEST_DECISION_SHEET.md`.

## 1. Does the roadmap permit it?

**Partly, and you need to confirm the sequencing (decision P0).**
- `docs/AUTO_TRADING_ROADMAP.md`, Milestone 3, already lists as acceptance "a broker integration test, separately
  scoped, runs on paper with tiny size and a written test plan".
- The same milestone delivers paper orders "for the approved strategy only", and it comes after Milestone 2, which
  needs an approved strategy. None exists.
- Running only the separately scoped integration test **before** any strategy exists moves one Milestone 3 item
  earlier. It does not approve Milestone 3 itself.
- The roadmap does not say this explicitly either way. That is why it needs your decision rather than my reading.

## 2. What it would test, and what it cannot

**It tests the mechanics of Alpaca's paper environment:**
- request formats and rejections (403 and 422);
- order visibility by client order id, and lookup timing;
- acknowledgement versus fill;
- partial fills, and execution-id semantics in activities;
- cancel request (204/422) versus confirmed cancellation;
- the inactive window of attached stop legs;
- wash-trade rejections;
- restart and unknown-outcome recovery against the real paper API;
- reconciliation of orders, positions and cash;
- optionally, client order id reuse (A9).

**It cannot establish:**
- **real-world slippage, fill quality or market impact**, because paper fills are Alpaca's simulation;
- **whether any strategy is profitable**: no strategy is involved, and the orders are scripted;
- **live-account behaviour**: margin, pattern-day-trader rules, real fees and routing differ.

## 3. Design principles (from the existing plan, unchanged)

- **Scripted, tiny orders:** limit orders only, on owner-chosen symbols and quantities (decision sheet item 2).
- **Separation from the dry run:**
  - The test never runs during a dry-run session.
  - It runs only after Milestone 1 is accepted, or in a separate paper account (C1).
  - Test positions would make a dry-run day fail its broker-evidence exposure check.
- **Same guards as now:**
  - Every write calls `require_order_submission_allowed()`.
  - The flags are set only in the test process's environment, never in `.env`.
  - The read-only client stays GET-only.
  - The adapter allows the paper host only; a test proves the live host is unreachable.
- **Ledger first, deterministic ids, no automatic resubmission;** UNKNOWN blocks entries.
- **Supervised:** the owner is present, there is a written stop list, and the owner reviews before any further
  session.
- **Risk limits:** `OWNER_BASELINE_2026_11_03` is unchanged. The test's own caps (shares, notional, orders, a
  test-loss limit) are separate, smaller owner numbers, and none is chosen here.

## 4. What exists, and what is missing

From `PAPER_TEST_PLAN_DRAFT.md` part 5, status on 2026-11-11, re-checked today: the 15 adapter tests pass.

| Item | Status |
|---|---|
| Write path gated by the safety guard | DONE offline |
| Ledger-first journal, deterministic ids, crash recovery (6 fresh-process drills) | DONE offline |
| Unknown-outcome blocking; reconciliation incl. a missing order | DONE offline |
| Emergency stop: block, cancel, confirm, reconcile | DONE offline. The exposure action is UNSET. |
| **Paper-only network transport + live-host-unreachable test** | **NOT BUILT** (a separate authorized build step) |
| **Kill switch checked before every submission** | **NOT CONNECTED** to the execution core |
| Hard limit values; test-loss limit; unprotected-time bound; escalation timers | **UNSET** (owner numbers) |
| Intended paper account on record | **NOT MET** (`config/intended_paper_account.json`, owner-written) |
| Milestone 1 acceptance, or a separate account | **NOT MET** (1 of 5 by the stored reports) |
| Written authorization | **NOT GIVEN** |

## 5. Proposed sequence (each step needs its own owner decision)

1. **P0:** confirm that a strategy-independent mechanics test may come before any approved strategy.
2. **Decisions:** the items in the decision sheet (A1-A10), the test-loss limit, and the account choice.
3. **Offline only, no order path enabled:**
   - connect the kill switch to the execution core;
   - review the session script against the approved decisions.
4. **Build step (a separate authorization):**
   - a paper-only network transport in `trading/paper_adapter/`, with a host allowlist and a live-host test;
   - tested against fixtures, never sending.
5. **Readiness:** every item MET in `execution_readiness.py`, including Milestone 1 acceptance or a separate account.
6. **Authorization:** written authorization for one supervised session with the specified orders.
7. **After the session:** a report listing which documented behaviours held, which did not, and the measured
   values. The flag returns to false.

## 6. The next decision

**P0.** Should the strategy-independent paper mechanics test be scheduled ahead of any approved strategy? Yes or
no. Nothing is built either way until the later steps are separately approved.
