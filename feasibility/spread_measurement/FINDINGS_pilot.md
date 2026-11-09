# SPY bid-ask spread pilot: findings (PROVISIONAL)

**FEASIBILITY EVIDENCE, PROVISIONAL.**
- **Data:** Alpaca SIP quotes, as retrieved in 2026.
- **Undocumented:** the timestamp clock, the quote construction (NBBO or not) and the condition
  code `?`.
- **Quotes are not fills:** no slippage, queue or impact information.
- **Scope:** not research evaluation. No returns were computed, the cost model is unchanged, no
  closed experiment was reopened, and the gap-down candidate is untouched.

| Item | Value |
|---|---|
| Pre-registration | `PLAN.md`, commit `be2d9cd`, SHA-256 `cb9a1e27…7173f32`; verified by the gate at run time |
| Command | `python -m trading.spread_measurement fetch-pilot`, then `analyze` |
| Run | once, 2026-11-09 01:22:28 to 01:24:03 UTC |
| Dates | the 6 pilot sessions: 2016-03-28, 2017-01-06, 2018-06-07, 2019-01-31, 2020-01-02, 2021-04-23 |
| Windows | 10 per date (B0-B7, E1, X1), 39 minutes per date, 60 date-windows in all |
| Downloads | `data/feasibility/spreads_pilot_20261109T012228Z/` (git-ignored) |
| Committed statistics | `findings_pilot.json` (no raw quotes) |
| Validation and final data | none requested |

## 1. Coverage and exclusions

| Item | Result |
|---|---|
| Windows fetched complete | **60 of 60.** No page cap, request cap or storage cap reached; no access refusal |
| Windows **measured** (headline-normal coverage at least 95%) | **60 of 60.** Lowest coverage 97.9% (2018-06-07 E1), then 98.5% and 98.9% |
| Records received | 1,020,258 |
| Invalid (bad price or timestamp, outside the window) | 0 |
| Duplicates | 0 |
| Out of order | 0 (no ORDERING ISSUE flags) |
| Locked (bid = ask) | 52,038 records (5.1% of records), but **0.37% of time** |
| Crossed (ask < bid) | 849 records (0.08% of records); 0.003% of time |
| One-sided | 0 |
| Other condition code | 0 |
| Condition code `?` (unknown) | **100% of records, all 6 dates, including 2021.** The 2021 date sampled on 2026-11-04 returned `R`; this 2021 date did not. A2 affects every quote measured |
| Stale time (over 5 s without an update) | 0.005% of window time |
| No-quote time (before the first record) | 0.05% of window time. The largest was 5 s at the start of 2018-06-07 E1 |
| Largest gap between records | 5.7 s (2018-06-07 B7); under 1.5 s on 14 of the 20 windows in 2020-2021 |
| Snapshot instants (102) | 99 ok, 1 AMBIGUOUS (2018-06-07 16:00:00; a later locked or crossed record), 2 unresolved (2018-06-07 15:30:00, 2020-01-02 12:16:00: no normal quote within 1 s) |
| Spreads over 10 cents | 0 |

## 2. Provisional spread measurements

**Headline:** on all 6 days, in every window, SPY's quoted spread was **1 cent** for most of the
time (88-100%, time-weighted). The widest recorded spread was 5 cents (an instant in 2021-04-23
X1). The 99th percentile was 1 or 2 cents in every window.

**What "half-spread" means here:**
- It is half the quoted spread, time-averaged over a window.
- It is an **estimate of the spread component of execution cost**: what a buy at the ask or a sell
  at the bid would give up relative to the mid, if it filled at the displayed quote.
- It is **not** what every buy or sell actually pays. A real order can fill better (inside the
  spread) or worse (slippage, a moving price, a size beyond the displayed quote, latency), and
  those parts are not measured here.

**Daily time-weighted mean spread, by window group (measured windows only, 6 of 6 dates each):**

| Group (what it matches) | Mean spread, cents (min / median / max) | Mean spread, bp (min / median / max) | Half-spread, bp (min / max) |
|---|---|---|---|
| E1: 001 entry, 15:29-15:34 | 1.000 / 1.001 / 1.050 | 0.239 / 0.376 / 0.492 | 0.120 / 0.246 |
| X1: exits, 15:57-16:00 | 1.002 / 1.011 / 1.026 | 0.242 / 0.368 / 0.500 | 0.121 / 0.250 |
| B0: 002 earliest entries, 10:00-10:16 | 1.001 / 1.031 / 1.108 | 0.247 / 0.394 / 0.492 | 0.123 / 0.246 |
| B1-B7: 002 entry window, pooled | 1.000 / 1.026 / 1.045 | 0.244 / 0.381 / 0.492 | 0.122 / 0.246 |
| B7: 002 latest entry, 14:58-15:01 | 1.000 / 1.013 / 1.100 | 0.240 / 0.390 / 0.493 | 0.120 / 0.247 |

