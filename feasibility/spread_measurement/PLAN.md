# SPY bid-ask spread measurement: plan and pilot pre-registration

**Status:**

| Part | State |
|---|---|
| Plan (24 sessions) | Proposed 2026-11-08 |
| **Pilot (6 sessions)** | **PRE-REGISTERED.** This file is committed before any request. Owner instruction, 2026-11-08: start with a six-session pilot, keep the quote windows, cap at 600 requests and 75 MB, keep the per-window caps, keep findings provisional, and show the revised plan before downloading |
| Pilot download | **NOT RUN.** Waits for the owner's go-ahead after reviewing this file |
| Remaining 18 sessions | **PENDING** a separate owner decision. They are refused in code |

**What this is:**
- a read-only feasibility measurement of SPY's quoted bid-ask spread in 2016-2021
- it is not an experiment, computes no strategy returns, and approves no trading rule
- it does not reopen experiment 001 or 002, and nothing in it can change their verdicts
- it does not change `trading/costs.py`
- no validation (2022-01-03 to 2024-06-28) or final (2024-07-01 to 2026-10-30) data is requested
- it does not resume or unblock the gap-down candidate (`DEFERRED_DATA_SEMANTICS`); that
  candidate's download block in `trading/execution_feasibility.py` is untouched

**Why:** both closed experiments charged a guessed spread of 0.5 bp per side at base cost.
- 002's result went from about zero (base) to -2.19% (stress) on cost assumptions alone
  (`research/FAILURE_COMPARISON_001_002.md`).
- 001's spec asked for this measurement before backtesting (SPEC section 10). It was never done.

## Glossary

- **Bid / ask:** the best displayed price to sell / buy at. **Spread** = ask - bid.
- **Mid** = (bid + ask) / 2.
- **bp (basis point)** = 0.01%. **Spread in bp** = 10,000 x spread / mid.
- **Half-spread:** what one buy or one sell pays relative to the mid. This is the number
  `trading/costs.py` assumes:
  - base: 0.5 bp per side
  - stress: 1.0 bp per side
  - severe: 2.0 bp per side
- **Locked:** bid = ask. **Crossed:** ask < bid.
- **Time-weighted:** each quote counts for as long as it was in force, not once per record.

## 1. Do the open Alpaca questions block a meaningful measurement?

The open questions are A1-A5 in `feasibility/execution_data/ALPACA_SUPPORT_REQUEST_DRAFT.md`
(unsent).

**Conclusion: they limit what can be claimed, but do not block a provisional, minute-scale
measurement.** This matches the scope correction in `feasibility/execution_data/FINDINGS_2.md`.

**Owner decision 2026-11-08:** findings stay **provisional**.

| Question | Effect on a spread measurement | Measurable provisionally? | Must wait |
|---|---|---|---|
| **A1** Timestamp clock (SIP, exchange or Alpaca receipt time) | Mostly affects which quote was in force at an exact instant. Time-weighted statistics over windows of 2-16 minutes move only at the window edges, unless the clock is off by more than seconds. | Yes: time-weighted window statistics, assuming clock error under 1 s | Sub-second claims. Snapshot spreads (section 5) are labelled **clock-dependent** |
| **A2** Condition code `?` | Non-firm, halted or indicative quotes cannot be filtered out by code | Yes. Every statistic is split by code, and `?` is labelled "condition unknown" | Any claim that all measured quotes were firm |
| **A3** Are bid/ask the consolidated best quote (NBBO)? | Bid and ask often come from different exchanges, so these are not single-exchange quotes. Whether they match the official NBBO is undocumented. | Yes, labelled "Alpaca SIP quote, construction undocumented" | Calling it the NBBO spread, or using it as a verified cost input |
| **A4** Locked / crossed meaning | Real zero or negative spreads, or artifacts? | Yes: excluded from the headline, with time shares reported | Counting locked time as a zero spread (shown only as a sensitivity) |
| **A5** Corrections, backfills, vendor changes | 2016-2021 quotes may differ from what was published then | Yes, labelled "as retrieved in 2026" | Any point-in-time claim |
| Size units (documented) | Sizes before 2025-11-03 are round lots (x100 shares) | Yes: converted to shares | None |

