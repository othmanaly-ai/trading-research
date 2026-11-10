# Prospective monitoring reliability gate: PROPOSAL (not active)

**Status:** proposed 2026-11-09, awaiting owner approval.
- **Not implemented as a pass/fail rule:** nothing is reclassified by it, and no earlier session
  is evaluated under it.
- **If approved:** it applies only from the first scheduled session after approval.

## Why a second measure is needed

- **The existing rule** (docs/MONITORING.md: 5 consecutive sessions, each FINALIZED or INCOMPLETE
  with a stated reason) measures **report completion**. It stays unchanged, and the city now
  labels it "Report completion".
- **What it does not measure:** whether the session was actually observed live.
- **Observed so far** (Nov 4, 5, 6 and 9), all four FINALIZED:
  - live on-time capture was 79, 130, 109 and 115-117 of 390 minutes
  - unplanned downtime was 188, 258, 270 and 273 minutes
- **What that means:** a strategy that needs live data could not have run on any of those days.

## Definitions (all from records the monitor already keeps)

| Term | Definition | Source |
|---|---|---|
| Scheduled minutes **S** | regular-session minutes from the XNYS calendar (390; 210 on early closes) | exchange calendar |
| Expected no-trade minutes **N** (per symbol) | minutes where the **later IEX re-fetch** has no bar. IEX had no trade, so no live bar was possible. Those where SIP also had no bar are "no trade anywhere". | `q_compare.iex_present` (re-fetch), delayed-SIP comparison |
| Eligible minutes **E** (per symbol) | **E = S − N**: the denominator for live capture | derived |
| On-time live minute | a live IEX bar stored within **180 s** of the bar's end (the existing `NORMAL_LIVE_LATENCY_S`) | `bars.received_utc` |
| Late recovery | a bar stored later than 180 s (catch-up after a gap) | report "received_by_catch_up" |
| Missing | eligible minute with no stored live bar | derived |
| Unplanned downtime | session minutes not covered by a live worker run, where the worker ended without a stop request | report "unplanned_downtime_minutes" |
| After-close completion | report FINALIZED: delayed-SIP comparison through the close, and the post-close recheck done | report status |
| Unresolved failure | an incident still open at finalization, any access refusal, or any structural defect | incidents table, report |

**Late recovery never counts as on-time capture.** It is reported, but it is not credited toward G2.

## Exact measurement rules (per symbol, per session)

1. **Denominator: uses later IEX evidence, so it can only be computed after the session.**
   - **The rule:** a minute *m* is an expected no-trade minute for symbol *s* when the later IEX
     re-fetch has no bar for (*s*, *m*). That re-fetch is the IEX history the monitor requests after
     the fact: `q_obs` feed `iex`, latest revision, as summarised in `q_compare.iex_present`.
   - **Why later evidence:** the live feed cannot tell "no trade on IEX" from "we missed it". Only a
     later look at what IEX reports distinguishes them.
   - **Unknown, never excluded:** if the re-fetch has no record for a minute (not compared), that
     minute is **eligible**, never excluded, and G4 fails anyway.
   - **Formula:** E(*s*) = S − N(*s*).
2. **Numerator.**
   - **The rule:** on-time minutes = minutes in E(*s*) with a live IEX bar stored at most 180 s after
     the bar's end. That is `bars.received_utc − (bar start + 60 s) ≤ 180 s`, as in the existing
     reports.
   - **Not counted:** live bars for minutes outside E(*s*), where the re-fetch shows no bar, are
     reported but not counted. Late-recovered bars (over 180 s) never count.
3. **G2 applies to each symbol separately.** SPY, QQQ and IWM must each reach on-time ≥ 99% of
   their own E(*s*). One symbol below 99% fails the session. Symbols are never averaged.
4. **Downtime (G1)** is measured from worker-run records (`m_workers`):
   - a session minute is **covered** if it lies within [`started_utc`, `last_alive_utc` + 20 s] of
     some worker run
   - uncovered session minutes are downtime
   - downtime is **unplanned** unless the run before the gap ended with exit reason "stop
     requested"
   - this is the existing `unplanned_downtime_minutes` in the evidence report
   - a stopped city server shows up here, because its worker stops too
