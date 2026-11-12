> **CORRECTION NOTICE (2026-11-11, same day): read `research/candidates/REVIEW_2026-11-11_pre_holiday.md` first.**
>
> Three statements in this proposal were wrong or overstated:
> 1. **The published evidence is for a different interval.** It uses close-to-close returns, which include the
>    overnight move and the open; our rule runs from 09:31 to the close.
> 2. **"Moves many times costs" was speculation** and is withdrawn.
> 3. **The 2.0% stop is not where the notional cap binds.** That point is 1.90-1.98% depending on the cost level; at
>    2.0% the risk cap binds.
> 4. **Sections 1 and 8 imply paper orders measure slippage.** They do not: paper fills test order handling and
>    simulated execution, and cannot establish real-world slippage. *(Added 2026-11-11; owner decision R1 rejected
>    this candidate.)*
>
> The recommendation is withdrawn: H2 is **NOT RECOMMENDED** (about 9 trades a year cannot be tested in practical
> time). The text below is kept unchanged as the record of what was proposed.

# Candidate: long SPY on pre-holiday sessions (PROPOSAL, not approved, not an experiment)

Written 2026-11-11.

**Status:**
- This is a proposal only. No strategy code exists for it, and no price or return data was looked at for it.
- It becomes experiment 003 only if the owner approves a `SPEC.md` built from section 4. Coding starts only after
  that approval ("spec first, code second").
- Nothing here suggests it is profitable. The published evidence (section 2) points toward a weak or vanished
  effect, so **the expected outcome is a failure**. The value of running it is a clean, cheap, honest test.

The Milestone 1 dry run is unaffected. Nothing here touches `trading/operations/`, the approvals file, the risk
limits or any lock. Orders stay disabled.

## 1. What research can proceed now, and what waits for Alpaca

The unanswered questions in `feasibility/execution_data/ALPACA_SUPPORT_REQUEST_DRAFT.md` (not sent) are about
**historical quote data**:
- the timestamp clock;
- the `?` condition code;
- whether the bid and ask are the consolidated best quote (NBBO);
- known corrections.

They do **not** affect SIP minute bars, which both closed experiments used.

| Work | Can it proceed now? | Why |
|---|---|---|
| A bar-based hypothesis on stored SPY development bars, priced with the existing base, stress and severe cost assumptions | **Yes**, after owner approval of a spec | Bars are documented and stored. Costs stay labelled assumptions. |
| Calendar-only preparation (event dates, trigger counts, power) | **Yes** (done today, section 6) | No prices, no outcomes |
| Fetching more **development-period** bars (for example other ETFs) | Yes in principle, but only as part of an approved spec | Bars are not affected by the quote questions. Every download is logged. |
| Measuring real spreads from historical quotes (a calibrated cost model) | **No: waits for Alpaca's answers** | Spread values depend on the quote semantics |
| The gap-down opening candidate | **No: waits** (DEFERRED_DATA_SEMANTICS) | Its 09:32 entry is spread-sensitive |
| Any strategy whose result depends on a spread measured at specific minutes | **No: waits** | Same reason |
| Slippage (as opposed to spread) | **No, not from data at all** | It needs real fills, so paper orders (Milestone 3), which are not authorized |
| Validation or final period data | **No** | Held out. Only after a development pass and an explicit owner decision. |

**Consequence for choosing a hypothesis:** prefer a rule that holds positions for hours, trades rarely, and expects
a move many times larger than the stress round-trip cost (6.6 bp), so that the unmeasured cost assumption cannot
decide the result. Experiment 002 failed exactly because its whole edge (+2.3 bp) was the size of the base cost.

## 2. Three hypotheses compared

All three are long-only, SPY or similar ETFs, intraday (flat at the close), under `OWNER_BASELINE_2026_11_03`.