**This measurement can never show:**
- slippage: it needs real fills, and orders are out of bounds
- queue position, hidden liquidity, market impact, our own order latency
- the official closing auction price

## 2. Dates

**Selection method (already applied; calendar only, no market data):**
1. Take all 1,511 XNYS sessions from 2016-01-04 to 2021-12-31.
2. Remove the 12 early-close sessions.
3. Remove the 7 sessions sampled on 2026-11-04. 1,492 sessions remain.
4. Draw 4 per year with `random.Random(20261108).sample(year_pool, 4)`, years in order from 2016
   to 2021, and sort each year.
5. No price, return, volatility or spread information was used. No substitutions.

**Pilot (owner instruction): the first listed date of each year.**

| Year | Pilot session | Pending (separate decision) |
|---|---|---|
| 2016 | **2016-03-28** (Mon) | 2016-05-03, 2016-06-17†, 2016-12-01 |
| 2017 | **2017-01-06** (Fri) | 2017-04-26, 2017-05-26, 2017-07-31 |
| 2018 | **2018-06-07** (Thu) | 2018-07-25, 2018-09-07, 2018-10-11 |
| 2019 | **2019-01-31** (Thu) | 2019-06-10, 2019-09-23, 2019-11-15‡ |
| 2020 | **2020-01-02** (Thu) | 2020-02-11, 2020-05-19, 2020-12-18† |
| 2021 | **2021-04-23** (Fri) | 2021-06-02, 2021-09-09, 2021-10-21 |

- † Quarterly expiration Friday and SPY ex-distribution date. ‡ Monthly options expiration.
  These flags apply to pending dates only. **None of the 6 pilot dates is flagged.**
- **Pilot fetch order:** the 24-date order pre-drawn with `random.Random(20261109)`, keeping only
  the pilot dates:

  **2018-06-07, 2021-04-23, 2020-01-02, 2019-01-31, 2016-03-28, 2017-01-06.**

- **Known gap:** 6 calm-looking random days are a pilot, not a distribution. Stressed sessions
  are almost certainly missing.

## 3. Quote windows (unchanged; regular 16:00-close sessions; times ET; start and end inclusive, as Alpaca documents)

These come from the closed specs: 001 SPEC sections 5-6, and 002 SPEC section 2.

| ID | Window | What it matches | Page cap | Snapshot instants |
|---|---|---|---|---|
| **B0** | 10:00:00-10:16:00 | **002's earliest entries** (from 10:01); B3 baseline entry at 10:01 | 60 | 10:01, 10:05, 10:10, 10:15 |
| **B1** | 10:45:00-10:47:00 | 002 entry window, mid-day sample | 10 | 10:46 |
| **B2** | 11:30:00-11:32:00 | same | 10 | 11:31 |
| **B3** | 12:15:00-12:17:00 | same | 10 | 12:16 |
| **B4** | 13:00:00-13:02:00 | same | 10 | 13:01 |
| **B5** | 13:45:00-13:47:00 | same | 10 | 13:46 |
| **B6** | 14:30:00-14:32:00 | same | 10 | 14:31 |
| **B7** | 14:58:00-15:01:00 | **002's latest allowed entry** (15:00) | 15 | 15:00 |
| **E1** | 15:29:00-15:34:00 | **001 entry:** decision 15:30; modeled fill at the 15:31 bar open; fallback up to the 15:33 bar; sensitivity fill at the 15:30 open | 45 | 15:30, 15:31, 15:32, 15:33 |
| **X1** | 15:57:00-16:00:00 | **Exits:** 002 at the 15:59 bar open; 001 at the 15:59 bar close (about 16:00:00); 002's last stop-active bar (15:58) | 40 | 15:59, 16:00 |

- **Totals:** 39 minutes per date, and at most **220 pages** per date. Windows are fetched in the
  table's order (time of day).
- **Snapshot instants:** each window starts at least 1 minute before its first snapshot instant.
- **Stop exits:** stops can fire at any minute after entry. These windows sample that span; they
  do not cover every minute of it.
- **No outcomes used:** windows are fixed from the specs. No closed-experiment outcome was used
  to choose them.

## 4. Rules for each quote