5. **Unresolved failures (G6)** are three counts, each of which must be 0:
   - **open incidents at finalization:** incidents with `opened_utc` ≤ the report's finalization
     time and no `resolved_utc` before it (the `incidents` table)
   - **access refusals:** the report's `access_refusals`, from explicit request outcomes only.
     These are live-poll failure events whose message carries HTTP 401/403, and comparison runs
     with status `access_failure`.
   - **structural defects:** the report's SIP-comparison category "structural defect", summed over
     the session

## What "on time within 180 s" establishes, and what it does not

**It establishes** only this: our monitor stored each counted one-minute IEX bar within 3 minutes
after that minute ended, measured on this computer's clock. In other words, the collection pipeline
was running and keeping up.

**It does not establish suitability for trading execution:**
- **A delay this size is too slow to act on.** Decisions that depend on a price can need seconds,
  not minutes. Normal delay was about 22 s, and the gate tolerates up to 180 s.
- **IEX is one exchange.** It carries about 1.5-4% of volume, so its bars are not the consolidated
  market (SIP), and its prices can differ from the national best bid and offer.
- **Minute bars summarise trades after the fact.** They contain no bid/ask quotes, spread or depth,
  and nothing about what an order would actually have paid.
- **The clock is local.** It was about 1 s off the broker on 2026-11-09, which is fine at the minute
  scale and not for sub-second claims.
- **No orders, fills, slippage or order-routing latency** are measured at all.

**A passed reliability gate means "the monitor observed the session live".** It is a precondition
for any later live-data work. It is never evidence that a strategy would work or be profitable.

## Proposed gate (all must hold, for every one of SPY, QQQ, IWM)

| # | Requirement | Proposed threshold | Why this number |
|---|---|---|---|
| G1 | Unplanned downtime during the session | **≤ 2 minutes** | A crash relaunch takes about 20 s, plus up to one 60 s poll. Two minutes allows one automatic recovery, not an outage. |
| G2 | On-time live capture | **≥ 99% of eligible minutes E** (≤ 3 missed minutes on a normal day) | These ETFs trade on IEX nearly every minute. On-time arrival was 22 s median when running. 99% tolerates transient misses. A lower bar (for example 95%, about 19 missed minutes) would hide outages a live strategy cannot tolerate. |
| G3 | Expected no-trade minutes N | **reported; if N > 5% of S, flagged for review** (not a fail) | For SPY/QQQ/IWM, many no-IEX-trade minutes would be unusual. They are excluded from E so the gate does not punish real market quiet, and they stay visible. |
| G4 | Delayed-SIP comparison | **100% of S compared** | Already achieved on every finalized day; anything less means missing evidence. |
| G5 | After-close completion | **FINALIZED by close + 2 hours** | Normal finalization is close + about 45 min when the server keeps running. 2 hours allows one restart, but not "finalized the next day by recovery". |
| G6 | Unresolved failures | **0 open incidents at finalization, 0 access refusals, 0 structural defects** | Any of these means the record itself is in doubt. |
| G7 | Request failures | **reported** (counted only from explicit request outcomes; see the fix of 2026-11-09) | Failures that cost live minutes are already caught by G1/G2. A count alone does not say whether data was lost. |

- **Reliability streak:** 5 consecutive scheduled sessions passing G1-G6, counted only from the
  first session after approval.
- **Sessions before approval** show "not evaluated under the reliability gate".
- **Separate from the dry run:** the dry-run acceptance (docs/DRY_RUN_ACCEPTANCE.md) is its own
  rule, and this gate does not replace it.

## What approval would change

1. **Code:** a function computes G1-G7 for a finalized session from its stored report and the
   comparison records, and displays the result next to "Report completion" in Market readiness.
2. **Prospective only:** the gate starts from the next session after approval. Stored reports and
   their versions are not modified.

## Decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| 1 | Adopt G1-G6 as the reliability gate? | Yes, prospectively |
| 2 | Thresholds | As above: 2 min, 99%, 5% review flag, 100%, close + 2 h, zero unresolved |
| 3 | Streak length | 5 consecutive sessions (matches the existing targets) |
