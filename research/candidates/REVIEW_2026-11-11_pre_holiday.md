# Review of the pre-holiday proposal, and one more-frequent alternative (decision paper)

Written 2026-11-11 at the owner's request. D1 is **not** approved.

Nothing in this review involved:
- computing a strategy return or any SPY return;
- reading protected (validation or final) data;
- running an experiment.

The dry run, the approvals file and the order guard are unchanged.

**Labels used in this review:**
- **[Published]:** from a cited source. Excerpts only were read, not full papers.
- **[Calculation]:** arithmetic from stated inputs.
- **[Assumption]:** an input chosen without our data.
- **[Speculation]:** an untested belief.

## 1. Does the published pre-holiday evidence cover our interval? No.

- **[Published] Close to close, not open to close.**
  - The classic studies use **daily close-to-close** index returns: Ariel (1990, *J. Finance*, 1963-1982) and
    Lakonishok and Smidt (1988).
  - A pre-holiday "day" there runs from the previous session's close to the pre-holiday close. It **includes the
    overnight move and the opening auction**, which our rule (09:31 open to the close) excludes.
  - I found no source that splits the pre-holiday return into overnight and intraday parts.
- **[Published] Part of the old effect may not be tradeable.** A summary of the 1975-1990 evidence says the
  pre-holiday return "may, in part" reflect closing prices moving from the bid to the ask. A bid-to-ask shift in
  the closing print is a measurement effect, not a price move a trader could capture.
- **[Published] The excluded part is where US index returns have tended to accrue.**
  - The New York Fed staff report "The Overnight Drift" (SR 917) finds that more than half of the S&P 500 return in
    its sample was earned outside regular trading hours.
  - Our own record agrees in direction: the 002 baseline "always long 10:01 to close" lost 1.30% at base costs over
    1,424 development trades (`002_opening_range_breakout/RESULTS_development.md`, D3). That is about +0.5 bp gross
    per trade [Calculation from the recorded figures], essentially zero.
- **[Published] The effect has declined:** Chong, Hudson, Keasey and Littler (2005).

**Conclusion:** the proposal's statement that published evidence motivates H2 was **overstated**. The evidence
concerns a different interval, an older period, and possibly a measurement artefact. A test of our open-to-close
rule would not replicate any published result.

## 2. Basis of the three statements in the proposal

| Statement | What it actually rests on | Verdict |
|---|---|---|
| "a hypothesized move of tens of bp, many times our cost assumptions" | Ariel's 9-14x the normal-day mean, on close-to-close 1963-1982 data. A normal-day mean of a few bp times 9-14 gives tens of bp. | **[Speculation]**, and it transfers the size from the wrong interval and the wrong era. **Withdrawn.** There is no basis for any expected size of our open-to-close effect. |
| "detectable only at about 20-34 bp" | **[Calculation]** MDE = (1.645 + 0.842) × σ / √n, with n = 53, 80% power, one-sided 5% (see below) | The arithmetic is correct; the inputs are assumptions. **Kept, relabelled.** |
| "about $90 a year" | **[Calculation]** $4,943 position × 20 bp × 9 trades = $89 gross. At base costs, (20 − 2.3) bp gives $79; at stress, (20 − 6.6) bp gives $60. | It **assumes** an effect exactly at the detectable size, which is **[Speculation]**. Kept only as "even a detectable effect is worth very little at these limits". |

**Inputs and assumptions behind the detectable-effect (MDE) figures:**
- **[Assumption]** σ, the standard deviation of one trade's open-to-close return, is 0.6-1.0%. It is **not measured
  from our data**; measuring it would mean computing the returns under test.
- **[Assumption]** Trades are independent with roughly normal averages.
- **[Assumption]** A plain mean test. Our actual gate is a percentile against random sessions, whose power is
  similar but not identical.
- The figures detect **gross > 0**. Passing the stress gate needs a gross effect of about **6.6 bp + MDE**.

## 3. Can 53 trades, and about 9 a year, produce useful evidence in practical time? No.

[Calculation, same assumptions]

