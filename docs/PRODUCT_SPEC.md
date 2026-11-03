# Trading City: product specification

Status: living document. Last updated 2026-11-03.

Order submission stays disabled through every milestone listed here.

## 1. Purpose

The product is a local research and monitoring tool for paper-trading
experiments. It answers one question: does a clearly specified strategy have
repeatable results after realistic costs, within agreed risk limits? It does
not assume an edge exists, and it never presents simulated or fixture results
as market evidence.

## 2. Modes (never blended)

| Mode | Data | What it shows | Status |
|---|---|---|---|
| **DEMO** | Synthetic fixtures (`trading/fixtures/synthetic.py`) | Software behavior only | Implemented |
| **HISTORICAL REPLAY** | Verified Alpaca historical bars | The strategy on real past sessions, time-gated | Blocked: data access unverified |
| **SIMULATION** | Historical replay outputs plus a reviewed scenario method | Sensitivity to costs/delays; resampled distributions | Proposed; method needs owner review (section 8) |
| **PAPER ACCOUNT** | Alpaca paper account, read-only | Broker-side balances, positions, activity | Blocked: access unverified |

Rules:
- Every event and every report carries its `mode`.
- A server instance runs exactly one mode. The browser rejects events from any
  other mode.
- Balances and performance from different modes are never added together,
  averaged, or shown in the same total.
- There is no silent fallback: if a mode's data is missing, that mode refuses to
  start and says why.

## 3. Shared records

One event stream (`trading/events.py`) feeds one ledger
(`trading/dashboard/ledger.py`). The city, the tables, the charts and the
evaluation reports are all views of that ledger. A report that disagrees with
the city is a bug. The tests check that they agree.

## 4. Tower detail tabs

Selecting a tower opens these tabs:

| Tab | Content | Source of truth |
|---|---|---|
| Rules & version | Strategy id, spec version, spec file hash, parameters, variant id, risk limits (marked placeholder if D1 is open) | `trading/strategies/registry.py`, `SPEC.md` |
| Scanner & news | Screening rules and source-linked news, time-stamped and gated to simulated time | **None configured.** The universe is fixed by the spec (SPY). No verified news source exists, so nothing is shown rather than placeholder headlines. |
| Historical replay | Sessions replayed, periods (development/validation/final), coverage | Blocked until data is verified. Shows the defined periods and 0% coverage. |
| Results | Evaluation report (section 7) for the current mode | `trading/evaluation.py` over ledger records |
| Paper account | Read-only broker activity | Blocked until access is verified |
| Decisions & risk | Every signal, decision, risk check and fill with timestamps | Ledger records |

## 5. Research responsibilities

These are configured in `research/responsibilities.json`. Each responsibility
names how it is implemented: a deterministic module, a manual owner step, or
not implemented. None currently uses an AI agent.

The reference video advertised a package of eleven skills. **It has not been
received or installed.** Only skills actually present in a session should be
reported as available.

## 6. Historical replay rules (for milestone 4)

- **Time gating.** The replay exposes only information available at the
  current simulated time:
  - bars whose interval has ended
  - news whose publication time has passed
  - data as first published, not later revisions
- **Leakage tests.** The engine already enforces bar-level gating, and
  `tests/test_backtest.py` changes future bars to prove decisions don't move.
- **Periods.** Development, validation and final periods stay distinct, as set
  in `trading/experiment.py`. The final period is locked behind an explicit flag.
- **Every report records:** sample size (trades), unique sessions, sessions
  with usable data vs. expected sessions (coverage), and skipped sessions by
  reason.
- **Repeat runs.** Re-running the same variant on the same data must give a
  byte-identical result hash. That is a **reproducibility check, not
  additional evidence**.

## 7. Evaluation report contents

For each evaluation (`trading/evaluation.py`):

- **Performance:** net P&L and return on allocation after modeled costs, gross
  P&L, and total modeled costs.
- **Risk:** maximum drawdown (mark-to-market), and exposure (time in market,
  average notional / equity).
