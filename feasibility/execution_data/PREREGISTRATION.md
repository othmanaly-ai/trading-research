# Execution-data access check: pre-registration

**Recorded: 2026-11-04, before any request in this check.**
- **Committed:** before running.
- **Purpose:** feasibility evidence for `research/FEASIBILITY_gap_down_opening.md`.
- **Not:**
  - a research evaluation
  - an experiment
  - an approval of any trading rule
- **No calculations:** no strategy returns and no parameters.
- **Authorized:** by the owner on 2026-11-04, as a bounded, read-only check.

## Dates (all in the development period, 2016-01-04 to 2021-12-31)

**Selection rule:**
- 6 sessions drawn uniformly at random from the 1,511 XNYS development sessions, with Python
  `random.Random(20261105).sample`, seed fixed before the draw.
- No price, return or volatility information was used.
- Plus **1 session chosen by the corporate-action calendar only**: 2019-06-21. That is the third
  Friday of June 2019, where SPY's quarterly ex-dividend date is expected. This expectation is
  **unverified**; the corporate-action record checks it. If it is not an ex-date, that is
  reported, and no other date is substituted.

| # | Session | Prior session | Why chosen |
|---|---|---|---|
| 1 | 2016-10-19 | 2016-10-18 | random draw |
| 2 | 2017-01-19 | 2017-01-18 | random draw |
| 3 | 2017-03-27 | 2017-03-24 | random draw |
| 4 | 2019-05-07 | 2019-05-06 | random draw |
| 5 | 2020-12-02 | 2020-12-01 | random draw |
| 6 | 2021-07-20 | 2021-07-19 | random draw |
| 7 | 2019-06-21 | 2019-06-20 | expected ex-dividend date (corporate-action check) |

The general market history of these days may be public knowledge; they were not chosen by it.
Validation (2022-01-03 to 2024-06-28) and final (2024-07-01 to 2026-10-30) dates are refused in
code.

## Requests (HTTP GET only, host `https://data.alpaca.markets`)

| Path | Endpoint | Parameters | Per date | Page cap |
|---|---|---|---|---|
| Corporate actions | `/v1/corporate-actions` | `symbols=SPY`, `types=cash_dividend`, `start=2016-01-04`, `end=2021-12-31`, `limit=1000` | once in total | 3 pages |
| Prior close and day open | `/v2/stocks/bars` | `symbols=SPY`, `timeframe=1Day`, `feed=sip`, `adjustment=raw`, prior session to session | 1 | 2 pages |
| Raw minute bars | `/v2/stocks/bars` | `timeframe=1Min`, `feed=sip`, `adjustment=raw`, 09:30:00 to 10:02:00 ET (bars 09:30 to 10:01) | 1 | 2 pages |
| Quotes | `/v2/stocks/quotes` | `symbols=SPY`, `feed=sip`, 09:30:00 to 09:35:00 ET, `limit=10000`, `sort=asc` | 1+ | **30 pages per date** |

**Hard caps:**
- **Total HTTP requests:** 240, counted at the HTTP layer, so the client's bounded 429 waits
  count too.
- **Pacing:** at least 0.4 s between requests, which stays under the plan's 200 per minute.

**If a page cap is reached:** that path for that date is reported **INCOMPLETE COVERAGE**,
with the last timestamp received. A partial response is never treated as complete.

**If access fails (401/403, or another non-200 after the client's bounded 429 handling):**
- the exact status and message are recorded
- **that request path stops for all remaining dates**, with no retries
- other paths continue

**No substitutions:**
- no feed is substituted (no IEX in place of SIP)
- no adjustment is substituted
- nothing is bought or upgraded

## Storage

| What | Where |
|---|---|
| Downloads | `data/feasibility/execution_<UTC>/`: git-ignored, separate from `data/history/` and from every experiment |
| Committed | this file, the code, and compact sanitized findings (`FINDINGS.md`, `findings.json`), with no quotes, bars or credentials |

## Validation (pre-declared)

- **Quotes:**
  - timestamps parse and lie inside the requested window
  - order is non-decreasing
  - bid and ask are > 0 and sizes are >= 0
  - counts of crossed (ask < bid) and locked (ask = bid) quotes
  - spread in cents and in bp of the midpoint, by minute 09:30 to 09:34: median, 90th
    percentile, share at 1 cent
  - quote counts and the largest gap between quotes, per minute
  - condition and tape codes, counted
- **Bars:**
  - OHLC invariants, volume >= 0
  - 32 expected minutes (09:30 to 10:01), missing minutes listed
- **Daily:**
  - the prior-session raw close and today's raw open are recorded
  - whether the daily close equals the official closing auction price is **not verifiable** here
- **Raw vs adjusted:** the price ratio between raw bars and the locally stored `all` bars for the
  same minutes. This is an adjustment factor, not a return.
- **Corporate actions:**
  - every dividend field returned
  - whether a declaration date exists and precedes the ex-date
  - whether 2019-06-21 is an ex-date
- **Timestamps:** provider timestamps (`t`) are kept apart from local retrieval times. The
  provider's meaning of `t` (participant or SIP time) is not documented here, and is labelled
  unverified.