| Sample | Trades | Smallest reliably detectable gross effect (σ 0.6 / 0.8 / 1.0%) |
|---|---|---|
| Development 2016-2021 | 53 | 20.5 / 27.3 / 34.2 bp |
| Validation 2022-2024H1 | 25 | 29.8 / 39.8 / 49.7 bp |
| Final 2024H2-2026-10 | 22 | 31.8 / 42.4 / 53.0 bp |
| Shadow observation, per year | about 9 | about 51-83 bp after one year |

- **Held-out tests:** validation and final can confirm only a very large effect. A real but modest effect would
  most likely fail them, and each held-out period can be spent only once.
- **Shadow trading:** accumulating 53 live trades, as many as development, takes **about 6 years**.
- **Verdict:** H2 cannot be "practically testable" in the sense the goal needs.

## 4. How the 2% stop relates to the risk limits (correction)

The engine sizes positions with `trading/risk.py::size_position`, called from `trading/engine.py`.

**Inputs:**
- Equity E = $100,000.
- Stop distance d, as a fraction of the decision price.
- Modeled round-trip cost c per share: 2 × (half-spread + slippage) + sell fee, at the cost level of that run.

**The four caps (shares are rounded down; the smallest cap binds):**
- **Risk:** 0.10% × E ÷ (d + c) per share, because the limits say risk includes costs.
- **Notional:** 5% × E ÷ price.
- **Gross exposure:** 10% × E ÷ price. Never smaller than the notional cap with one position.
- **Participation:** 1% of median minute volume. Never binding for SPY at about 100 shares.

**Where the risk and notional caps meet [Calculation]:** they are equal when d + c = 0.001 ÷ 0.05 = 2.00%.

| Cost level | c | Largest stop at which the notional cap binds | Position with a 2.0% stop |
|---|---|---|---|
| base | 2.3 bp | 1.977% | $100 ÷ 2.023% = **$4,943** (risk cap binds) |
| stress | 6.6 bp | 1.934% | $100 ÷ 2.066% = **$4,840** |
| severe | 9.6 bp | 1.904% | $100 ÷ 2.096% = **$4,771** |

**What this means:**
- **Correction:** the proposal's statement that 2.0% is "the widest stop at which the 5% cap binds" was **wrong**. At
  2.0% the risk cap binds at every cost level, so the position also shrinks as the assumed cost rises.
- **A limit-derived choice:** a stop of **1.90%** makes the notional cap bind at all three cost levels, so all three
  cost runs hold the same position (about $5,000). That keeps the cost comparisons like-for-like.
- **What the limit does not cover:**
  - **The 0.10% risk ceiling is a plan, not a guarantee.** The model fills the stop at the stop price plus the
    modeled slippage. A bar that opens below the stop fills at that open, so a real loss can exceed $100.
    `acceptance_limit` refuses an entry whose own price gap would already break the risk budget.
  - **Stop slippage in fast markets is unmeasured.** The 0.5-2.5 bp slippage assumptions come from no fills.
  - **For SPY a 1.9-2% intraday stop rarely triggers [Assumption].** In practice it sets the position size, and
    protects mainly against crash days.

## 5. One more frequent alternative our data can honestly evaluate

**H4: intraday continuation in SPY.**
- **Rule:** if yesterday's session rose from its 09:31 open to its last regular close, buy today at the 09:31 open
  and sell at today's last regular bar. Long-only, one trade per signal day, flat overnight.
- **Data:** stored development SIP bars only.

**Why it is worth testing (not why it would work):**
- **[Published]** Intraday returns predicting later intraday returns positively, and overnight returns predicting
  intraday returns negatively, are reported:
  - for the cross-section of US stocks (Lou, Polk and Skouras, "A tug of war", *J. Financial Economics*), at
    roughly monthly horizons;
  - and in the New York Fed overnight-drift report for S&P 500 futures.

  I have **not** verified the index, the daily horizon or the period from full texts. Applying it to SPY day to
  day is a **[Speculation]**: a hypothesis, not a replication.