- **Sample:** trade count, unique sessions traded, sessions evaluated,
  coverage, and skips by reason.
- **Outcomes**, classified by the rules below.
- **Trade statistics:** average gain, average loss, win count, loss count,
  and average holding time.
- **Cost sensitivity:** net P&L if modeled costs were 0x, 1x, 2x or 3x.
  Costs are linear in basis points, so this is exact for the cost model used.
- **Limitations:** listed in every report, including mode, sample size and
  data source.

### Outcome classification rules (`trading/outcomes.py`)

These are applied to each executed trade by scanning its 1-minute bars from
the entry bar up to the exit:

| Class | Rule |
|---|---|
| `target_first` | A bar's range reaches the target, and no earlier or same bar reached the stop |
| `stop_first` | A bar's range reaches the stop, and no earlier bar reached the target, and the same bar did not also reach the target |
| `ambiguous` | One bar's range reaches **both** stop and target. Bar data cannot show which came first, so it is **not** counted as a target hit. The engine's fill is the pessimistic stop. |
| `neither` | Neither level was reached before the scheduled exit |
| `unfillable` | A decision to enter had no executable price (no entry bar within the allowed delay, or a stressed order failure). Counted from decisions, not trades. |

- If a strategy version defines no target, `target_first` and `ambiguous` are
  reported as **not applicable**, not as zero.
- "Target reached" is a price event. It is not the same as a profitable trade
  after costs; the report shows both separately.
- Frequencies are descriptions of the evaluated sample. They are not
  probabilities of future outcomes.

## 8. Scenario simulation method (PROPOSED: awaiting owner review)

Nothing in this section is implemented. Two methods are proposed. Both start
from historical replay outputs, so they also wait on milestone 4.

**A. Execution-assumption grid (deterministic).** Re-run the same historical
sessions with:
- execution delay of 0, 1 or 2 minutes
- cost levels base, stress and severe
- the stop-multiplier neighbors

This involves no randomness and no new paths. It answers "how fragile is the
result to execution assumptions?"

**B. Session block bootstrap (random, seeded).**
- **Resampling unit:** whole sessions' net trade returns (one per session,
  zero for no-trade sessions), never individual bars.
- **Time dependence:** contiguous blocks of `L` sessions (proposed `L = 5`, one
  trading week) are drawn with replacement. This keeps volatility clustering
  and serial dependence within blocks.
- **Each run records:** method, block length, seed, number of runs, and the
  number of underlying historical sessions `N`.
- **Output:** distributions of total return and maximum drawdown, labeled as
  resampled.
- **What more runs do:** they reduce Monte Carlo noise in the estimated
  distribution.
- **What more runs do not do:** they add no information beyond the `N`
  historical sessions. The width of the distribution is limited by `N`, not by
  the run count. A user-chosen run count is capped at 10,000.
- **Never shown as history:** resampled paths are never shown as actual
  historical sessions or placed on the price chart.

Questions for review:
1. Block length.
2. Whether to resample sessions only from the development period.
3. Run-count cap.

## 9. Milestone checklist

| # | Milestone | Status | Evidence |
|---|---|---|---|
| 1 | Inspect repository, identify reusable parts | Done | This document, section 3 |
| 2 | Product spec and checklist | Done | This file |
| 3 | DEMO dashboard with deterministic fixtures | Done (this milestone) | `pytest`, browser checks in PROGRESS.md |
| 3a | Versioned strategy specs, responsibilities config, outcome rules, evaluation report, tower tabs | Done (this milestone) | `tests/test_evaluation.py`, `tests/test_dashboard.py` |
| 4 | Historical replay on verified data | Blocked | Needs `.env` paper keys, a passing `verify_data_access`, then an SPY data loader |
| 5 | Scenario simulation | Proposed | Needs review of section 8, and milestone 4 |
| 6 | Paper-account monitoring (read-only) | Blocked | Needs verified Alpaca access |
| later | Paper order submission | Not planned | Requires separate explicit approval |
