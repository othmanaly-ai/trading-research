# Why experiments 001 and 002 failed: a plain-English comparison

Written 2026-11-08. It uses only the recorded development-period results:
- `001_intraday_momentum/STATUS.json` and `RESULTS_development.md`
- `002_opening_range_breakout/STATUS.json` and `RESULTS_development.md`
- the cost model in `trading/costs.py`
- the quote-access findings in `feasibility/execution_data/FINDINGS.md`

I reran nothing for this. I retrieved and inspected no validation or final data. No strategy rule
was changed, and neither experiment is reopened. Every figure is a **historical simulation**: real
Alpaca SIP prices, with modeled fills and modeled costs. None of it is a broker result.

## Glossary

- **bp (basis point):** 0.01%. On a $4,850 position, 1 bp is about 49 cents.
- **Gross:** profit or loss before trading costs. **Net:** after costs.
- **Round-trip cost:** the total modeled cost of buying and later selling once. In `trading/costs.py`:
  - **base:** 2.3 bp. That is a 0.5 bp half-spread plus 0.5 bp slippage on each side, plus a 0.3 bp
    sell fee.
  - **stress:** 6.6 bp.
  - **severe:** 9.6 bp.
- **Random-entry baseline:** the same trading budget spent on random days. A real edge should beat
  most random runs. "95th percentile" means it beat 95% of them.

## The two strategies in one line each

- **001, intraday momentum (late day):** if SPY was up between yesterday's close and 10:00, buy at
  15:31 and sell just before the close.
- **002, opening-range breakout (morning):** buy when SPY rises above its 09:30-10:00 high, with a
  stop, and exit before the close.

Both trade only SPY, only long, and used the same 2016-2021 development data with the same risk limits.

## Side by side

| | 001 intraday momentum | 002 opening-range breakout |
|---|---|---|
| Trades | 816 | 1,058 |
| Gross result (before costs) | **-$509.98**, about **-1.2 bp per trade** | **+$1,166.46**, about **+2.3 bp per trade** |
| Modeled costs at base | $900.65, about 2.3 bp per trade | $1,180.56, about 2.3 bp per trade |
| **Net at base costs** | **-$1,410.63 (-1.41%)** | **-$14.10 (-0.014%)** |
| Net at zero cost | -0.50% | (not run as a gate; gross is +1.17%) |
| Net at stress costs | -2.99% (stopped by the 3% drawdown halt) | -2.19% |
| Net at severe costs | -3.00% (halt) | -2.91% (halt) |
| Rank vs random entry | **10th percentile** (worse than most random runs) | **83rd percentile** (better than most, but short of the required 95th) |
| Without the 10 best trades | -$2,027 | -$1,103.73 |
| Small parameter changes | all 4 neighbors negative | 2 of 3 positive, 1 negative (midpoint stop -0.31%) |
| By year | every year negative | near zero every year (-0.16% to +0.18%) |
| Max drawdown (base) | 1.43%, within the 3% limit | 0.82%, within the 3% limit |
| Rules failed / passed | failed 1, 2, 4, 5 / passed 3 | failed D1, D4, D5, D6 / passed D2, D3 |
| Implementation check | all 816 trades recomputed independently: 0 mismatches | gate fields verified; one display bug (two NaN fields) fixed, gates unchanged |

## Why 001 failed: there was no edge to begin with

- **The signal pointed the wrong way, slightly.** On days the rule bought (up mornings), SPY's last
  30 minutes averaged -1.60 bp. On days it skipped, they averaged +0.18 bp. The correlation between
  the morning move and the late move was +0.02, which is essentially none.
- **It lost before any cost was charged.** At zero cost it still lost 0.50%. Costs made a small loss
  bigger: they were about 64% of the final loss, and the rest was price movement.
- **The loss was broad, not bad luck.** 59% of trades lost, 72% of months were negative, and every
  year was negative. Removing the 10 best and 10 worst trades left it still negative.
- **Random days beat it.** It ranked at the 10th percentile of random long/flat entry. It only
  "beat" buying every day because it held about half the exposure.

**In short:** cheaper trading would not have saved 001. The pattern it relied on was not present in
2016-2021 SPY data.

## Why 002 failed: a small edge, entirely eaten by costs

- **There was a small positive move before costs.** The breakout trades gained about +2.3 bp each,
  on average, before costs.
- **The base cost was about the same size, 2.3 bp.** So net came out at almost exactly zero
  (-$14.10 on $100,000). At stress costs (6.6 bp) the same trades lost 2.19%. Costs were roughly
  the entire margin: the result depends on cost assumptions that have not been measured.