Every record is kept in the raw download. The analysis classifies each record; it removes
nothing from the files.

| Case | Definition | Treatment |
|---|---|---|
| Invalid | missing, NaN or negative bid/ask; unparseable timestamp; timestamp outside the requested window | Excluded and counted |
| Duplicate | byte-identical record (page or window boundary) | Counted once; duplicates counted |
| Out of order | timestamp earlier than the previous record | Counted. The date-window is flagged **ORDERING ISSUE**. Durations use the records sorted by timestamp (stable) |
| Normal | ask > bid > 0 | Used in spread statistics, if its condition code qualifies (below) |
| Locked | ask = bid > 0 | Excluded from the headline; time share reported. Sensitivity: mean recomputed with locked time counted as a 0-cent spread |
| Crossed | ask < bid, both > 0 | Excluded; time share reported |
| One-sided | bid = 0 or ask = 0 ("no active bid/ask" per the docs) | Excluded; time share reported |
| Condition `?` | not in the provider's table | Included in the headline, labelled "condition unknown"; every statistic is also split by code |
| Condition `R` | "Regular Market Maker Open" | Included |
| Any other code | anything else, or more than one code on a record where one is neither `?` nor `R` | Class "other condition": excluded from the headline, counted, and time share reported |
| Stale | a record stays in force more than **5.0 s** with no newer record | The time beyond 5.0 s is "stale / no update": excluded, time share reported |
| No quote | window time before the first valid record | Excluded, time share reported |
| Wide spread | normal spread > 10 cents | Not removed. Counted and listed with its timestamp (up to 50 listed); the maximum and 99th percentile are always reported |

- **In force:** a record is in force from its timestamp until the next valid record's timestamp,
  or until the window end, then capped by the stale rule.
- **Time shares:** headline-normal + locked + crossed + one-sided + other condition + stale + no
  quote = 100% of the window.
- **Coverage threshold:** a date-window counts as **measured** if headline-normal time covers at
  least 95% of the window. Otherwise it is **partial**: reported, but kept out of the
  cross-date summaries.
- **Snapshot instants (clock-dependent):**
  - use the latest headline-normal record at or before the instant, within the preceding 1.0 s
  - if a later non-normal record also precedes the instant, the snapshot is labelled
    **AMBIGUOUS** (value still reported)
  - if there is no headline-normal record within 1.0 s, the snapshot is **unresolved** and no
    value is given

## 5. Measurements (pilot)

**Per date-window:**
- **Spread in dollars, cents and bp:**
  - time-weighted mean, median, 90th and 99th percentile, maximum
  - count-weighted mean and median, as a secondary view
- **Half-spread in bp:** the time-weighted mean / 2, compared with 0.5 / 1.0 / 2.0 bp
- **Time share** at 1 cent, 2 cents and 3 cents or more
- **Exclusions:**
  - excluded-quote counts by reason (invalid, duplicate, locked, crossed, one-sided, other
    condition)
  - out-of-order count
  - time shares of every class
  - coverage, and measured or partial
- **Condition codes:** counts, plus time-weighted mean spread per code
- **Activity:** quote count and the largest gap between records
- **Displayed size:** median bid and ask size in shares (lots x 100). Our modeled positions were
  about 10-25 shares.
- **Wide spreads:** count over 10 cents, with up to 50 timestamps listed
- **Snapshot spreads**, labelled as in section 4

**Across the 6 dates, per group:**
- **Groups:** E1 (001 entry); X1 (exits); B0; B1-B7 pooled, time-weighted across those windows
  (002 entry window); B7
- **For each group:**
  - the minimum, median and maximum of the daily time-weighted mean spreads, in cents and bp,
    measured windows only
  - the count of measured dates whose time-weighted mean half-spread exceeds 0.5, 1.0 and 2.0 bp
  - coverage counts beside every number (measured, partial, incomplete, not fetched)

**Resource usage:**
- HTTP requests (total, by status, pages per date-window)
- bytes stored per file and in total
- wall-clock duration
- every cap reached

**Not computed:**
- no change in mid price over time, and no return of any kind (the mid is used only as the bp
  denominator)
- no trades, no fills, no strategy logic

