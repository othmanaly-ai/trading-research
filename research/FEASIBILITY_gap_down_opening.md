# Feasibility note: gap-down opening reversal (not an experiment)

Status: **feasibility only (2026-11-04)**
- No experiment 003, spec, lock or variant exists.
- No returns were computed, no data was fetched, and risk limits are unchanged.
- Sources: existing specs (`001_intraday_momentum/SPEC.md`, `002_opening_range_breakout/SPEC.md`),
  `NEXT_HYPOTHESES.md`, `EXPLORATION_LOG.md`, `docs/MONITORING.md`, and today's monitoring
  report. That report is operational evidence, not research data.

## 0. Correction

The alternative proposed in chat on 2026-11-04 was: buy at the 09:31 open, keeping the
09:30-09:59 low as the stop. That is **inconsistent**, because the 09:30-09:59 low is only known
at 10:00, after the entry. It is withdrawn. The stop below uses only information known before
the entry.

Also withdrawn as unsupported:
- "Low turnover makes it less cost-sensitive." What matters is the cost per trade relative to
  the gross move per trade. Turnover only scales both.
- "A shorter hold makes the estimate tighter." A shorter hold has a smaller spread of returns
  per trade, but the effect being measured may also be smaller. Costs are a larger share of a
  short move. So precision relative to the effect is not necessarily better.
- "An effect of 15-20 bp per trade is implausible for SPY." No evidence was given for this.
  The volatility figure behind it was an assumption.

## 1. Rules using only information available at each time

Labels: **[approved]** = an existing rule in an approved, closed spec (001 v1.3 / 002 v1.0),
reused as written. **[draft]** = written earlier in `NEXT_HYPOTHESES.md` B, never approved.
**[new]** = proposed here, not approved, chosen by reasoning and **not** from any returns.