| | H1: Scheduled FOMC statement days | H2: Pre-holiday sessions (recommended) | H3: Sector-ETF intraday relative strength |
|---|---|---|---|
| Rule in one line | Buy SPY after the open on scheduled Fed statement days, sell just before the 14:00 ET statement | Buy SPY after the open on the session before a regular exchange holiday, sell at the close | At 10:00, buy the sector ETF with the strongest move since the open, sell at the close |
| Why it might work (external, unverified) | The "pre-FOMC drift": US stocks rose about 0.49% in the 24 h before scheduled announcements, 1994-2011 (Lucca and Moench, 2015) | Old evidence that pre-holiday returns were many times the normal daily average (Ariel 1990; Lakonishok and Smidt 1988), often attributed to short covering and investor mood before closures | Intraday order flow and news may diffuse across sectors over hours, so relative strength might persist within the day |
| Published evidence on the recent period | **Against.** Kurov, Wolfe and Gilbert (2021, *Finance Research Letters*) report the drift "essentially disappeared after 2015". That is our development window. | **Mixed to against.** Chong, Hudson, Keasey and Littler (2005, *J. Int. Money and Finance*) document a decline of the effect, with reversals in some markets | **None found** for this exact intraday rule |
| Development trades (2016-2021) | 47 (48 scheduled minus 1 cancelled, 2020-03-18; dates verified on federalreserve.gov) | **53** (calendar count, section 6) | About 1,500 (one per session) |
| Hold | About 4 h 25 min | About 6 h 28 min (about 3.5 h on 6 early-close days) | About 6 h |
| Free parameters | Entry and exit minute (exit fixed by the 14:00 release) | **None in the primary rule** (entry and exit are fixed session points) | Many: universe, ranking window, rank-1 vs top-k, entry time |
| Cost sensitivity | Low: one round trip per event; the hypothesized move is tens of bp | Low: same | **High**: daily turnover on ETFs whose spreads we have **never** measured (only SPY spreads were sampled) |
| New data needed | None (stored SPY bars, plus an event list) | **None** (stored SPY bars, plus the exchange calendar already in the project) | 9-11 ETFs × 6 years of development bars, plus a per-ETF cost model |
| Contamination of our development data (`EXPLORATION_LOG.md`) | Low: FOMC days were inside the 001/002 runs but never separated or viewed | Low: the same, never separated or viewed | None for the ETFs. The 10:00 decision is close to the "morning range" family already used on SPY |
| Depends on Alpaca's quote answers? | No | No | **Effectively yes**: without measured ETF spreads, the cost assumption could decide the result |
| Main weakness | A test on 2016-2021 mostly repeats a published null result | Small sample: only effects of about 20-35 bp or more are detectable | Overfitting risk and unmeasured costs |

## 3. Recommendation: H2, pre-holiday sessions

H2 is recommended because it is the **cleanest available test**, not because it is expected to work:
- It has zero free parameters in the primary rule, so there is nothing to tune.
- It uses only data already stored, and needs nothing Alpaca has not answered.
- It is the least cost-dependent of the three: one round trip on 53 days, against a hypothesized move of tens of bp.
- Its development data is not contaminated by anything we have looked at.
- H1 is rejected because the published evidence already covers our development window and reports no effect.
  Testing it would mostly repeat that study.
- H3 is deferred because its result would rest on unmeasured ETF spreads, and its many design choices invite
  overfitting.

**Honest limits, stated before any data is seen:**
- **Power:** with 53 trades, the test can reliably detect only a large effect. Assuming an open-to-close standard
  deviation of 0.6-1.0%, that is about **20-34 bp** per trade (80% power, one-sided 5%). The standard deviation is an
  assumption, not measured from our data. A real but smaller effect would most likely be reported as a failure.
- **Dollars under the current limits are tiny:**
  - The 5% notional cap means about $5,000 per trade on $100,000.
  - A 20 bp edge is about $10 per trade, or about $90 a year on 9 trades.
  - Even a pass would be **evidence about a pattern, not an income source**.
  - The limits stay as they are. Changing them is an owner decision and is not proposed.
- **Third hypothesis on the same data:** 001 and 002 already used the 2016-2021 development data. Section 4.7
  addresses the multiple-testing risk.

## 4. Proposed experiment 003 (draft for a SPEC.md; not approved)

### 4.1 Data
- **Instrument and bars:** SPY, Alpaca **SIP** 1-minute bars, regular session, adjustment `all` (the bars already
  stored in `data/history/SPY/sip/all/`, with their manifest).
- **Calendar:** XNYS, `America/New_York` time.
- **Period:** development only, 2016-01-04 to 2021-12-31. Validation (2022-01-03 to 2024-06-28) and final
  (2024-07-01 to 2026-10-30) stay untouched until a development pass and an explicit owner decision.
- **No quotes, and no other symbols.**

### 4.2 Which sessions trade
- **Signal session:** session *d* is a signal session when the next weekday after *d* is a **regular** XNYS holiday
  (`regular_holidays` in `exchange_calendars`).
- **Excluded:** ad hoc closures (2018-12-05, 2025-01-09), since they are not a scheduled holiday.
- **Known in advance:** the calendar is published years ahead, so the signal has no look-ahead.
- **Count:** 53 development sessions. 6 are early closes (13:00).

### 4.3 Trading rules
- **Entry:** a market order filled at the **open of the 09:31 bar**, plus modeled costs. This avoids the opening
  auction print.
  - Data checks as in 002: valid structure and no missing minute up to the decision.
  - The same 2-minute fallback as 001/002; otherwise no trade, recorded with its reason.
- **Protective stop:** 2.0% below the entry price, filled intrabar. A bar opening below the stop fills at its open,
  and a touch in the entry bar counts (the pessimistic rule from 002).
  - Why 2.0%: it is the widest stop at which the 5% notional cap binds under 0.10% risk per trade. It is derived from
    the owner's limits, not tuned on data.
