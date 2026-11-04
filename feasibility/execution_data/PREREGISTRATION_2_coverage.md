# Amendment 2: quote coverage through the proposed exit (pre-registration)

**Recorded:** 2026-11-04, before any request in this amendment. It is committed before running.

**Authorization:** the owner, 2026-11-04 ("Check quote coverage through the proposed 10:00
exit").

**Not:**
- a research evaluation
- an experiment
- an approval of any rule

**No calculations:** no returns and no parameters.

## Dates

The same 7 development sessions as `PREREGISTRATION.md`. No additions and no substitutions.

## Requests (HTTP GET only, `https://data.alpaca.markets`)

| Path | Endpoint | Parameters | Cap |
|---|---|---|---|
| Quote conditions | `/v2/stocks/meta/conditions/quote` | `tape=B` | 1 request |
| Quotes | `/v2/stocks/quotes` | `symbols=SPY`, `feed=sip`, 09:35:00 to 10:01:00 ET (both inclusive, per the docs), `limit=10000`, `sort=asc` | **100 pages per date** |

**Hard caps:**
- **Total HTTP requests:** 360, counted at the HTTP layer.
- **Pacing:** at least 0.4 s between requests.
- **If a page cap is reached:** INCOMPLETE COVERAGE for that date, with the last timestamp received.
- **If access fails:** that path stops for all remaining dates, with no retries.
- **No substitutions:** no feed is substituted, nothing is bought.

**Overlap:** the quote stamped exactly 09:35:00 (end of the first window) can appear in both
windows. Identical records are counted once in coverage; no other record is removed.

## Validation (pre-declared)

Per minute from 09:35 to 10:00, and for the 10:00 exit minute:
- quote count
- largest gap between consecutive quotes
- minutes with no quote
- each quote classified as:
  - normal (ask > bid > 0)
  - locked (ask = bid)
  - crossed (ask < bid)
  - one-sided (bid or ask = 0, which means "no active bid/ask" per the Alpaca docs)

  with count and time-weighted shares
- spread statistics on normal quotes, reported **beside** the shares of the other classes
- nothing deleted

Storage is in `data/feasibility/` (git-ignored). Only compact findings are committed.
