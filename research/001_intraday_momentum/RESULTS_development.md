# Experiment 001-fd13f1fdef: development-period result

**Verdict: the hypothesis fails on development data. Do not promote to validation.**
This is a historical simulation: real Alpaca SIP prices, but modeled fills and costs. It is
not broker results.

## Run

| Item | Value |
|---|---|
| Experiment / lock | `001-fd13f1fdef` (spec v1.3, hash `0b32b30b3b33`), lock matched at run time |
| Variant | `d11b3023b7bf`: primary, long-only, no tuning. 1st of 10 allowed development variants. |
| Status | **FAILED at the development stage** under the predefined SPEC section 14 criteria (`STATUS.json`) |
| Evaluation period | Development, 2016-01-04 to 2021-12-31 (1,511 sessions) |
| Run id | `20261104T001504609413Z-d11b3023b7bf` |
| Code | git `19de2c3` plus uncommitted changes. The new `trading/evaluate.py` only loads stored days and calls `run_experiment`. A bounded HTTP 429 retry in the client is used only for downloads. Neither alters any calculation; both are committed with this record. |
| Command | `.venv\Scripts\python -m trading.evaluate --period development` |
| Data | SPY, Alpaca SIP, 1-minute and daily bars, adjustment `all`, retrieved 2026-11-04. 1,511 of 1,511 development sessions usable; 99.983% of expected minutes present. Validation and final: 0 sessions retrieved. |
| Risk limits | Owner baseline: $100,000 start, 0.10% planned risk incl. costs, 0.50% daily, 3% drawdown, 5% notional, 10% gross, 2 positions |

## Results (base costs, about 2.3 bp round trip)

| Metric | Value |
|---|---|
| Trades / unique sessions | 816 / 816 (of 1,511 sessions) |
| Net P&L after modeled costs | **-$1,410.63 (-1.41%)** |
| Gross P&L, same trades before costs | -$509.98 (corrected 2026-11-04, see note) |
| Modeled costs (spread, slippage, sell fees) | $900.65 (corrected) |
| Mean move per trade, before costs | **-1.24 bp of notional** (standard error 1.08 bp; from the zero-cost re-run) |
| Mean net per trade | -3.54 bp of notional (about -$1.73) |
| Max drawdown | 1.43% (limit 3%) |
| Time in market / average position | 3.9% of session time / 4.8% of equity (the notional cap bound on 802 of 816 trades) |
| Win rate / average win / average loss | 40.8% / +$7.37 / -$8.00 |
| Profit factor | 0.64 |
| Sharpe (annualized) and 95% bootstrap CI | -1.53 [-2.72, -0.59]: the interval excludes zero |
| Every year 2016-2021 | negative |
| Exits | 757 time exits, 59 stops; 0 unresolved or overnight carries |
| Skipped sessions | 664 negative signal (long-only), 24 warm-up, 5 zero signal, 1 missing previous close, 1 data gap before decision (2019-08-12) |

## Pass rules (fixed before the run)

| Rule | Result |
|---|---|
| 1. Positive after base costs, and stress net >= 0 | **Fail** (base -1.41%, stress -2.99%) |
| 2. Beats always-long, and >= 95th percentile of random entry | **Fail.** Beats always-long in total (-1.94%, with about twice the exposure), but only the **10th percentile** of 10,000 random long/flat runs at the same long rate. Random long days did better. |
| 3. Drawdown within 3% | Pass (1.43%) |
| 4. Positive without the top 10 trades | **Fail** (-$2,027) |
| 5. Parameter neighbors same sign (positive) | **Fail:** all four neighbors are negative (-1.36% to -1.62%) |

**Correction note (2026-11-04):** the first version of this record gave gross -$495.46 and
costs $915.17. Those figures came from a separate zero-cost re-run, in which 14 risk-capped
trades sized slightly differently because costs were not included in the risk cap. For the
evaluated trades, gross is -$509.98 and costs $900.65. Net, and every pass/fail result, is
unchanged.

## Cost sensitivity

| Costs | Net return | Note |
|---|---|---|
| zero | -0.50% | Not positive even without costs |
| base | -1.41% | |
| stress | -2.99% | The 3% drawdown halt triggered; the experiment stopped after 802 trades |
| severe | -3.00% | The 3% drawdown halt triggered; stopped after 636 trades |

## Limitations

- Alpaca returned no data before 2016-01-04, so the first ~25 development sessions served as
  warm-up instead of trading.
