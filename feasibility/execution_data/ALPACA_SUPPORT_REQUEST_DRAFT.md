# Support request to Alpaca: FINAL for the owner to send (NOT SENT)

**Status:** draft for the owner to review and send personally, if they choose.
- **History:** prepared 2026-11-04; updated 2026-11-09 with the spread pilot's observations.
- **Not sent:** nothing in this project sends it.
- **No identifiers:** it contains no credentials, account numbers, API keys or account
  identifiers. Before sending, add only what you choose to share.
- **Where to send:** Alpaca's support request form, <https://alpaca.markets/support/request>
  (name, email, subject, description). Alpaca's site also lists support@alpaca.markets for
  technical support.

---

**Subject:** Historical SIP stock quotes, 2016-2021: NBBO construction, filtering, condition code "?", timestamps

Hello,

I use Market Data API v2 historical stock quotes for research on 2016-2021 SPY data. I could not
find the answers below in the documentation
(https://docs.alpaca.markets/us/reference/stockquotes-1 and the Market Data FAQ).

**Requests** (GET `https://data.alpaca.markets/v2/stocks/quotes?symbols=SPY&feed=sip&limit=10000&sort=asc`):
- **Opening sample:** 09:30-10:01 ET on 2016-10-19, 2017-01-19, 2017-03-27, 2019-05-07, 2019-06-21,
  2020-12-02 and 2021-07-20.
- **Pilot:** windows between 10:00 and 16:00 ET on 2016-03-28, 2017-01-06, 2018-06-07, 2019-01-31,
  2020-01-02 and 2021-04-23. That is 1,020,258 quotes, for example 10:00-10:16, 15:29-15:34 and
  15:57-16:00 ET.
- **Condition table:** `/v2/stocks/meta/conditions/quote?tape=B`.

**What we observed:**
- **Condition `?`:**
  - All 1,020,258 pilot quotes have condition `?`, including 2021-04-23.
  - In the opening sample, 6 of 7 dates have `?`, but 2021-07-20 has `R`.
  - `?` is not in the tape B condition table.
- **Exchanges:** bid and ask exchanges usually differ, which looks like a consolidated quote.
- **Locked and crossed:** both occur (ask = bid; ask < bid).
- **Timestamp precision:** milliseconds before 2019, nanoseconds after.

Sample records (SPY, tape B):

| `t` | bid (bx, bp, bs) | ask (ax, ap, as) | c |
|---|---|---|---|
| 2017-03-27T13:30:00.583Z | P 231.93 x 33 | T 231.92 x 1 | ? |
| 2019-06-21T13:30:00.083493308Z | X 294.14 x 5 | P 294.14 x 20 | ? |
| 2021-07-20T13:30:00.00056192Z | Z 425.65 x 5 | P 425.68 x 28 | R |

**Questions, in order of priority:**

1. **Consolidation:**
   - Do `bp`/`ap` in historical SIP quotes represent the consolidated national best bid and offer
     (NBBO) as disseminated by the SIP? If not, how are they constructed?
   - Are locked and crossed records genuine NBBO states, or artifacts of sequencing quotes from
     different exchanges?
2. **Filtering and corrections:**
   - Are any historical SIP quotes withheld, filtered, deduplicated or corrected, for example by
     condition, sequence or venue?
   - Are there documented backfills, vendor or processing changes, gaps or known limitations for
     2016-2021?
3. **Condition code `?`:**
   - What does `?` mean? Is it "condition not available", or a specific condition?
   - Why does 2021-04-23 return `?` while 2021-07-20 returns `R`?
   - Can `?` records include quotes that were not firm or not eligible for the NBBO (for example
     non-firm, indicative, halt or closing-period quotes)?
4. **Timestamp:**
   - Which clock does `t` represent: the SIP timestamp, the participant (exchange) timestamp, or
     Alpaca's receipt time?
   - Did its meaning, source or precision change during 2016-2021?

**Why this matters to us:** most quotes we measured are 1 cent wide. That alone does not tell us
whether every record was an eligible consolidated quote, or which quote was in force at a given
time. Both quote eligibility and timestamp meaning affect how we interpret spread estimates
derived from these records.

Thank you.

---

## Notes for the owner (not part of the message)

**Why both open questions still matter for the pilot (`feasibility/spread_measurement/FINDINGS_pilot.md`):**
- **Eligibility (questions 1-3):** narrow spreads do not show that unknown-condition quotes are
  harmless.
  - If some `?` records were non-firm, filtered differently, or not true NBBO states, then the
    measured spread, its time weighting, and the locked/crossed shares could all describe
    something other than the executable best price.
  - A filtering step that removed unusual quotes would also make spreads look narrower than they
    were.
- **Timestamps (question 4):** the time-weighting depends on the timestamps too.
  - Each quote's in-force duration, the stale and no-quote shares, and every snapshot at an exact
    instant assume a consistent clock.
  - Window averages are less sensitive than snapshots, but they still rely on the order and spacing
    of records.

## Answers needed to resume the gap-down candidate (owner checklist)

The candidate stays **DEFERRED_DATA_SEMANTICS** until written answers establish all of these:

| # | Needed | Resumes only if |
|---|---|---|
| A1 | The clock behind `t`, and any 2016-2021 change (question 4) | It is named (SIP, participant or receipt), and any change is dated |
| A2 | The meaning of `?` (question 3) | It is defined, or stated to mean "no condition available", for 2016-2021 |
| A3 | Whether bid/ask are the consolidated best quote (question 1) | It is stated, with the construction method |
| A4 | Locked/crossed interpretation (question 1) | A provider statement exists, so our proposed treatment can be checked against it |
| A5 | Filtering, corrections and limitations (question 2) | A list, or an explicit "none known" for 2016-2021 |

- **Not enough:** an incomplete or ambiguous answer keeps the candidate deferred. No assumption may
  fill the gap.
- **Resuming approves nothing:**
  - It permits only a new owner decision about a spec.
  - It approves no rule, and starts no experiment and no download.
- **The pilot:** these answers would inform whether its findings can be relied on more firmly.
  *(Corrected 2026-11-11: a reply clarifies the quote data; it does not by itself validate every spread estimate or
  remove every limitation, such as the pilot covering 6 calm days.)* They would not change the cost model by themselves.

## What the answers would resolve, and what stays unknown (owner notes, 2026-11-11)

Checked 2026-11-11:
- the form <https://alpaca.markets/support/request> ("Contact support | Alpaca": name, email, subject,
  description) loads;