**By date (E1 / X1 mean half-spread, bp):**

| Date | E1 | X1 |
|---|---|---|
| 2016-03-28 | 0.246 | 0.250 |
| 2017-01-06 | 0.220 | 0.220 |
| 2018-06-07 | 0.181 | 0.183 |
| 2019-01-31 | 0.195 | 0.186 |
| 2020-01-02 | 0.155 | 0.158 |
| 2021-04-23 | 0.120 | 0.121 |

- **Why bp falls over time:** the spread stayed at about 1 cent while SPY's price roughly doubled.
  That is the 1-cent tick, not a change in market quality.
- **Against the cost model:**
  - No measured date-window had a mean half-spread above the model's spread assumption at base
    (0.5 bp per side), let alone stress (1.0) or severe (2.0). The estimated spread component is
    0.12-0.25 bp per side.
  - That is one-quarter to one-half of the base assumption, **for the spread component only, on
    these 6 calm-looking days**.
  - The base model's other parts are unmeasured: slippage (0.5 bp per side) and the sell fee
    (0.3 bp).
- **Sensitivity (locked time counted as 0 spread):** it changes the means by about 1% or less (locked time is at most 1.3% of a window).
- **Busier windows:** the most 2-cent time was in B0 and the mid-day samples: up to 11.9% (2020-01-02
  B6) and 10.8% (2019-01-31 B0). E1 and X1 were at 1 cent for 95-100% of the time.
- **Displayed size:** median 500-11,500 shares at the best bid and ask (round lots x 100). Our
  modeled positions were 10-25 shares. Displayed size is not a promise of a fill.

## 3. Actual resource usage

| Resource | Used | Cap |
|---|---|---|
| HTTP requests | **135** (1 condition table + 134 quote pages), all HTTP 200, no 429 waits | 600 |
| Storage | **7.87 MB** (raw quotes plus logs) | 75 MB |
| Largest window | 19 pages (2021-04-23 B0) | 60 |
| Duration | 95 s | none |

| Date | Pages | Quotes | MB |
|---|---|---|---|
| 2016-03-28 | 18 | 129,967 | 0.63 |
| 2017-01-06 | 15 | 83,675 | 0.42 |
| 2018-06-07 | 15 | 89,777 | 0.70 |
| 2019-01-31 | 25 | 210,046 | 1.69 |
| 2020-01-02 | 25 | 188,442 | 1.65 |
| 2021-04-23 | 36 | 318,351 | 2.71 |

- **Against the plan's estimate:** usage came in below it (300-500 requests, 25-40 MB). The
  storage guard's 200 KB-per-page reserve was conservative: actual pages averaged about 58 KB.
- **The remaining 18 sessions:** by the same rates, they would need about 400-450 requests and
  about 25 MB, more if the expiration and ex-distribution days are busier.

## 4. Reliability, and whether the remaining 18 sessions are justified

**What is reliable (provisionally):**
- The method and limits worked as specified.
- Coverage is near-complete and nothing was excluded as invalid.
- On these 6 days, the quoted spread in the strategies' windows was almost always 1 cent, and its
  bp value is predictable from SPY's price level.
- The day-to-day spread in cents is small (daily means 1.00-1.11 cents), so more calm days are
  unlikely to move these medians much.

**What is not established:**
- **Stressed days.** None of the 6 is a known high-volatility session. Spreads are widest exactly
  when costs matter most, and a random calm sample says nothing about that tail.
- **Semantics.** Every quote carries the unknown `?` code, and the clock and NBBO construction are
  undocumented (A1-A3). The numbers are labelled, not verified.
- **Most of the cost.** Spread is under half of the base round trip (1 of 2.3 bp). Slippage and
  fees are not measured, and quotes cannot measure slippage.

**Assessment:**
- **Cost:** the remaining 18 sessions are cheap and low-risk (about 400-450 requests, about 25 MB, a
  few minutes), and the pipeline is now proven.
- **Value:** they add little.
  - They would mostly re-measure calm days, where the answer is already close to "1 cent".
  - They would leave the two open gaps untouched: stressed days and undocumented semantics.
  - Four of them are expiration or ex-distribution days, which adds some variety. They are still
    random, not chosen for stress.
- **Conclusion:** the pilot is reliable enough to say, provisionally, that the base spread
  assumption looks conservative for SPY on ordinary days. It is **not** reliable enough to change
  the cost model, and running the 18 would not make it so.
- **What would make it so:** a pre-registered stress stratum, chosen by a public rule that
  uses no returns, and/or Alpaca's answers to A1-A5. Both are owner decisions; neither is started.

Nothing in this file changes `trading/costs.py`, any experiment lock or any closed verdict.