- **Exit:** at the close of the last regular bar (15:59, or 12:59 on early-close days).
- **Sizing:** 0.10% of equity at risk, including modeled costs, over the stop distance, capped at 5% notional. In
  practice the cap binds, at about $5,000.
- **Risk and halts:** exactly `OWNER_BASELINE_2026_11_03` and the experiment 002 halt rules: 0.50% daily loss, 3%
  drawdown halt, at most 2 positions, 10% gross exposure, no leverage.

### 4.4 Costs
- Base 2.3 bp, stress 6.6 bp, severe 9.6 bp per round trip (`trading/costs.py`, unchanged).
- These remain **assumptions**: spread is unmeasured pending Alpaca, and slippage is unmeasured without fills.
- Every result is reported at all three levels and at zero cost (the zero-cost run is a diagnostic only).

### 4.5 Benchmarks (computed with the same engine, costs and limits)
1. **No trade.**
2. **Random-session long:** the same entry, stop and exit on the same number of randomly drawn non-signal
   development sessions. The draws are stratified by year, use a fixed seed, and are repeated 10,000 times. This
   controls for "being long SPY intraday in that year".
3. **Always long, every development session,** with the same rules. Its exposure is about 28 times larger, and the
   report says so.

### 4.6 Failure criteria (fixed before any run; identical in structure to 001/002, not weakened)
The hypothesis is **rejected** if, on development data, any of these hold:
- net after base costs ≤ 0;
- net after stress costs < 0;
- below the **95th percentile** of the random-session baseline (benchmark 2);
- not positive after removing the **10 best trades**. With 53 trades this is a strict test; it is kept as in 001/002
  rather than relaxed.
- any predeclared neighbour flips the sign of net base:
  - entry at the 10:00 bar instead of 09:31;
  - stop 1.5%;
  - stop 3.0%;
  - early-close sessions excluded;
- maximum drawdown above 3% (the halt).

**Insufficient sample:** if fewer than the owner's minimum trade count execute (decision D3 below), the result is
**INCONCLUSIVE**, never a pass.

### 4.7 Controls against overfitting
- **One primary rule, no variant search:**
  - The variant budget is 1, and the 4 neighbours are reported only as robustness checks, never selected.
  - `trading/experiment.py` enforces the budget and the period lock. There is an `EXPERIMENT_LOCK.json`, and every
    attempt is logged in `experiment_attempts.csv`.
- **Pre-registration:** the spec hash and the tested code commit are locked before the single development run.
- **Multiple testing:** this is the third hypothesis tested on the same development data. The owner may
  **strengthen** the bar (decision D4), for example the 99th instead of the 95th percentile. It is never weakened.
- **No rescue:** a failure closes the candidate. Lower costs, other holidays or other entry times would be a new,
  separately approved hypothesis, logged as contaminated by this run.
- **Held-out periods:** validation has 25 signal sessions and final has 22. They are run only after a development
  pass, each once, with pass rules fixed in advance (decision D5).

### 4.8 What a pass would and would not mean
- A pass means the pattern beat random timing in a historical simulation with assumed costs. It is not a broker
  result, and not evidence of future profit.
- It would make the strategy **eligible to propose** for Milestone 2 (shadow observation), nothing more.

## 5. Checked against what we have already examined

| Earlier idea | Record | Overlap with H2 |
|---|---|---|
| 001 intraday momentum (close-to-10:00 return → last 30 min) | `001_intraday_momentum/` (FAILED) | Different signal (calendar, not price), different hold (full session). 001's runs included pre-holiday days, but returns on them were never separated or viewed. |
| 002 opening-range breakout | `002_opening_range_breakout/` (FAILED) | Different signal. 002's runs included these days; never separated. |
| "Buy after down mornings" diagnostic (+2.46 bp, lowest r1 quintile) | `EXPLORATION_LOG.md` 2026-11-04 | None: H2 does not condition on any price move |
| Gap-down opening | `candidates/gap_down_opening` (DEFERRED) | None: no gap condition and no quote dependence |
| Candidate B (gap-down reversal) in `NEXT_HYPOTHESES.md` | not selected | None |
| H1 FOMC drift (today) | this file | Rejected in favour of H2. Its verified dates are listed below for reuse. |

**Verdict:** H2 is a new hypothesis for this project. It is **not** fresh evidence of anything. It is an old, widely
published anomaly, and the literature says it has weakened. The only new element would be our own pre-registered
test on 2016-2021 SPY minute bars.

**Residual contamination:**
- I have seen the aggregate results of 001 and 002, which include these 53 days inside 1,500-session totals. That
  gives no usable information about their pre-holiday returns.
