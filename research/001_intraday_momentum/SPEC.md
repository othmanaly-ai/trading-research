# Experiment 001: Intraday momentum in SPY (specification)

Spec version: 1.2. Version history:
- 1.0: approved 2026-11-03.
- 1.1: adds the section 17 implementation clarifications.
- 1.2: section 17 item 7, how the daily loss limit handles unrealized losses.

The strategy registry records this version and the file's hash. No real data
had been seen when any of these versions was written.

**Status: APPROVED by owner on 2026-11-03 for D2-D10 (proposed defaults accepted).
D1 (risk limits and setup answers) is still open. Implemented and tested on
synthetic data only. Not run on real data.**
No market data has been retrieved yet (no Alpaca keys in this project), so no
statement below about behavior or returns is a measured result.

This is an experiment to test whether an edge exists after costs. It is not an
investment recommendation, and it assumes no edge until the evidence shows one.

---

## 1. Candidate hypotheses

All three can in principle be tested with Alpaca historical bars (SIP feed,
1-minute and daily, available since 2016 per Alpaca's docs; access not yet
verified for this account).

### H1. Intraday momentum: the first half hour predicts the last half hour

- **Idea.** If SPY is up from yesterday's close to 10:00 ET, buy at 15:30 and
  sell at the close; if down, sell short. Published for SPY over 1993-2013
  (Gao, Han, Li & Zhou, *Market Intraday Momentum*, J. Financial Economics, 2018).
- **Why it might work.** Late-informed traders act on morning news near the
  close, and some funds and option dealers have to rebalance in the same
  direction as the day's move in the final half hour.
- **How it could fail.** Published effects often weaken once known. The effect
  may live only in high-volatility regimes. The expected move per trade is
  small, so a few basis points of cost can erase it.
- **Data.** SPY 1-minute bars plus daily closes. Available from Alpaca in
  principle; not yet verified.
- **Frequency and execution.** At most 1 trade per day, held about 30 minutes.
  Entry and exit times are fixed, so there is no stop/target ambiguity in the
  core rule. Sensitivity: low spread (SPY), but the exit price near the close
  matters.
- **Complexity and limits.** Very low: one signal, one instrument, two fixed
  times. Limit: one instrument gives only ~250 observations per year, and its
  days are not independent across market regimes.

### H2. Opening range breakout (ORB)

- **Idea.** Record the high and low of the first 15-30 minutes. Buy a break
  above the high, or sell short a break below the low, with a stop at the other
  side of the range and an exit at the close.
- **Why it might work.** The open absorbs overnight news. A break of the
  opening range can signal continued one-sided order flow.
- **How it could fail.** In choppy markets, false breakouts trigger stops
  repeatedly. Stop orders slip in fast markets.
- **Data.** 1-minute bars; we have it in principle.
- **Frequency and execution.** 0-1 trades per day per symbol. Highly
  sensitive to execution: entries happen exactly when price is moving fast.
- **Complexity and limits.** Moderate. Several free parameters (range length,
  stop, target, filters) invite overfitting. 1-minute bars cannot tell
  whether the stop or the target was hit first inside a bar (section 9).

### H3. Overnight gap fade in large stocks

- **Idea.** When a stock opens far from yesterday's close, bet on a partial
  move back toward the close during the morning.
- **Why it might work.** Overnight overreaction and thin pre-market liquidity.
- **How it could fail.** News-driven gaps (earnings, guidance) often keep
  going. Halts and wide opening spreads are common.
