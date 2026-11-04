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
| Gross P&L, same trades before costs | -$495.46 |
| Modeled costs (spread, slippage, sell fees) | $915.17 |
| Mean move per trade, before costs | **-1.24 bp of notional** (standard error 1.08 bp) |
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

## Recommendation

Reject this hypothesis in its v1.3 form. The development result is negative before costs,
negative every year, below the random-entry baseline, and not sensitive to small parameter
changes. Validation is meant for variants that pass development; using it now would spend held-out
data on a result already known to fail. Validation and final data remain untouched.