- I have also read the published claims of the effect and of its decline, which is a prior, not data.

**Verified FOMC scheduled statement days** (source: federalreserve.gov `fomchistorical2016`-`2020` and
`fomccalendars` pages, read 2026-11-11). The statement day is the second day of each meeting:
- 2016: 01-27, 03-16, 04-27, 06-15, 07-27, 09-21, 11-02, 12-14
- 2017: 02-01, 03-15, 05-03, 06-14, 07-26, 09-20, 11-01, 12-13
- 2018: 01-31, 03-21, 05-02, 06-13, 08-01, 09-26, 11-08, 12-19
- 2019: 01-30, 03-20, 05-01, 06-19, 07-31, 09-18, 10-30, 12-11 (the 10-04 meeting was unscheduled)
- 2020: 01-29, 04-29, 06-10, 07-29, 09-16, 11-05, 12-16 (03-18 cancelled; 03-02 and 03-15 unscheduled)
- 2021: 01-27, 03-17, 04-28, 06-16, 07-28, 09-22, 11-03, 12-15

The 14:00 ET release time for 2016-2021 is taken from Fed practice and is **not verified** here.

## 6. Offline preparation done today

- **Calendar count, no prices** (scratch script, not project code):
  - development: 53 signal sessions, 6 of them early close;
  - validation: 25 (1 early close; Juneteenth starts in 2022);
  - final: 22 (4 early close).
- **Development signal sessions:**
  - 2016: 01-15, 02-12, 03-24, 05-27, 07-01, 09-02, 11-23, 12-23, 12-30
  - 2017: 01-13, 02-17, 04-13, 05-26, 07-03, 09-01, 11-22, 12-22, 12-29
  - 2018: 01-12, 02-16, 03-29, 05-25, 07-03, 08-31, 11-21, 12-24, 12-31
  - 2019: 01-18, 02-15, 04-18, 05-24, 07-03, 08-30, 11-27, 12-24, 12-31
  - 2020: 01-17, 02-14, 04-09, 05-22, 07-02, 09-04, 11-25, 12-24, 12-31
  - 2021: 01-15, 02-12, 04-01, 05-28, 07-02, 09-03, 11-24, 12-23
- **Power arithmetic:** with n = 53 and an assumed open-to-close standard deviation of 0.6 / 0.8 / 1.0%, the minimum
  detectable mean is 20.5 / 27.3 / 34.2 bp per trade (80% power, one-sided 5%).
- **Not done, by rule:**
  - no strategy code and no synthetic tests of the rule (coding waits for spec approval);
  - no price data read for these dates;
  - no downloads.

## 7. Owner decisions that block experiment 003

| # | Decision | Needed for |
|---|---|---|
| D1 | Approve, change or reject H2 as the next hypothesis | anything further |
| D2 | Approve the spec (rules in 4.1-4.6 as written, or with changes) | coding and the lock |
| D3 | Minimum executed trades for a verdict (for example 45 of 53); fewer gives INCONCLUSIVE | the pass rules |
| D4 | Whether to strengthen the random-baseline bar for multiple testing (95th → 99th percentile) | the pass rules |
| D5 | Pass rules for validation (25 trades) and final (22): for example, net base > 0 and above the random median | before any held-out run |
| D6 | Which cost level must pass (stress is proposed, as in 001/002) | the pass rules |

## 8. From research to paper trading, then to limited live trading

Each step needs its own owner decision. None follows automatically.

1. **Research pass (Track A):** development pass, then validation pass, then final pass, each under locked rules,
   with every attempt logged.
2. **Shadow observation (Milestone 2):** the approved version runs on live bars without orders, for a predeclared
   number of sessions **and** trades. With about 9 signal days a year, this takes many months; the owner sets the
   length.
   - The decisions must reproduce offline, byte-identical.
   - Shadow-vs-backtest consistency is judged by a predeclared rule.
   - Prerequisite: Milestone 1 accepted (five consecutive PASS sessions; currently 1 of 5).
3. **Supervised paper orders (Milestone 3):** all six readiness items MET (`trading/dashboard/execution_readiness.py`):
   - dry-run acceptance;
   - approved execution policies A1-A6;
   - the confirmed intended paper account;
   - safety controls tested **against paper**;
   - an approved written test plan;
   - a written authorization.

   Fills then give the first slippage measurements (with paper-fill caveats).
4. **Evidence review (Milestone 4):** paper vs shadow vs backtest, incidents and limitations. Then continue,
   revise or stop.
5. **Limited live trading:** a separate future proposal requiring:
   - explicit written authorization;
   - a new host allowlist entry;
   - legal and account checks (including pattern-day-trader rules);
   - its own risk limits;
   - Alpaca's written answers for the cost model.

   Nothing in steps 1-4 creates it.
