# Execution-data access check: findings (2026-11-04)

**FEASIBILITY EVIDENCE:**
- not a research evaluation
- no strategy returns computed, no parameters chosen
- no experiment
- no trading rule approved

**Pre-registration:** `PREREGISTRATION.md` (commit 883f7bb, before any request).
**Compact machine-readable results:** `findings.json`.

| Item | Value |
|---|---|
| Run | `python -m trading.execution_feasibility fetch`, then `analyze` |
| Local retrieval time | 2026-11-04 23:01:42 to 23:02:15 UTC |
| HTTP requests | **57** of the 240 cap, all HTTP 200; no 429 waits |
| Access failures / stopped paths | none |
| Page caps reached | none; every path is complete |
| Downloads (git-ignored, 3.1 MB) | `data/feasibility/execution_20261104T230142Z/`, separate from `data/history/` and every experiment |
| Held-out data | none requested; every date is checked against the development period in code |

**Timestamps:** provider timestamps (`t`) are what Alpaca returned. Their exact meaning
(participant or SIP time) is **unverified**. Local retrieval times are in `requests_log.json`.

## 1. Historical SIP quotes, 09:30-09:35 ET

**Access:** the free plan returned historical SIP quotes for all 7 development dates, from
10,259 to 160,494 quotes per date.

| Date | Quotes | Crossed | Locked | Median spread (each minute, 09:30-09:34) | Share of time at 1 cent, 09:30 / 09:32 |
|---|---|---|---|---|---|
| 2016-10-19 | 16,305 | 0 | 867 | 1 cent (0.47 bp) | 99.5% / 100% |
| 2017-01-19 | 10,259 | 1 | 172 | 1 cent (0.44 bp) | 90.4% / 97.6% |
| 2017-03-27 | 27,304 | 42 | 1,133 | 1 cent (0.43 bp) | 93.1% / 97.1% |
| 2019-05-07 | 50,073 | 50 | 1,698 | 1 cent (0.34 bp) | 89.2% / 91.0% |
| 2019-06-21 | 38,940 | 128 | 1,925 | 1 cent (0.34 bp) | 59.8% / 97.4% |
| 2020-12-02 | 77,912 | 5 | 392 | **2 cents** at 09:30-09:31, then 1 cent | **32.6%** / 50.6% |
| 2021-07-20 | 160,494 | 53 | 4,705 | 1 cent (0.23 bp) | 78.8% / 95.7% |

**Validation:**
- timestamps all parse
- order is non-decreasing
- no non-positive bids, asks or sizes
- the first quote arrives within 0.01 s of 09:30
- the largest gap between quotes within a minute is 2.2 s
- crossed (ask < bid) and locked quotes occur. They are counted, not removed or explained.

**What the fields show:**
- **Exchanges:** each quote carries a bid exchange and an ask exchange, so it looks like a
  consolidated best bid and offer. That interpretation is unverified.
- **Condition codes:** 6 of 7 dates return the condition code `?` (not informative); 2021
  returns `R`.
- **Precision:** timestamps are millisecond precision in 2016-2017 and nanosecond from 2019.
- **End time:** the end of the window is **inclusive**. One quote stamped exactly 09:35:00 appears
  on two dates, and minute requests returned 33 bars (09:30-10:02) instead of 32.

**Spreads are wider at 09:30-09:31 on some days.**
- **Widest case:** on 2020-12-02, about two-thirds of the opening minutes' time had a spread above
  1 cent.
- **Against the cost model:** the observed median full spread was 0.23-0.55 bp. The 002 cost
  model's base assumes 1 bp per round trip from half-spreads alone.
- **Sample size:** that is **7 days**, not a distribution.

## 2. Raw SIP minute bars, 09:30-10:02 ET

**Validation:**
- 33 bars on every date, with no missing minute
- 0 OHLC or volume violations, 0 ordering errors

**Raw vs stored adjusted (`all`) prices:**
- **Ratio:** from 1.0726 (2021) to 1.1658 (2016).
- **Within a day:** constant to about 5 parts in 100,000.
- **So:** adjusted development prices differ from executable prices by **7-17%** in level.

**Daily vs minute open:** the raw daily bar's open differs from the 09:30 minute bar's open by
-1, 0 or +1 cent. Which one is the official opening auction price is **not verifiable** here.

## 3. Prior raw closes and corporate actions

**Prior close:**
- the raw daily bar for the prior session was returned on all 7 dates
- whether the daily close equals the official closing auction price is **not verifiable** here

**Dividends (`/v1/corporate-actions`, `cash_dividend`, 2016-01-04 to 2021-12-31): 21 records**
- **Expected ex-date confirmed:** 2019-06-21 is an ex-dividend date in the record ($1.43164).
  No other sampled date is.
- **Size against the threshold:** that dividend is **0.48% of the prior raw close** ($295.88).
  On that ex-date, a raw-price gap includes a mechanical drop almost equal to the draft's 0.5%
  threshold. This is a price-level fact, not a return.
- **Missing records:** SPY paid quarterly dividends in this period, but 21 records came back
  instead of 24. No record for Q1 2016, Q2 2018 or Q4 2021. The dates are not inferred and no
  extra request was made: a wider date range would touch 2022, so the path was stopped as
  planned. Possible cause, unverified: the range filters on the process date (Q4 2021 would
  process in January 2022).
- **Fields returned:** `ex_date`, `rate`, `process_date`, `cusip`, `special`, `foreign`, `id`,
  `symbol`. `record_date` and `payable_date` appear only from 2020.
- **No `declaration_date`.** Whether each dividend was known before the 09:31 decision on its
  ex-date **cannot be established from this source**. The records were retrieved in 2026, not
  as published at the time.

## 4. Limitations of this execution data

- **Fills:** quotes are not fills. They show displayed prices and sizes only. They do not show:
  - whether an order of our size would fill at the quote
  - queue position
  - hidden liquidity, or the price impact of crossing
- **Order arrival:** quotes do not show how fast our order would arrive. Today's monitoring
  measured 21 s median receipt of completed IEX bars; order routing time is unmeasured.
- **Sample:** 7 days are enough to confirm access and data shape, not to estimate a cost
  distribution or stress costs.
- **Auction prices:** the official opening and closing auction prices are not identified.
- **Codes:** crossed quotes and uninformative condition codes are present but not explained.

## Conclusion on feasibility

| Requirement | Status |
|---|---|
| Opening spread modeling | **Supported**: historical SIP quotes are accessible, timestamped and plausible for 2016-2021 |
| Raw executable prices for entry and exit | **Supported**: raw SIP minute and daily bars are accessible |
| Dividend handling at decision time | **Needs additional data**: 3 of the expected 24 quarterly records are missing, there is no declaration date, and the records are not point-in-time. The draft's 0.5% gap threshold is about the size of one SPY dividend, so this is material. |
| Fill and queue realism | **Not available** from any data we have; it stays a labelled assumption |

**Overall:** the available data supports further execution modeling of spreads. But it **needs
additional data**, a point-in-time dividend source or an owner-approved conservative dividend
rule, before the hypothesis could be specified without a known look-ahead or misclassification
risk.
