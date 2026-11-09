# Milestone 1 dry run: what counts as pass, failure, interruption and incomplete

**Status:** written 2026-11-09, **before any real-session evidence was collected**. Changing these
rules later restarts the five-session count.

**Owner decision (2026-11-09):** five consecutive scheduled market sessions must PASS. This verifies
that the dry-run **operates** correctly. It says nothing about profitability, and no strategy is
involved.

**Implemented in:** `trading/operations/report.py` (`classify`, `acceptance`). Tests:
`tests/test_operations_runner.py`.

## Principle: missing evidence is never a pass

- A session is PASS only if positive evidence for every requirement below exists in the records.
- Anything absent counts as INCOMPLETE or INTERRUPTED: a run, a check, a decision minute, a
  heartbeat, the after-close step.
- **Precedence, when several apply:** FAIL > INCOMPLETE > INTERRUPTED > PASS. Every applicable
  reason is listed, not only the deciding one.

## Fixed parameters

| Parameter | Value | Why |
|---|---|---|
| Latest on-time start | before the final pre-open check (09:25 ET) | the pre-open checks must have run before the open |
| Decision minutes | every minute from the open to 5 minutes before the close (385 on a regular day, 205 on an early close) | the DRY_RUN decision window; no strategy defines a narrower one |
| Decision timing | each minute's decision is recorded **within that minute** | a late decision would be a replay; missed minutes stay missed |
| Heartbeat | every 15 s; a gap over 90 s is an interruption | detects sleep, freezes and kills |
| Clock tolerance | 2.0 s against the broker clock, at the pre-open check and every 30 min | engineering default (roadmap); not yet an owner decision |
| Disk | at least 1 GB free in the runtime folder | room for records |
| Market-data dependency | the monitoring worker alive in at least 95% of decision minutes | the dry run must observe the data it would depend on. Freshness is reported, not gated (IEX quiet minutes are normal) |
| After close | the runner stays until 20 min after the close, then writes the report | the 15-min SIP delay plus a 5-min margin, matching monitoring |

## FAIL: a safety or correctness violation

Any one of these:
- **F1** Any decision recorded with entry **allowed**.
- **F2** A decision recorded for a minute other than the current one, or outside the decision
  window (a replay, a future decision or a wrong phase).
- **F3** The order guard found enabled, or `TRADING_MODE` not `paper`. The runner refuses to start
  and records why.
- **F4** An environment other than DRY_RUN.
- **F5** Runtime records inside OneDrive or the project folder (refused at start).
- **F6** An unhandled software error in the runner (recorded as an `exception` event, or a run that
  ended in `crash`).
- **F7** The report does not reconcile with the records: decision counts, or denial-reason tallies.
- **F8** Two decisions for the same minute.

## INCOMPLETE: not enough evidence to judge

- **I1 NOT RUN:** no run record for a scheduled session.
- **I2 Late start:** the first run started at or after the final pre-open check.
- **I3** No final pre-open check recorded.
- **I4** The records for the session cannot be read.
- **I5** The operations code at run time was not exactly a committed version: uncommitted or
  untracked changes existed in `trading/operations/` or the other fingerprinted files.
  - Every run records the commit hash and whether the code matched it.
  - The session report lists them under `code_version`.
  - Added 2026-11-09, before any session evidence.

**PENDING:** the session's report time has not been reached. It is not a classification and is not
counted.

## INTERRUPTED: it started properly, but operation broke

- **N1** At least one decision minute is missing.
- **N2** A heartbeat gap over 90 s between the start and the after-close step.
- **N3** The runner did not reach the after-close step: stopped, killed, machine asleep or
  restarted.
- **N4** A dependency check failed at the final pre-open check: credentials, broker clock or
  account, calendar agreement, clock skew, disk, records, or the monitoring worker.
- **N5** A periodic in-session check failed or could not be performed (broker clock, skew).
- **N6** The monitoring worker was alive in fewer than 95% of decision minutes.

## PASS: all of these, with evidence

1. A run started before the final pre-open check (on time).
2. The final pre-open check is recorded, with every check OK.
3. Every decision minute is recorded exactly once, within its minute, and **denied**, with
   reasons.
4. The heartbeat has no gap over 90 s.
5. The periodic clock checks are recorded and within tolerance.
6. The monitoring worker was alive in at least 95% of decision minutes.
7. The runner reached the after-close step, and the report reconciles with the records.
8. No FAIL, INCOMPLETE or INTERRUPTED reason applies.

**Allowed, and not counted against a PASS:**
- The kill switch being ON (an owner drill): it only adds a denial reason.
- Stale data minutes: these are reported.

## Counting five consecutive sessions

- **Which sessions count:** XNYS sessions in calendar order, starting from the first session with any
  run record. Weekends and holidays are not scheduled sessions and are skipped.
- **The streak:** any non-PASS session, **including NOT RUN**, resets it to zero.
- **Same code:** all five sessions must share one operations-code fingerprint, recorded per run:
  - a hash of `trading/operations/*.py` and `config/approved_strategies.json`
  - plus `trading/sessions.py`, `trading/safety.py` and `trading/alpaca_client.py`

  A change to that code restarts the count. Each counted session must also have run exactly a
  committed version (I5), so the evidence is tied to the commit shown in its report.
- **Milestone 1 operation is accepted** when five consecutive scheduled sessions are PASS with one
  fingerprint, and the offline test suite passes at that code.
- **Command:** `python -m trading.operations acceptance`.

## What a PASS does not mean

- It does not mean the data is suitable for execution, that any strategy is profitable, or that
  orders would work.
- No orders exist in Milestone 1.