**Committed outputs after the run:**
- `feasibility/spread_measurement/FINDINGS_pilot.md`
- `feasibility/spread_measurement/findings_pilot.json`
- statistics only: no raw quotes, no credentials

## 6. Pilot hard limits (implemented in `trading/spread_measurement.py`, tested before any request)

| Limit | Value |
|---|---|
| Host, method | `https://data.alpaca.markets`, HTTP GET only, through the existing read-only client |
| Endpoints | `/v2/stocks/quotes` (`symbols=SPY`, `feed=sip`, `limit=10000`, `sort=asc`); and 1 request to `/v2/stocks/meta/conditions/quote?tape=B`. Nothing else |
| Symbol, feed | SPY only, SIP only. No feed substitution; nothing bought or upgraded |
| Dates | exactly the 6 pilot dates. Any other date, including the 18 pending ones, is refused in code. So is any date outside the development period, and any early-close session |
| Page caps per date | B0 60; B1-B6 10 each; B7 15; E1 45; X1 40. At most 220 per date |
| **Total HTTP requests** | **600**, counted at the HTTP layer, including the condition-table request and the client's bounded 429 waits |
| Pacing | at least 0.4 s between requests |
| **Storage** | **75 MB** in total, in `data/feasibility/spreads_pilot_<UTC>/` (git-ignored, separate from `data/history/` and every experiment) |
| Storage guard | Before each window, the run checks that the bytes used plus a worst-case reserve (page cap x 200 KB) fit under 75 MB; if not, it stops. After each write it re-checks actual bytes, and stops if 75 MB is exceeded |
| Page cap reached | that date-window is **INCOMPLETE COVERAGE**, with the last timestamp received; never treated as complete |
| Request or storage cap reached | the run stops. The window in progress is **INCOMPLETE**, and all later windows are **NOT FETCHED**. No second run without a new owner approval |
| Access failure (401/403, or another non-200 after bounded 429 handling) | status and message recorded; the quotes path stops for all remaining windows and dates; no retries |
| Pre-registration gate | the fetch refuses unless this file is tracked by git with no uncommitted changes. The commit hash and the file's SHA-256 are recorded in the results |
| Retention | raw downloads stay local until the owner decides; only compact findings are committed |

**Estimate for the pilot (from the 2026-11-04 page counts):**
- about 300-500 requests
- about 25-40 MB
- 10-25 minutes

`data/` is inside OneDrive, so the download will sync unless sync is paused.

## 7. Limitations (repeated in the findings)

- **6 days:** a pilot. It checks the method and resource use, and gives first spread figures. It
  is not a distribution, and it has no stressed days.
- **Quotes are not fills.** Slippage, queue position, hidden liquidity, impact and latency are
  unmeasured.
- **Undocumented semantics:** the clock, construction, condition codes and corrections (section
  1). The results are provisional.
- **Closing auction:** not identified, so market-on-close exits are not covered.
- **Scope:** SPY only, development years only, full-day sessions only.
- **Tick size:** the 1-cent minimum spread makes bp figures fall as SPY's price rose. This is not
  a change in market quality by itself.

## 8. Decisions

| # | Decision | State |
|---|---|---|
| 1 | Provisional measurement while A1-A5 are unanswered, changing no model | **Decided 2026-11-08: provisional** |
| 2 | Pilot dates, fetch order, windows, limits (sections 2, 3, 6) | **Decided 2026-11-08** (owner instruction); this file is the pre-registration |
| 3 | Start the pilot download | **Pending:** after the owner reviews this file |
| 4 | The remaining 18 sessions | **Pending:** a separate decision after the pilot findings |
| 5 | Optional stress add-on | Not proposed for the pilot |
| 6 | Any change to the cost model | Out of scope. It would be a separate owner decision, would supersede the experiment locks, and would apply only to future experiments |

## 9. Commands

```powershell
.venv\Scripts\python -m trading.spread_measurement limits          # print dates, windows and caps; no network
.venv\Scripts\python -m trading.spread_measurement fetch-pilot     # GET only, capped; needs the committed plan
.venv\Scripts\python -m trading.spread_measurement analyze <dir>   # offline, writes findings_pilot.json
```
