# Candidates for experiment 002 (PROPOSED: owner to choose; nothing implemented)

Constraints carried over: SPY only, long-only, no leverage, no overnight holds except
involuntary carries, the owner risk baseline (`OWNER_BASELINE_2026_11_03`), base, stress and
severe cost models, and the same development, validation and final periods. Validation and
final data stay untouched until a development pass.

## How much evidence there is

Neither candidate is supported by our own evidence. Experiment 001 showed only what does
**not** work: SPY's move from the previous close to 10:00 did not predict the last 30
minutes (correlation +0.02). Both candidates rest on external reasoning, so treat them as
**speculative**.
- B also has a weak, statistically insignificant hint in development data that we have
  already seen.
- That makes B's development result partly contaminated, which is a weakness, not support.

What the diagnosis does motivate is to **change the information set and the horizon instead
of tuning r1**:
- Costs (about 2.3 bp per round trip) were about 64% of experiment 001's loss, because a
  30-minute hold produces small moves.
- Longer holds give any real effect more room to exceed costs.

## A. Long-only 30-minute opening-range breakout (recommended)

**Rationale (speculative, external):** after the open, large participants work orders over
hours. A break above the first half hour's high may mark one-sided buying that persists for
the rest of the day (order-flow persistence and trend-following behavior). Practitioner
literature claims such effects; we have not verified those claims.

**How it differs from 001:**

| | 001 | A |
|---|---|---|
| Signal | Prior close to 10:00 return | Today's intraday price action (break above the morning high) |
| Entry time | Fixed (15:30) | Event-driven (10:00 to 15:00) |
| Hold | 30 minutes | Hours (median breakout 52 minutes after the open, so about 5 hours) |
| Stop | 2 x sigma30 | Structural (morning low) |

**Rules (draft for spec v1.0 of experiment 002):**
- **Data:** SPY SIP 1-minute bars, adjustment `all` (already stored for development).
- **Opening range:** H = high and L = low of the 09:30-09:59 ET bars, known at 10:00.
  Requires all 30 bars; otherwise no trade.
- **Signal:** the first completed bar from 10:00 to close - 60 min whose close is above H.
  One entry per session at most.
- **Entry:** market order at the next bar's open (one-minute delay), plus costs. Same 2-minute
  fallback and data checks as 001.
- **Stop:** L, filled intrabar. A bar opening below L fills at its open. Pessimistic rule:
  a stop touched in the entry bar counts.
- **Exit:** time exit at the close of the 15:59 bar (C - 1 on early-close days). No profit
  target, so no target/stop ambiguity.
- **Sizing:** 0.1% risk including costs over the distance (entry - L), capped at 5% notional,
  so about $5,000.
- **Risk and halts:** daily, drawdown, halt and carry rules exactly as 001 v1.3.

**Sample:** about 1,059 development trades (70% of sessions trigger).

**Should fail when:**
- Markets are choppy or mean-reverting after the open (false breakouts followed by stops).
- Breakout entries pay more than modeled, because buying into a rising price costs more spread
  and slippage.
- The effect, if it ever existed, has been arbitraged away by 2016-2021.

**Cost sensitivity:** about one round trip on 70% of sessions, similar turnover to 001, but
over a longer hold.
- It is **most sensitive to entry slippage**, since entries happen in motion.
- Stress (6 bp) and severe (9 bp) runs matter. The pass rule should require stress net >= 0,
  as in 001.

**Baselines (predefined):**
1. **No trade.**
2. **Random-time long:** on the same breakout sessions, enter long at a uniformly random minute
   between 10:00 and close - 60, with the same stop rule (morning low) and exit. 10,000 runs.
   This controls for simply being long in the afternoon on those days.
3. **Always long 10:01-to-close every session,** with the same stop. This has about 1.4x the
   exposure, which the report states.

**Falsification (predefined, same structure as 001):** the hypothesis is rejected if, on
development data, any of these hold:
- net after base costs <= 0, or stress net < 0
- below the 95th percentile of the random-time baseline
- not positive after removing the 10 best trades
- a neighbor flips sign (opening range of 15 or 45 minutes, or the stop at the range midpoint)
- drawdown is greater than 3%

## B. Long-only gap-down reversal (speculative, partly contaminated)

**Rationale (speculative, external):** large overnight declines may overshoot as
overnight sellers demand liquidity at the open; liquidity providers and value buyers may
then lift prices during the day (overreaction and liquidity-provision arguments).

**How it differs from 001:** it conditions on the overnight gap (open vs previous close), not
the close-to-10:00 move. It buys weakness instead of strength, and holds about 6 hours.

**Why the diagnosis touches it (a caution):** down-morning sessions (lowest r1 quintile)
averaged +2.46 bp in the last 30 minutes. That is not significant, and it was already seen,
so development data cannot test B cleanly. Only the untouched validation period could, and
that would spend it.

**Rules (draft):**
- **Signal:** the 09:30 bar's open is at least 0.5% below the previous official close. The
  0.5% threshold is a round number fixed now and will not be tuned.
- **Entry:** decision at 10:00, market order filled at the 10:01 open, plus costs.
- **Stop:** the 09:30-09:59 low, intrabar, with the same pessimistic rules.
- **Exit:** time exit at the close of the 15:59 bar.
- **Sizing, risk and halts:** as A.

**Sample:** only about **167 development trades** (11% of sessions). Over a ~6-hour hold,
the per-trade spread is large, so the test can detect only a large effect.

**Should fail when:** gaps reflect real news, so declines continue; or volatility regimes
(such as 2020) dominate the small sample.

**Cost sensitivity:** low turnover (11% of sessions). Entry is 30 minutes after the open, when
spreads are normal. It is less cost-sensitive than A, but much more sample-limited.

**Baselines:** no trade; random long 10:01-to-close on the same number of randomly chosen
sessions, with the same stop; always long 10:01-to-close (about 9x the exposure, stated).

**Falsification:** the same rules as A. Neighbors: gap thresholds of 0.3% and 0.7%; stop at
the 10:00 price minus the opening-range width.

## Recommendation

**Candidate A**, for testability, not expected profit:
- It has about 6x the sample of B.
- It isn't contaminated by what we have already seen.
- It uses only stored data.
- It has one fixed rule with no free threshold in the primary version.

Missing evidence that would strengthen either candidate: measured quoted spreads and
slippage around SPY breakouts (historical quotes), and an independent published
replication on post-2016 data.