- the cited reference page ("Historical quotes") still defines neither `?` nor the clock behind `t`.

**Answers could resolve (quote-data semantics only):**
- whether historical SIP bid/ask records are the NBBO, so spread measurements describe the best displayed price;
- what condition `?` means, and whether non-firm or ineligible quotes are included;
- the timestamp clock, so time-weighting and "quote in force at minute X" are defined;
- known filtering, corrections and gaps for 2016-2021.

**Corrected 2026-11-11:** a reply may clarify how to read the historical quotes. It does **not** automatically validate
every spread estimate or remove every data limitation:
- **The pilot sample is small:** 6 calm days and selected windows.
- **Ambiguous answers are possible:** a partial or unclear reply leaves the questions open.
- **The estimates still need re-checking** against whatever the answers say, for example a filter or a clock change.

At most this informs the **spread** part of the cost model. The gap-down candidate could then get a new owner decision.

**Answers cannot resolve (needs real fills, or is not in quote data at all):**
- **Execution slippage:** the difference between the decision price and the actual fill, which depends on order
  type, timing, routing and latency.
- **Market impact and fill probability:** whether an order at the displayed size would have filled, and at what
  price. Displayed size is not depth, and hidden liquidity is not shown.
- **Fees in practice:** regulatory fees, and any per-order costs on the actual account.
- **Paper-fill realism:** Alpaca's paper fills are simulated and are not proof of real-money fills.
- **Whether any strategy has an edge.**

Slippage stays an explicit assumption. **Corrected 2026-11-11:** paper fills can test order handling and Alpaca's
simulated execution, but cannot establish real-world slippage. Only real-money fills (a separately authorized live
pilot, if ever) could measure it.