| Step | Time it is known | Rule | Status |
|---|---|---|---|
| Previous close `P_prev` | before the open | previous session's official close (section 2) | [approved] definition from 001; executable source [new] |
| Gap `g` | 09:31:00 + feed latency | `open(09:30 bar) / P_prev_x - 1`, where `P_prev_x` is the previous close minus any cash dividend going ex today (section 2) | [new] |
| Signal | same | `g <= -0.5%`. The threshold is fixed and never tuned; only its trigger frequency (11.1% of development sessions) was seen. | [draft] |
| Data checks | same | 09:30 bar exists and passes `Checks` (002 section 1). Otherwise no trade. | [approved] |
| Decision price `P_D` | same | close of the 09:30 bar | [new], same pattern as 002 (signal bar's close) |
| Entry | 09:32 | marketable limit buy at the **open of the 09:32 bar**. Rejected, never resized, if the open is above the executable limit (002 invariant 2). If there is no 09:32 bar, use the first bar in [09:32, 09:34]; otherwise the entry expires. | 2-minute delay [new]; order model and fallback [approved] |
| Stop | fixed at the decision | `S = P_D x (1 - abs(g))`: the decline may continue by as much again as the gap before the thesis counts as wrong. Touch counts within a bar; a bar opening below S fills at its open; a touch in the entry bar counts (pessimistic). | level [new]; fill handling [approved] |
| Sizing | at the decision | 002 rule with L replaced by S: `min(0.001 E / ((P_D - S) + RT), 0.05 E / P_D, gross cap, 1% participation)`. Since `abs(g) >= 0.5%`, the 5% notional cap will usually bind. | [approved], applied to a [new] stop |
| Scheduled exit | 10:00 | market sell at the **open of the 10:00 bar**. Stop active through the 09:59 bar. | [new] horizon; exit convention [approved] |
| Risk controls | | owner baseline, daily and drawdown halts, one entry per session | [approved], unchanged |

**Why the entry is at 09:32 and not 09:31:**
- In real operation the 09:30 bar is complete only at 09:31:00.
- Today's monitoring received completed IEX bars a median 21 s after their end.
- So the 09:31 bar's open has already traded before a decision is possible.
- The 09:32 open is the earliest price this system could plausibly act on. Even that is a
  first trade, not a guaranteed fill.

**Free choices the owner would have to approve before any test** (none may be chosen from returns):
- the stop formula
- the 2-minute delay
- the 10:00 exit
- the dividend rule

## 2. Previous close and opening price in real operation

| Item | Development data (stored) | Real operation (free plan) | Gap between them |
|---|---|---|---|
| Previous close | SIP daily bar close, adjustment `all` | Raw daily bar, or the official close, available after the previous session | Adjusted values are scaled for later dividends and are **not executable prices** |
| 09:30 opening price | SIP 1-minute bar open: first consolidated trade in that minute | IEX 09:30 bar, available about 09:31:20. SIP for 09:30 only arrives after 09:45 (15-minute delay), too late. | IEX's first trade can differ from the consolidated open and from the opening auction price. A minute with no IEX trade gives no bar, so no trade. |
| Corporate actions | `all` removes ex-dividend drops from the history | Raw prices fall by the dividend on the ex-date | A raw-price gap on an ex-date includes the dividend. That is mechanical, not a sell-off. |

Rules needed:
- **Executable prices:** they are always **raw**. Adjusted data may only be used to compute
  the ratio `g`, and the record must say so. It is never substituted silently for a fill or
  stop price.
- **Live:** `P_prev_x = P_prev - declared dividend` on ex-dates, using a dividend amount known
  before the open. Our read-only client has no corporate-actions method today. Until one is
  added and verified, **ex-dividend sessions are skipped**: no trade, not recorded as a
  signal.
- **Development:** a correct test needs **raw** SIP bars plus dividend records for the
  development period. We store only `all`. A re-fetch of raw development data is allowed (not
  a held-out period), but it has not been done.
- **Feed mismatch:** a SIP-based development test cannot show how IEX-based live signals
  behave. Today's IEX-vs-SIP close differences (median 0.3-0.7 bp) are small next to a 50 bp
  threshold. But the opening minute was not measured separately, and it is one day.

## 3. Can minute bars represent the opening?

| Element | Represented by minute bars? | Label |
|---|---|---|
| Opening spread | **No.** Bars have no bid/ask. The 001 spec itself notes that opening spreads are wide and unmeasured (001 SPEC, sections on costs). The model uses 0.5 bp per half-spread at base and 1 bp at stress. | **UNMEASURED COST** |
| Slippage beyond the spread | No; modeled at 0.5 bp per side (base) and 2 bp (stress) | **UNMEASURED COST** |
| Execution delay | Partly. A 2-minute delay is enforced by rule. Real delay comes from today's monitoring (median 21 s receipt) plus order routing, which is unmeasured. | approximate |
| Entry fill | The bar's open is the first trade, not our fill | **AMBIGUOUS FILL** |
| Stop behaviour | The order of high and low inside a bar is unknown. A touch counts pessimistically, but fill at the stop price can be optimistic in a fast opening market. | **AMBIGUOUS FILL** |
| Halts / limit-up-limit-down near the open | They show only as missing bars | data check, no fill invented |
| Opening auction | It is not identified in bars | not modeled |

The two closed experiments were cost-fragile:
- 001: costs were about 64% of the loss.
- 002: net was about zero at base and negative at stress.

This hypothesis trades at the time of day when costs are least known. A development result near
zero would therefore not be interpretable.

## 4. Prior exploration (from `EXPLORATION_LOG.md`)

- **Not computed:** returns from 09:32 to 10:00 on gap-down days were never computed.
- **001 diagnosis:** down mornings had +2.46 bp in the **last 30 minutes**. That is a different
  window, and the effect was not significant.
- **002's B3:** a 10:01-to-close long, aggregate only, all sessions. A different window.
- **Indirect exposure:** 001 computed the prior-close-to-10:00 return (r1) for every session,
  and the gap frequency was counted. Combining the two would reveal part of this outcome. That
  combination was not done and must not be done.
- **Contamination:** low to moderate. It is not zero, and it must be disclosed in any spec.

## 5. Does it warrant an experiment now?

**Not yet.**
- **Support:** the rationale is external and unverified, and we have no evidence of our own.
- **Costs:** the main thing that decides the result, the opening spread and fill quality, is
  exactly what minute bars cannot show.
- **Data:** development data is adjusted while execution is raw, and the dividend handling
  needs data we do not store.

## Recommendation

**Obtain better execution data first.** Specifically, for owner approval as a separate
read-only data milestone:
1. Check whether historical SPY quotes (bid/ask) around 09:30-09:35 are accessible on our plan
   for development-period dates, and record the refusal if not. This is unverified; it has not
   been tried.
2. Fetch raw (unadjusted) development bars and the dividend dates.

If quotes are not accessible, **defer this research path**. Do not test it on modeled opening
costs alone.
