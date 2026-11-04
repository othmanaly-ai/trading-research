# Experiment 002-895a4f9c5d: development-period result

**Verdict: FAILED at development** under the predefined spec v1.0 rules (D1, D4, D5 and D6 fail).
This is a historical simulation: real Alpaca SIP prices with modeled fills and costs, not broker
results. Validation and final data were not retrieved.

## Run

| Item | Value |
|---|---|
| Experiment / lock | `002-895a4f9c5d`: spec v1.0, file hash `25b5f29ef8b5`; tested code commit `33fede4`; lock committed in `4ba245d` |
| Run id | `20261104T034149Z`, run at git `4ba245d` (clean) |
| Command | `.venv\Scripts\python -m trading.orb_experiment --run development` |
| Period | Development, 2016-01-04 to 2021-12-31 (1,511 sessions; data reused from experiment 001) |
| Data | SPY, Alpaca SIP 1-minute bars, adjustment `all` (provenance: `001_intraday_momentum/runs/...data_provenance.json`) |
| Configurations evaluated | Exactly the 4 predeclared (primary, range_15, range_45, midpoint_stop). No others. |
| Risk limits | Owner baseline: $100,000 start, 0.10% planned risk incl. costs, 0.50% daily, 3% drawdown, 5% notional, 10% gross, 2 positions |

## Acceptance rules

| Rule | Result | Supporting metrics |
|---|---|---|
| **D1** Net > 0 at base and >= 0 at stress | **FAIL** | Base **-0.0141%** (-$14.10); stress **-2.19%** (-$2,193.86) |
| **D2** No halt (base, stress) and max drawdown <= 3% | PASS | No halt in base or stress. Intraday max drawdown 0.82% (base) and 2.49% (stress) |
| **D3** Beats B3 (full account, base) | PASS | Strategy -0.0141% vs B3 **-1.30%**. B3 has 1,424 trades and a different exposure, so this is context, not proof of skill. |
| **D4** Positive without the 10 largest winners | **FAIL** | -$14.10 - $1,089.63 = **-$1,103.73** |
| **D5** Configurations 2-4 each > 0 and no halt | **FAIL** | range_15 +0.334%, range_45 +0.038%, **midpoint_stop -0.306%**; no halts |
| **D6** Screening: >= 95th percentile of B1 | **FAIL** | **83.0th** percentile (seed 20261104); 83.1th (seed 20261105). An engineering screen, not a significance test. |

## Primary, full account

| Metric | Base | Stress | Severe (reported) |
|---|---|---|---|
| Net P&L | -$14.10 | -$2,193.86 | -$2,909.19 (drawdown halt triggered) |
| Gross P&L | +$1,166.46 | +$1,156.72 | +$498.08 |
| Modeled costs | $1,180.56 | $3,350.58 | $3,407.27 |
| Trades / unique sessions | 1,058 / 1,058 | 1,058 | 737 (stopped by the halt) |
| Max drawdown (intraday marks) | 0.82% | 2.49% | 3.00% |
| Time in market / average notional | 41.7% / 4.85% of equity | same | |
| Win rate / average win / average loss | 46.9% / +$18.05 / -$15.96 | 42.1% | |
| Profit factor | 0.998 | 0.78 | 0.60 |
| Sharpe with 95% bootstrap CI | -0.006 [-0.85, +0.73] | -1.17 | |
| Average holding time | 231.6 min | | |

- **Gross vs costs:** gross was slightly positive, about +2.3 bp per trade on about $4,850 notional.
  That is roughly equal to the base round-trip cost, so net is about zero; at stress costs it is
  clearly negative.
- **Exits:** 401 stops, 657 time exits.
- **By year:** 2016 +0.09%, 2017 -0.06%, 2018 -0.04%, 2019 -0.03%, 2020 -0.16%, 2021 +0.18%.
- **Exit sensitivity (reported only):** a market-on-close exit gave +0.075%.

## Data exclusions and unresolved cases

- **448** sessions had no breakout (not an exclusion; no signal).
- **3** sessions had an incomplete opening range (missing bars in 09:30-09:59). These are the
  March 2020 sessions whose gaps match the reported market-wide halts.
- **2** sessions stopped by M2 (a failed data check before a signal), recorded explicitly:
  2016-02-02 (missing bar 11:19 ET) and 2021-05-05 (11:27 ET).
- **0** involuntary overnight carries, **0** unresolved and **0** provisional valuations; no
  position was open at the dataset boundary.

## Comparisons (diagnostic: fixed $5,000 per trade, no halts, dollar P&L / $100,000)

| | Strategy | B1 (seed 20261104, 10,000 runs) | B2 (context; conditional) |
|---|---|---|---|
| Participation | 70.2% (p = 0.7016 of 1,508 eligible) | same p | strategy sessions only |
| Trades | 1,058 | mean 784.7 matched; **273.4 unmatched (25.8%)** | 99 sessions with no room before the entry |
| Diagnostic net | **-$175.44 (-0.175%)** | median -$548.65 (-0.549%); 95th percentile +$87.73 | median **+$4,350.59** |
| Mean holding time | 231.6 min | 146.5 min* | |
| Mean stop distance | 41.1 bp | 39.5 bp* | |
| Total costs | $1,216.70 | mean $902.35 | |

- \* These two B1 fields were NaN in the original run, because of a reporting bug (NaN-propagating
  sum). They were recomputed after the fix with the same data, seeds and function; the gate
  fields were verified identical (`runs/20261104T034149Z.b1_descriptive_fix.json`).
- **B1 vs the strategy:** B1 is not risk- or exposure-matched. It held for shorter times and had
  fewer trades because of unmatched draws. The strategy ranked 83rd, below the 95th screening
  hurdle.
- **B2:** it ranked far above the strategy. B2 is biased upward by construction: on days a
  breakout happened, entering earlier captures more of the rise. It shows that entering at the
  breakout came late within those days, but it is context only.

## Limitations

- The development data was reused from experiment 001 (disclosed before the run).
- Costs are modeled guesses; the result is near zero at base and negative at stress, so it is
  cost-fragile.
- The exit proxy (the C - 1 bar's open) is not a guaranteed fill.
- One instrument and one six-year period.

## Recommendation

Reject this candidate at the development stage, as the predefined rules require. Do not
promote it to validation, and do not adopt the positive range_15 neighbor; selecting the best
neighbor is not allowed. Validation and final data remain untouched.