- **Data.** Needs news or earnings dates to separate news gaps from no-news
  gaps (we don't have this). Also needs a point-in-time list of which stocks were
  large and listed on each past date. We don't have that, and using today's list
  creates **survivorship bias** (only the winners that still exist are tested).
- **Frequency and execution.** Several trades per day across stocks. Very
  sensitive to opening spreads and auction prices.
- **Complexity and limits.** Highest. The missing data makes an honest test
  impossible right now.

### Recommendation: start with H1

H1 is the most testable: fixed decision times (no intra-bar ordering
problems), one very liquid instrument that has existed through the whole data
period (no survivorship problem), one signal with no free parameters in the
primary version, and data the free plan should cover. Its main weakness is a
small edge relative to costs and the risk that the published effect has
faded. Both are exactly what the test is meant to measure.

---

## 2. Universe

- **Primary:** SPY only (S&P 500 ETF). It traded continuously throughout 2016
  to the present and is among the most liquid US-listed securities.
- **Optional extension (decision D2):** QQQ, IWM, DIA, tested as separate
  pre-declared variants. All existed for the whole period, so a fixed list
  carries no survivorship bias. They are highly correlated with SPY, so they
  count as one risk bucket, not diversification.
- **Excluded for now:** single stocks. We have no point-in-time listing data,
  so any stock list chosen today would be biased.

## 3. Session, time, bars

- Calendar: `exchange_calendars` XNYS. Holidays are skipped. On early-close
  days (13:00 ET close), all times shift relative to the close (below).
- Timezone: decisions in America/New_York; data stored in UTC plus ET.
- Bars: SIP 1-minute bars, regular session only. A bar stamped `t` covers
  `[t, t+1min)` and is only known after `t+1min`.
- Prices: request both `adjustment=raw` and `adjustment=all` (decision D7).
  Returns use adjusted prices so that dividend ex-dates do not create fake moves.
  Costs that are fixed in cents use raw prices.

## 4. Signal (formulas)

For session *d* with close time *C* (16:00, or 13:00 on early-close days):

- `P_prev` = previous session's official close (daily bar close, adjusted).
- `P_10` = close of the 09:59 ET bar (last trade before 10:00), adjusted.
- `r1 = P_10 / P_prev - 1`. Known at 10:00:00 ET at the earliest.
- Direction: `+1` (long) if `r1 > 0`, `-1` (short) if `r1 < 0`, no trade if
  `r1 == 0` or if any input is missing.
- Primary version has **no threshold** and no other filter (no tuning).

Decision D3: the published version measures from the previous close. An
alternative measures from today's open (excludes the overnight gap). Only the
primary is run first; the other is a logged variant.

## 5. Entry

- Decision time: `C - 30 min` (15:30 ET; 12:30 on early-close days). All
  inputs are known well before this, so no future data is used.
- Order: market order at the decision time (paper only, later milestone).
- **Simulated fill:** open of the bar starting at `C - 29 min` (one-minute
  execution delay), plus costs (section 10). Sensitivity run: open of the
  `C - 30 min` bar (no delay).
- If that bar is missing, use the next bar's open within 2 minutes; otherwise
  no trade that day (logged as "skipped: no entry price").

## 6. Exit, stop, expiry, end of day

- **Time exit:** close the position at the close.
  - Base simulation: market order at `C - 1 min`, filled at the close of the
    `C - 1 min` bar, minus costs.
  - Alternative (decision D4): market-on-close order filled at the official
    close (daily bar close).
- **Protective stop (decision D5):** stop distance `S = 2 x sigma30`, where
  `sigma30` is the standard deviation of the last-30-minute return over the
  previous 20 sessions (known before entry). It exists to cap damage on rare
  extreme days, not to improve returns.
  - Stop fill: the stop price, or the bar open if the bar opened beyond the stop
    (a gap through the stop), minus costs.
- **No profit target** in the primary version.
- **Expiry:** an entry order not filled within 2 minutes is cancelled and the day
  is skipped. The stop is a day order, cancelled at the time exit.
- **End of day:** always flat by the close. Never hold overnight.

## 7. Sizing, exposure, loss limits

Risk numbers are **placeholders** until the owner answers the setup questions
(D1). The software enforces whichever values are agreed.

- `E` = account equity at the decision time.
- Shares = floor of the smallest of:
  - `R x E / S`: risk budget R% of equity if the stop is hit. Placeholder R = 0.5%.
  - `L x E / price`: notional cap. Placeholder L = 1.0, meaning no leverage.
  - `1%` of the median 1-minute volume over 15:00-15:29 that day (participation cap).
- Concurrent positions: 1 (SPY only). With the extension (D2), at most one
  position per ETF, and the total risk across all ETFs is capped at R.
- Daily loss limit: placeholder 1% of equity. With one trade per day this
  rarely triggers; it stays in code for later multi-symbol variants.
- Drawdown kill switch: if equity falls D% (placeholder 5%) below its peak,
  no new trades until the owner reviews. In the backtest this is reported as a
  breach.
- Short selling needs a margin account. Decision D6 is long-and-short versus
  long-only.

The risk check has veto power. A failed risk or data check blocks the trade,
and no other component can override it.

## 8. Gaps, halts, partial fills, missing prices, corporate actions

| Situation | Rule |
|---|---|
| Overnight gap | Part of the signal by design (r1 includes it). |
| Missing `P_prev` or `P_10` bar | No trade. Logged. |
| Data check failure for the day (duplicates, invalid OHLC, gaps in 15:00-16:00) | No trade. Logged. |
| Market-wide halt | Level 1 and 2 circuit breakers do not halt trading after 15:25 ET. A Level 3 halt closes the market for the day: the simulated exit moves to the next session's open and the trade is flagged. |
| Partial fill | Size is capped by participation, so the base case assumes a full fill. Stress test: fill only 50% of the order. |
| Failed order | Stress test: 2% of entries randomly fail (day skipped); 2% of exits fill one minute late at the next bar's close. |
| Missing exit bar | Use the last bar at or before the close; flag the trade. |
| Dividends | Handled by adjusted prices (section 3). |
| Splits | SPY had none in the period; the adjusted series handles any. |

## 9. Future-data leakage and same-bar ambiguity

- Every value used at time T must come from bars that ended at or before T.
  A bar stamped 15:29 ends at 15:30:00, so it can inform a 15:30 decision, and
  the fill comes from a later bar.
- The code will enforce this by passing only past bars to the signal function,
  plus a test that shuffles future bars and checks the signals don't change.
- **Same-bar stop/target ambiguity:** a 1-minute bar shows only its open, high,
  low and close, not the order of trades. If a stop and a target both fall
  inside one bar's range, we cannot know which was hit first. Rule: **assume
  the stop was hit first** (the pessimistic choice).
  - The primary H1 rule has no target, so this only matters for variants that
    add one.
  - The same pessimism applies to the entry bar: a stop touched within the
    entry bar counts as hit.

## 10. Cost assumptions (to be checked against data)

| Item | Base | Stress |
|---|---|---|
| Commission | $0 (Alpaca's stated stock commission) | $0 |
| Half-spread, per side | 0.5 bp | 1 bp |
| Slippage beyond spread, per side | 0.5 bp | 2 bp |
| Regulatory sell fees (SEC Section 31, FINRA TAF) | parameter; look up current rates before running | 2x base |
| Execution delay | 1 minute | 2 minutes |

- **Round trip, base:** about 2 bp. **Round trip, stress:** about 6 bp,
  plus a 10 bp "severe" run.
- Before backtesting, measure SPY's actual quoted spread at 15:30 and 15:59 on
  a sample of days using Alpaca historical quotes, and replace the 0.5 bp guess
  with the measured value.
- A 1 bp cost equals 0.01%. On $10,000 that is $1.

## 11. Baselines (same window, same exposure, same sizing)

1. **Always long:** long SPY every day from entry to close, same sizing and
   stop. This tests whether the signal adds anything beyond the average
   last-half-hour drift.
2. **Random direction:** 10,000 runs with coin-flip direction on the same days.
   The strategy's net result is compared to this distribution (a permutation
   test).
3. **No trade:** zero return. The strategy must beat doing nothing after costs.

## 12. Periods (chronological, fixed before any data is seen)

| Period | Dates | Purpose | Sessions (XNYS calendar) |
|---|---|---|---|
| Development | 2016-01-04 to 2021-12-31 | Build, debug, try logged variants | 1,511 (12 early closes) |
| Validation | 2022-01-03 to 2024-06-28 | Check variants promoted from development | 625 (3 early closes) |
| Final test | 2024-07-01 to 2026-10-30 | **Run once** for the single chosen version | 587 (6 early closes) |
| Forward paper | after the final test | Later milestone, paper only | |

- Lookback windows such as the 20-day `sigma30` may use days before a
  period's start. That is past data, so it is allowed.
- Software lock: the backtest refuses final-test dates unless run with an
  explicit `--final-test` flag. The run is recorded in an append-only log, and
  a second run is flagged in every report.

## 13. Variant accounting

- Every run on any period is appended to `research/001_intraday_momentum/variants.csv`.
  Fields: id, timestamp, git commit, parameters, period, metrics, decision.
- Budget (decision D9): at most 10 variants on development, at most 2 promoted
  to validation, exactly 1 to the final test.
- Reports state how many variants were tried. The more variants tried, the
  higher the bar a winner must clear, because the best of many random tries
  looks good by chance.
- If the final test fails, the experiment is rejected. It is not tweaked and
  re-tested on the same final data.

## 14. Evaluation criteria (fixed before running)

Reported for every run:

- Net total and average return per trade after costs (base, stress and severe).
- Maximum drawdown: the largest drop from a peak in equity.
- Exposure: share of market time in a position, and average notional.
- Trade count, plus days skipped and why.
- Average win, average loss, profit factor (gross wins / gross losses), win rate.
- Return per unit of risk (annualized Sharpe ratio) with a bootstrap 95% confidence interval.
- Results by year.
- Concentration: net result with the 10 best trades removed, and the share of
  profit from the top 10 trades.
- Parameter neighbors: entry time ±15 minutes, stop multiplier 1.5 / 2.5.

**Pass rules for the final test** (all must hold; specific numbers decided in D8):

1. Net return > 0 at base costs, and not clearly negative at stress costs.
2. Net result better than the always-long baseline and above the 95th
   percentile of random-direction runs.
3. Maximum drawdown within the agreed limit D.
4. Still positive with the 10 best trades removed.
5. Same sign for the parameter neighbors (not a knife-edge result).

**Why win rate alone is not enough:** a strategy can win 70% of the time and
still lose money if its losses are much larger than its wins. Another can win
40% of the time and make money because its wins are larger. What matters is
average win x win rate minus average loss x loss rate, after costs.

## 15. Roles (performed by one model, Claude, as checklists)

These are analytical roles, not independent agents. Agreement between them is
not independent confirmation, because they share one model and the same data.

| Role | Input | Output | Can veto? | Rejects when |
|---|---|---|---|---|
| Data integrity (`trading/validate.py`) | Raw bars | Pass/fail per day | Yes | Any structural failure or missing required bar |
| Strategy spec | This document | Signals | No | n/a |
| Backtest and costs | Signals, bars, cost table | Trades, equity curve | No | n/a |
| Overfitting audit | variants.csv, period log | Promotion decision | Yes | Budget exceeded, final test reused, or result fails neighbor/concentration checks |
| Risk | Proposed trade, equity | Approved size or block | **Yes (always wins)** | Any limit exceeded, or data not passed |

Execution reliability (duplicate orders, broker position reconciliation) and
ongoing monitoring are later milestones. They don't exist yet.

## 16. Unresolved decisions for owner review

D2-D10 below were accepted as proposed on 2026-11-03. Changing any of them
later counts as a new variant and must be logged (section 13).

| # | Decision | Proposed default |
|---|---|---|
| D1 | Country, experience, paper balance, intended real capital, data budget; risk per trade R, daily limit, drawdown limit D | **OPEN.** Placeholders R=0.5%, daily 1%, D=5% until answered |
| D2 | SPY only, or add QQQ/IWM/DIA | SPY only first |
| D3 | Signal from previous close (published) or from today's open | Previous close |
| D4 | Exit at 15:59 market or market-on-close | 15:59 market (base), MOC as sensitivity |
| D5 | Include the protective stop | Yes, 2 x sigma30 |
| D6 | Long and short, or long only | Long and short (needs margin account) |
| D7 | Fetch both raw and adjusted bars | Yes |
| D8 | Numeric pass thresholds (e.g. minimum Sharpe lower bound) | Pass rules in section 14 as written |
| D9 | Variant budget | 10 / 2 / 1 |
| D10 | Period boundaries | As in section 12 |

## 17. Implementation clarifications (2026-11-03, before any data was seen)

Choices made while coding. No results existed when they were made.

1. **Data-check window (section 8).** The "gaps in 15:00-16:00" check would
   look at bars after the 15:30 decision, which is future data. The engine
   checks only the bars known at the decision: structural checks on the day so
   far, and no missing minute in 15:00-15:29. Problems after entry are handled
   by the exit rules (missing exit bar, halt).
2. **Sizing price (section 7).** Shares are computed from the last close known
   at the decision (the 15:29 bar), not from the later fill price. The stop
   is then placed relative to the actual fill.
3. **Late-exit stress (section 8).** A "late" exit fills at the official close,
   because no regular-session bar exists after the 15:59 bar.
4. **"Not clearly negative at stress costs" (pass rule 1).** Implemented
   strictly as stress-cost net return >= 0. Loosening it must be decided
   before any validation run.
5. **Random baseline (section 11).** It uses the days on which both a long and
   a short trade were possible, with the drawdown kill switch off, so that
   every random run trades the same days.
6. **Period lock and budget (sections 12-13).** Enforced in `trading/experiment.py`:
   - The final period refuses to run without `final_test=True`.
   - Validation requires a prior development run of the same variant, and the
     final test requires a prior validation run.
   - New variants beyond the budget are refused.
   - Every run is appended to `variants.csv` (tracked by Git).
   - Full reports go to `results/experiment_001/` (git-ignored).

7. **Daily loss limit with unrealized losses (v1.2, section 7).**
   - **Check:** after every completed 1-minute bar, the open position is marked
     at that bar's close against the estimated entry fill.
   - **Breach:** if the loss reaches the daily limit (a fraction of start-of-day
     equity), the position exits at the **next bar's open**, the same one-minute
     delay as entries. If there is no later bar, it exits at the breach bar's close,
     and the trade is flagged.
   - **Priority:** a stop touched inside a bar takes priority over a breach marked
     at that bar's close.
   - **Effect:** with the stop at 2 x sigma30 and 0.5% risk sizing, the limit
     normally acts only on gaps or halts. It exists so the control is enforced in
     code, not just written down.

**Prerequisite for any implementation:** paper keys in `.env`, then a
successful `python -m trading.verify_data_access`, then a separate SPY
2016-2026 download and quality report. Order submission stays disabled
throughout.