- Costs are modeled guesses (no measured spread). That matters little here, because the
  result is negative before costs.
- Positions were small (about $4,800), so dollar results are small. The per-trade basis-point
  figures carry the information.
- One instrument, six years, about 800 trades: one test of one rule, not proof that no
  intraday momentum exists anywhere.
- March 2020 bars show 14-minute gaps matching the reported market-wide halts. All were before
  the 15:30 decision and affected no trade. The 2019-08-12 late gap (cause unknown) made that
  session skip.

## Reproducibility and file locations

Committed (in this folder):
- `runs/20261104T001504609413Z-d11b3023b7bf.json`: the full evaluation report (metrics,
  baselines, neighbors, pass rules).
- `runs/...data_provenance.json`: data source, feed, adjustment, requested and received
  ranges, pages, coverage, gap sessions, transformations, and the local manifest hash.
- `variants.csv`, `experiment_attempts.csv`: run and attempt logs.
- `EXPERIMENT_LOCK.json` (current lock) and `locks/` (superseded locks).

Kept local only (git-ignored):

| Artifact | Location | Why excluded |
|---|---|---|
| Downloaded SPY bars (raw API responses, per-session minute files, daily bars, full manifest), about 132 MB | `data/history/SPY/sip/all/` | Bulky; re-downloadable with the command in the provenance file |
| Original report output | `results/experiment_001/20261104T001504609413Z-d11b3023b7bf.json` | Same content as the committed copy |
| Data-access check outputs (the 2016 SAMPLE bars and the paper account summary) | `data/alpaca/20261103T235104Z/` | The account summary holds paper-account balances |

To reproduce:
1. Re-download the data with the command in the provenance file.
2. Confirm the manifest's counts match: 1,511 usable development sessions, 146 pages.
3. Run `python -m trading.experiment_lock` (it should report a match).
4. Run `python -m trading.evaluate --period development`. This logs a new attempt. A
   re-run is a reproducibility check, not additional evidence.

## Diagnosis (development data only; `diagnose_development.py`)

**Implementation check: no defect found.** All 816 trades were recomputed independently from
the stored CSV files, not through the engine's data objects:
- signal r1 from the previous daily close and the 09:59 bar
- sigma30 from the 20 prior sessions
- entry at the 15:31 bar's open (one minute after the 15:30 decision)
- stop, shares under every cap, and the stop/time exit rule
- costs and the equity chain

There were 0 mismatches, and the equity chain ended at $98,589.37 in both. The run also
contained 0 overnight carries and 0 unresolved cases.

**The predictive relation is absent.** SPY's last-30-minute return (bp), on development
sessions with a valid signal:

| Group | Mean | Std error | Sessions |
|---|---|---|---|
| All | -0.78 | 0.89 | 1,490 |
| r1 > 0 (the strategy's long days) | -1.60 | 1.07 | 831 |
| r1 < 0 (not traded) | +0.18 | 1.51 | 654 |

- Correlation between r1 and the last-30 return: +0.02.
- By r1 quintile, low to high: +2.46, -1.48, -1.48, -2.45, -0.96. Not monotonic.
- The rule picked days that did slightly *worse* than average. That explains why it ranked at
  the 10th percentile of random long/flat entry, and only "beat" always-long because it held
  about half the exposure.

**Losses are broad, not concentrated:**
- 59.2% of trades lost; the median trade was -$1.64.
- 72% of 71 months were negative, and every year was negative.
- Without the 10 worst and 10 best trades the result is still -$1,626.
- Costs ($900.65) are about 64% of the loss; the remaining -$509.98 is the price movement itself.
- Stop exits (59 trades, -$1,076.92) look large, but stopped trades are losers by
  construction, so this does not show the stop caused harm. The stop-multiplier neighbors
  (1.5x and 2.5x) were both also negative.

**Defects vs evidence:** the accounting, timing, fills and costs check out, so the result is
evidence against the v1.3 hypothesis on 2016-2021 SPY data, not a software artifact. The open
limitations (guessed costs; exit at the 15:59 bar instead of the closing auction) cannot turn a
negative pre-cost signal positive.

## Recommendation

Reject this hypothesis in its v1.3 form. The development result is negative before costs,
negative every year, below the random-entry baseline, and not sensitive to small parameter
changes. Validation is meant for variants that pass development; using it now would spend held-out
data on a result already known to fail. Validation and final data remain untouched.