- **The edge was fragile in other ways too:**
  - Without its 10 largest winners it lost $1,103.73, so a handful of big days carried it.
  - One of the three predeclared variations (the midpoint stop) was negative.
  - Against random entry it ranked 83rd, below the required 95th, so it was hard to tell apart
    from luck.
- **Why lower costs would not overturn the verdict:**
  - The pass rules were fixed before the run.
  - Reopening a closed experiment with a friendlier cost assumption, or picking the best variation
    (range_15, +0.33%), is exactly the after-the-fact rescue the process forbids.
  - The random-entry comparison already charges random trades the same costs, and 002 still ranked
    only 83rd.

## What the two failures have in common

1. **The moves being targeted are tiny compared with trading costs.** 001 needed more than 2.3 bp
   per trade just to break even at base costs, and it had -1.2 bp. 002 had +2.3 bp, exactly the base
   cost, and far less than the 6.6 bp stress cost. For one-trade-a-day SPY rules, a few basis
   points of cost is the hurdle that matters.
2. **The cost numbers themselves are guesses.**
   - The opening-minute quote checks (7 development dates, 09:30-09:34 only) found a median full
     spread of 0.23-0.55 bp. That is below the 1 bp per round trip the base model charges for
     spread.
   - But those checks cover only the opening minutes, on 7 days. The quote data's timestamp clock
     and condition codes are not yet documented (the same blockers that defer the gap-down
     candidate).
   - Slippage (1 bp of the base round trip) and the sell fee are not measured at all.
   - So nobody knows yet whether 2.3 bp is too high, about right, or too low. That matters most for
     a strategy like 002, whose result swung from zero to -2.19% across the cost levels.
3. **Neither beat random entry convincingly** (10th and 83rd percentiles, against a 95th-percentile
   rule).
4. **The process worked as designed.**
   - The implementations were checked and no defect changed the results.
   - Both were rejected at the development stage.
   - Validation (2022-01-03 to 2024-06-28) and final (2024-07-01 to 2026-10-30) data were never
     retrieved, so they stay unused for a future hypothesis.
5. **The development data is now partly "used up".** `EXPLORATION_LOG.md` records that late-day
   rules, morning-range or breakout rules, and "buy after down mornings" ideas have all been
   looked at on 2016-2021 SPY. A new hypothesis of those kinds, tested on the same data, would be
   weaker evidence.

## Recommended next research task

**A pre-registered SPY execution-cost measurement. It measures the quoted bid-ask spread at the
times of day these strategies trade, on development dates only, and computes no strategy returns.**

What it would produce:
- A measured distribution of SPY's quoted spread, at minimum for the opening half hour, a sample
  of mid-day minutes (when 002-type breakouts enter), and 15:30-16:00 (when 001 traded). The
  dates, windows and request caps would be fixed in writing before any download, as was done in
  `feasibility/execution_data/PREREGISTRATION.md`.
- A written comparison of the measured spreads with the base, stress and severe assumptions in
  `trading/costs.py`. Changing those assumptions would be a separate owner decision. Any change
  would break the experiment locks and would apply only to future experiments.
- A proposed **minimum-edge rule** for future specs: a hypothesis should be expected to clear the
  stress round-trip cost with margin before it is worth spending data on.

Why this task, based on the findings above:
- Cost was the deciding factor for 002 and amplified 001's loss, yet it is the least-measured input
  in the whole system.
- It needs no strategy outcomes, so it does not consume or contaminate development data the way a
  third hypothesis test would.
- It helps every future hypothesis, including the deferred gap-down candidate if that resumes.
- It touches no validation or final data and places no orders.

Limits to state up front:
- **Spread only:** quotes show the spread, not real slippage. Slippage needs actual real-money fills (paper fills are simulated and cannot establish it; clarified 2026-11-11), and
  placing orders is outside the current rules.
- **Provisional until the quote questions are answered:** the timestamp clock, the `?` condition
  code, and whether the bid/ask are the consolidated best quote (questions A1-A5 in
  `feasibility/execution_data/ALPACA_SUPPORT_REQUEST_DRAFT.md`). Sending that draft is the owner's
  decision. It also remains the only way to resume the gap-down candidate.
- **Owner approval comes first:** the pre-registration (dates, windows, request cap) needs the
  owner's approval before any download.
- **It reopens nothing:** it does not reopen experiment 001 or 002, and no result from it can
  change their verdicts.

Not recommended right now:
- **A third strategy on 2016-2021 SPY:** it would run into the same cost wall and the
  contamination noted above.
- **Rerunning 001 or 002 with lower costs:** that would be after-the-fact rescue of closed
  experiments.
