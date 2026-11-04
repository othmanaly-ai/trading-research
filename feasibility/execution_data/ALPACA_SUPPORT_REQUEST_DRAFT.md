# Draft support request to Alpaca (NOT SENT)

**Status:** draft prepared 2026-11-04 for the owner to review and send personally, if they
choose.
- It has **not** been sent, and nothing in this project sends it.
- It contains no credentials, account numbers, API keys or account identifiers.
- Before sending, the owner should add only what they choose to share.

---

**Subject:** Historical SIP stock quotes (2016-2021): timestamp, condition code "?",
consolidation, corrections

Hello,

I am using the Market Data API v2 historical stock quotes for research on 2016-2021 data, and I
could not find the following in the documentation
(https://docs.alpaca.markets/us/reference/stockquotes-1 and the Market Data FAQ).

**Requests used** (GET, `https://data.alpaca.markets`):
- `/v2/stocks/quotes?symbols=SPY&feed=sip&start=2019-06-21T13:30:00Z&end=2019-06-21T13:35:00Z&limit=10000&sort=asc`
  (also the same window on 2016-10-19, 2017-01-19, 2017-03-27, 2019-05-07, 2020-12-02 and 2021-07-20)
- `/v2/stocks/meta/conditions/quote?tape=B`

**Sample records returned** (SPY, tape B):

| `t` | bid (bx, bp, bs) | ask (ax, ap, as) | c |
|---|---|---|---|
| 2017-03-27T13:30:00.008Z | Z 231.93 x 7 | M 231.94 x 100 | ? |
| 2017-03-27T13:30:00.583Z | P 231.93 x 33 | T 231.92 x 1 | ? |
| 2019-06-21T13:30:00.000495624Z | P 294.13 x 68 | Z 294.14 x 5 | ? |
| 2019-06-21T13:30:00.083493308Z | X 294.14 x 5 | P 294.14 x 20 | ? |
| 2019-06-21T13:30:00.088005892Z | B 294.15 x 5 | P 294.14 x 20 | ? |
| 2021-07-20T13:30:00.00056192Z | Z 425.65 x 5 | P 425.68 x 28 | R |
| 2021-07-20T13:30:00.447292672Z | Z 425.69 x 10 | P 425.67 x 23 | R |

**Questions:**

1. **Timestamp clock:**
   - Which clock does `t` in historical SIP quotes represent: the SIP timestamp, the
     participant (exchange) timestamp, or the time Alpaca received the quote?
   - Did its meaning, source or precision change during 2016-2021? Records before 2019 have
     millisecond precision; later ones have nanosecond precision.

2. **Condition code "?":** what does `?` mean in these historical records? It is not in the
   `/v2/stocks/meta/conditions/quote?tape=B` table. Records from 2021 show `R` instead.
   Possibilities include "not available", "unmapped" or a specific condition.

3. **Consolidation:**
   - Do the bid and ask fields represent the consolidated national best bid and offer, or
     another construction (for example, the latest quote from any exchange, or a
     per-exchange best quote)?
   - How should locked (ask = bid) and crossed (ask < bid) records be interpreted? Are they
     genuine NBBO states, an artifact of sequencing quotes from different exchanges, or
     something else?

4. **Corrections and limitations:** are there documented corrections, gaps, backfills,
   feed-source changes or known limitations that affect 2016-2021 historical SIP quotes and
   should be considered for execution research? For example:
   - changes of data vendor or processing
   - quotes withheld or filtered
   - the round-lot size convention before 2025-11-03

Thank you.

---

## Answers needed to resume the candidate (owner checklist)

The candidate stays **DEFERRED_DATA_SEMANTICS** until written answers establish all of these:

| # | Needed | Resumes only if |
|---|---|---|
| A1 | The clock behind `t`, and any 2016-2021 change | It is named (SIP, participant or receipt), and any change is dated |
| A2 | The meaning of `?` | It is defined, or stated to mean "no condition available", for 2016-2020 |
| A3 | Whether bid/ask are the consolidated best quote | It is stated, with the construction method |
| A4 | Locked/crossed interpretation | A provider statement exists, so our proposed treatment can be checked against it |
| A5 | Corrections and limitations | A list, or an explicit "none known" for 2016-2021 |

- **Not enough:** an incomplete or ambiguous answer keeps the candidate deferred. No
  assumption may fill the gap.
- **Resuming approves nothing:** it permits a new owner decision about a spec. It approves no
  rule, and starts no experiment and no download.