- **[Speculation]** Mechanism: professional, intraday clienteles might trade persistently day to day, while the
  overnight move belongs to a different clientele.

**Checked against what we have examined:**
- **001 used a different variable.** Its r1 ran from the previous close to 10:00, so it included the overnight gap,
  which the literature says predicts the opposite way. The previous day's open-to-close return has **never been
  computed** in this project.
- **"Down mornings" and the gap-down candidate** are overnight- or morning-conditioned, so there is no overlap.
- **Contamination:** low but real. We know the unconditional intraday drift in development is about zero (the 002
  baseline above), and the 001/002 runs contained these days.
- **Signal frequency was deliberately not counted.** Counting it would mean computing the very returns under test.
  Roughly half of sessions is an **[Assumption]**, about 750 development trades.

**Detectable effect [Calculation, same assumptions]:**

| Sample | Trades (assumed half) | Detectable gross effect (σ 0.6 / 0.8 / 1.0%) |
|---|---|---|
| Development | about 750 | 5.4 / 7.3 / 9.1 bp |
| Validation | about 156 | 11.9 / 15.9 / 19.9 bp |
| Final | about 140 | 12.6 / 16.8 / 21.0 bp |
| Shadow, 6 months | about 60 | 19.3 / 25.7 / 32.1 bp |

**Its weakness:**
- The detectable effect is **about the size of the stress cost (6.6 bp)**.
- Passing the stress gate reliably needs a gross effect of about **12-16 bp**, an edge on the scale of experiment
  002's (+2.3 bp gross), times five or more.
- A plausible small effect would therefore most likely give "passes at base, fails at stress". That is the 002
  outcome, and under our unchanged rules it is a **FAIL**.
- The result would hinge on cost assumptions that are still unmeasured: spread waits for Alpaca's answers, and
  slippage waits for fills.

## 6. Comparison

| | H2 pre-holiday | H4 intraday continuation |
|---|---|---|
| Published evidence for **our** interval | None (it is close-to-close, older, partly a measurement effect) | None directly. Related evidence on other horizons and instruments, unverified. |
| Development trades | 53 | About 750 (assumed) |
| Detectable effect, development | 20-34 bp | 5-9 bp |
| Practical forward test | No (about 6 years for 53 trades) | Yes (about 60 trades in 6 months) |
| Dependence on unmeasured costs | Low, but only because only huge effects are detectable | **High**: the detectable effect is about the stress cost |
| Free parameters | None | None in the primary rule (sign threshold 0; fixed entry and exit) |
| Contamination | Low | Low, plus the known zero unconditional drift |
| Data needed | Stored | Stored |

## 7. Recommendation

1. **Do not approve H2 (D1).** It fails the "practically testable" goal (about 9 trades a year). Its published
   motivation is for a different interval. Recorded as **NOT RECOMMENDED** in its `STATUS.json`; the proposal is
   kept with a correction notice.
2. **H4 is the better research path of the two, but it is not justified as the very next step.** Its verdict would
   most likely be decided by the cost assumption.
3. **Do first:** reduce the cost uncertainty that decided 002 and would decide H4.
   - **[Owner decision]** Send the Alpaca quote questions (`feasibility/execution_data/ALPACA_SUPPORT_REQUEST_DRAFT.md`).
     Only you can send it.
   - With written answers, the pre-registered spread measurement in `FAILURE_COMPARISON_001_002.md` can run.
4. **If you prefer to proceed now:** H4 can still be run honestly under the **unchanged** rules (stress net ≥ 0,
   95th percentile against random sessions, 10-best removal, neighbours, 3% drawdown). You would have to accept in
   advance that "base pass, stress fail" is recorded as FAIL and closes it.
   - A spec would need: the 1.90% stop (section 4); neighbours of entry 10:00, stop 1.5% and stop 3.0%; and
     benchmarks of random sessions (same count, stratified by year), always long, and no trade.
   - Using the previous day's **close-to-close** return as the signal would be a **different** hypothesis (it
     includes the overnight move), not a neighbour.
