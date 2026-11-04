# Distribution calendar, quote interpretation and exit coverage: findings (2026-11-04)

**FEASIBILITY EVIDENCE:**
- not a research evaluation
- no returns computed, no thresholds tuned
- no experiment
- no entry, stop or exit rule approved

**Held-out data:** no held-out market data was requested. The issuer page displays its whole
distribution history; only development-period rows were stored.

## 1. SPY distribution calendar (`spy_distributions_development.json`)

**Instrument:**
- SPDR S&P 500 ETF Trust, ticker SPY, CUSIP 78462F103, ISIN US78462F1030
- NYSE Arca, listed 1993-01-22
- per the issuer's fund page, retrieved 2026-11-04

**Source:** the issuer, State Street Global Advisors.
- **URL:** <https://www.ssga.com/us/en/intermediary/resources/documents/etf-dividend-distributions>,
  "Historical Distributions", SPY row expanded
- **Retrieved:** 2026-11-04 23:13:40 UTC, by reading the page in the in-app browser
- **Content:** the page shows ex, record and payable dates and amounts. It has **no publication
  or declaration dates**.

**Coverage:**
- one distribution per quarter, continuously from 1993-03-19 to 2026-09-18
- **24 in the development period**, all on the third Friday of March, June, September and
  December
- no capital-gain distributions in 2016-2021

**Reconciliation with Alpaca:**
- 21 of 24 match exactly, on both date and amount
- Alpaca is missing 2016-03-18, 2018-06-15 and 2021-12-17
- Alpaca has 0 extra records
- the Alpaca response was **not** treated as complete

### Retrospective classification vs historical availability

| | Result |
|---|---|
| Development sessions | 1,511 |
| Verified ex-distribution: **excluded before any signal evaluation** | 24 |
| Verified non-ex-distribution: eligible | 1,487 |
| Unresolved: ineligible | 0. This depends on the issuer history being complete; corroboration is partial. |
| Ex-dates with archived issuer schedules captured **before** the ex-date | **7 of 24**: 2020-06-19, 2020-09-18, 2020-12-18 (capture 2020-05-19); all four 2021 dates (capture 2021-01-30) |
| Ex-dates with **no point-in-time evidence** | 17: all of 2016-2019 and 2020-03-20 |

- **Archive search:** Internet Archive captures of the schedule exist only from 2020-05.
- **Classification only:** the 1,487 / 24 split is a **retrospective** classification. Except
  for those 7 dates, it does not show what a trader could have known at 09:31 that day.

**Selection bias:**
- **Expiration days:** every excluded session is a quarterly index option and futures expiration
  Friday, a morning with unusual opening-auction activity. Any later result would not describe
  those days, and the eligible set has none of them.
- **Excise dates:** both archived schedules also list a "Potential Excise Distribution" date
  (2020-12-30, 2021-12-30), and none occurred. A live fail-closed rule would skip such dates
  until confirmed, while the historical classification does not, because 2016-2019 schedules
  are not available to identify them.

### Future operation (proposed; required before any live use)

- **Calendar before the open:** before each session, the current year's issuer schedule is
  retrieved and stored, with its URL and retrieval time.
- **What blocks trading:** trading on a session is allowed only if that session is shown as
  **not** an ex-date. Any of these blocks it (**fail closed**):
  - an ex-date
  - a "potential" distribution date
  - a schedule that is missing, stale or unparseable

## 2. Quote interpretation (official Alpaca documentation, read 2026-11-04)

Source: <https://docs.alpaca.markets/us/reference/stockquotes-1>, page modified 2026-05-27.

| Item | Official text | Status |
|---|---|---|
| Quote object | "The best bid and ask information for a given security", with bid and ask exchange fields | Consistent with a national best bid and offer; **not stated** to be the SIP's official NBBO |
| `t` | "Timestamp in RFC-3339 format with nanosecond precision" | **UNRESOLVED:** the docs do not say whether this is the SIP, participant or Alpaca time |
| Bars (market-data FAQ) | minute bars use "the (SIP) timestamp of the trade" | Documented for bars and trades, not for quotes |
| `as` / `bs` | "in shares (round lots prior to November 3, 2025)" | Development-period sizes are **round lots (x100)**, not shares |
| `ap` / `bp` = 0 | "no active ask/bid" | 0 such quotes found |
| `c` | the quote-condition table for tape B was retrieved (13 codes) | 6 of 7 dates return `?`, which is not in the table, so **unmapped**. 2021 returns `R` ("Regular Market Maker Open"). |
| `start` / `end` | "inclusive" | Confirmed: quotes stamped exactly at the window end appear |

## 3. Locked and crossed quotes (proposed treatment, not approved)

- **Kept:** every quote is retained and classified as normal (ask > bid > 0), locked (ask = bid),
  crossed (ask < bid) or one-sided (a zero side). Nothing is deleted.
- **Spreads:** spread statistics use normal quotes only, and are always reported **beside** the
  count and time shares of the other classes.
- **Reference prices:** for a reference price at time T, use the latest quote at or before T.
  If it is not normal, the price is labelled **AMBIGUOUS**, and the more adverse of that quote
  and the latest normal quote is used:
  - a buy takes the higher ask
  - a sell takes the lower bid
- **No normal quote:** if there is no normal quote in the preceding 1 s, the case is
  **unresolved** and no price is invented.

**Observed (7 days, 09:30-10:01):**
- locked quotes: 0.06-1.2% of the time
- crossed quotes: up to 0.09%
- one-sided quotes: 0%

## 4. Quote coverage through the proposed 10:00 exit

| Item | Value |
|---|---|
| Pre-registration | `PREREGISTRATION_2_coverage.md` (commit a67fc20) |
| Requests | 195 of 360, all HTTP 200; no page cap reached, no refusal |
| Retrieval time (local) | 2026-11-04 23:19:06-23:21:33 UTC |
| Quotes, 09:35-10:01 | 44,949 to 714,801 per day |
| Minutes 09:35-10:00 with no quote | **none** on any day. The "10:01" bucket covers only its first instant. |
| Largest gap between quotes | 5.5 s (2017-01-19); under 1.1 s from 2019 on |
| Ordering | non-decreasing on every day |
| Normal-quote median spread | 1 cent in every minute on every day. The 90th percentile is 2 cents on 3 days. |
| Lowest per-minute time share at 1 cent | 47% (2020-12-02); 82-100% on the other days |
| Exit minute (10:00) | quoted on all 7 days; median spread 1 cent |

**Data summary:** stored as `coverage_findings.json`. Downloads stay git-ignored in
`data/feasibility/coverage_20261104T231906Z/`.

## 5. What this is not

- **Not a cost model:** seven sampled days are **not** a validated execution-cost model. They
  confirm that the data exists, how it is shaped and how far it reaches. They do not give a cost
  distribution.
- **No fills:** quotes do not establish achievable fills, queue position, hidden liquidity,
  market impact or our own order latency.

## Verdict

| Requirement | Status |
|---|---|
| Retrospective distribution classification | **Established:** issuer source, instrument verified, coverage continuous |
| Point-in-time distribution availability | **Partial:** 7 of 24 dates evidenced; 17 not |
| Quote coverage, entry through exit | **Established** for the 7 sampled days |
| Quote timestamp semantics | **Not established:** the official docs do not say which clock |
| Quote condition codes, 2016-2020 | **Not established:** `?` is unmapped |
| Execution-cost model | **Not established**, and not claimed |

Under the owner's stated rule, quote interpretation could not be established from accessible
official sources. The recommendation is therefore **to defer this candidate**. No data was
purchased, and no assumption fills the gap.