5. **Neither path is justified as a route to meaningful profit under the current limits.** About $5,000 per
   position means even a real edge is worth tens to a few hundred dollars a year. The limits are not proposed to
   change.

## 8. Decisions prepared for you

| # | Decision | Options |
|---|---|---|
| R1 | H2 pre-holiday | Reject (recommended) / keep as a deferred idea |
| R2 | Next research step | (a) Send the Alpaca quote questions first, then the spread measurement (recommended). (b) Approve drafting an H4 spec now, under the unchanged rules. (c) Neither: stop strategy research until costs are measured. |
| R3 | If (b): the stress gate stays decisive, and base-pass / stress-fail is a FAIL | Confirm (required, not a choice to weaken) |
| R4 | If (b): minimum executed trades for a verdict, and validation/final pass rules | Your thresholds |

## 9. Owner decisions and later corrections (2026-11-11, recorded after the review)

**R1: pre-holiday candidate REJECTED by the owner.**
- `pre_holiday_session/PROPOSAL.md` (with its correction notice) and this review are kept unchanged as the record.

**R2: priority is resolving the Alpaca quote-data questions.**
- The message is final in `feasibility/execution_data/ALPACA_SUPPORT_REQUEST_DRAFT.md`.
- Only the owner sends it.

**Withdrawn: the 1.90% stop suggestion (section 4, section 7 item 4).**
- Choosing a stop so that every cost scenario holds the same position is a convenience, not a rationale.
- Per the owner, any strategy rule needs an independent rationale and a locked specification.
- The arithmetic in section 4 stands as a description of how sizing works. It recommends no stop value.

**Correction: the evidence cited for H4 (section 5).** The primary papers were checked:
- **Lou, Polk and Skouras ("A tug of war", J. Financial Economics; 22-page PDF):**
  - Instruments: individual US stocks (CRSP 1993-2013), international stocks, and 22 equity-index futures
    (1996-2016).
  - Definitions: the intraday return runs from the **VWAP of 9:30-10:00** (volume-weighted average price) to the
    close. The overnight return is imputed from close-to-close.
  - Signals are **one-month (or longer) past returns**, mostly **cross-sectional** sorts of stocks, with
    **monthly** holding periods.
  - Its only index-level test is time-series momentum across the 22 index futures, with monthly formation and
    holding. There, the **intraday component is -0.29% a month (t = -0.78)**, essentially zero, and the profit is
    overnight (+1.10%, t = 2.67).
  - The paper does **not** test a single index's previous-day intraday return predicting the next day's.
- **Boyarchenko, Larsen and Whelan ("The Overnight Drift", NY Fed Staff Report 917; S&P 500 futures 1998-2020):**
  - The sentence "intraday returns predict subsequent intraday returns positively" is the paper **citing Lou,
    Polk and Skouras for firm-level patterns**. It is not its own index result. **The review's section 5 was wrong
    to attribute it to this report for S&P futures.**
  - The report contains no previous-day intraday → next-day intraday test.
  - It states that its own overnight-drift strategy "is not profitable in practice" after transaction costs.
- **Gao, Han, Li and Zhou (2018, "Market intraday momentum")** concerns the same day (the first half-hour
  predicting the last half-hour). That is experiment 001's family (failed, contaminated), not a day-to-day rule.

**Evidence verdict on H4: NOT SUPPORTED by primary evidence.** The rule would be an extrapolation on three counts:
- from individual stocks to an index ETF;
- from a one-month cross-sectional signal to a one-day time-series signal;
- from monthly holding to a single session.

The closest index-level evidence (index futures, monthly) finds **no** intraday continuation. H4 is not
recommended for a spec. It remains an unapproved idea with no claim of support.

**Further corrections (2026-11-11):**
- **"Slippage waits for fills" (section 5):** this means **real-money** fills. Paper fills test order handling and
  Alpaca's simulated execution, but cannot establish real-world slippage.
- **"With written answers, the spread measurement can run" (section 7):** an Alpaca reply may clarify the historical
  quotes. It does not automatically validate every spread estimate or remove every data limitation.
