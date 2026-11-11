# Milestone 1 dry run: what counts as pass, failure, interruption and incomplete

**Status:** written 2026-11-09, **before any real-session evidence was collected**. Changing these
rules later restarts the five-session count.

**Owner decision (2026-11-09):** five consecutive scheduled market sessions must PASS. This verifies
that the dry-run **operates** correctly. It says nothing about profitability, and no strategy is
involved.

**Implemented in:** `trading/operations/report.py` (`classify`, `acceptance`). Tests:
`tests/test_operations_runner.py`.

## Amendment 2026-11-10: broker evidence for "no exposure" (owner-authorized correction)

**Defect found.** Until this amendment, the closing step at 15:55 ET recorded `exposure_none` as passed with the note
"DRY_RUN holds no positions and contains no order code". It never asked the broker, and the classification below did
not look at closing checks at all. The runner's description ("confirms the closing phase holds no exposure") and
`docs/OPERATIONS.md` claimed a verification that did not happen.

**Correction.** The owner authorized this correction on 2026-11-10, knowing it changes the operations fingerprint.
- `exposure_none` is now read-only broker evidence: the paper account's identity (trading host plus a 12-digit
  one-way account reference), its positions, and its open orders, including partially filled ones. The observation
  time is recorded.
- It runs at the 08:45 and 09:25 ET checks (and at a late start) as a dependency check, and again at 15:55 ET.
- **VERIFIED_NONE** is the only passing result.
- **EXPOSURE_FOUND** lists what was found. Nothing is closed or cancelled.
- **UNVERIFIABLE** covers missing credentials, a failed request, a malformed or incomplete response (a full
  open-order page), a slow observation, a wrong environment, or an account that differs from the one observed
  earlier in the session.

**New reasons (for sessions dated 2026-11-11 and later):**
- **F9** Unexpected exposure found at the broker in any check (positions or open orders). DRY_RUN must hold none;
  owner review required.
- **I6** The runner reached the closing step, but the closing exposure was not verified by broker evidence:
  - no closing record;
  - a record without a broker observation (a local assertion is not evidence);
  - UNVERIFIABLE;
  - an observation taken before the closing phase;
  - no verified observation earlier in the session to compare the account with;
  - the account differs from the earlier observation.
- **N4** (extended) The final pre-open exposure check failed or was not recorded.
- **PASS** additionally requires item 9: a VERIFIED_NONE exposure observation at the closing phase, for the same
  account as the earlier verified observation in that session.

**Records before this amendment are not relabelled.** Sessions dated before 2026-11-11 keep the classification they
had under the original rules. Their closing check stays what it was: a recorded assumption, not evidence. This does
not weaken anything: before the amendment no session had passed (2026-11-09 INTERRUPTED, 2026-11-10 INCOMPLETE;
streak 0 of 5).

**Effect on the count.** The fingerprint changed from `461c31297c5a6c1e`, on which no session had run, to the
corrected version's fingerprint (`PROGRESS.md`). The five-session count was already 0, so no counted session is lost.
The count starts with the first session that runs the committed corrected code. No other requirement or waiting
period is added.

**Also labelled, not changed (2026-11-10; SUPERSEDED by the correction below).** `calendar_agreement` within 5 s
of the open or close is not compared. It is now recorded as `compared: false`, "SKIPPED ... an explicit assumption,
not evidence". Its pass/fail value is unchanged, because the first periodic check falls at 09:30:00 ET. Changing it
would turn every on-time session into a failure without adding evidence; that would need a separate owner decision.

**What the 15:55 ET observation proves, and what it doesn't.**
- **It proves:** at its recorded observation time (seconds after 15:55 ET), the paper account answered from the paper
  host, was the same account as at the earlier verified observation, and listed no positions and no open orders
  (including partially filled ones).
- **It doesn't prove:**
  - the account state after that moment: an order placed between 15:55 and 16:00 could still fill at the close, and
    nothing is checked after the close;
  - that nothing happened between the observations (08:45, 09:25, 15:55): an order opened and closed between two
    snapshots is not visible to a positions-and-open-orders check.
- **Why that is acceptable:** the dry run contains no order code (a static test enforces it), so this check guards
  against outside or manual activity; it is not a full audit.
- **The approved Milestone 1 requirement** (roadmap, and the rules above) asks for an after-close **report**, not an
  after-close **account reconciliation**; broker reconciliation belongs to Milestone 3. The after-close step at
  16:20 ET therefore does not query the broker, and acceptance uses the 15:55 observation as a **pre-close
  observation**.
- **Adding an after-close account check would be a new requirement**, which needs an owner decision. It would not
  need any extra waiting: the runner is already running at 16:20 ET.

**Calendar agreement: corrected 2026-11-11.** The superseded note above was wrong. It said the first
periodic check falls at 09:30:00 ET, so the 5-second boundary skip would affect every session. In fact:
- The first periodic check runs 30 minutes after the 09:25 ET final check, at 09:55 ET.
- The real records of 2026-11-09 and 2026-11-10 hold 26 calendar checks, **all actually compared, none skipped**:
  pre-open or late start, the 09:25 final check, then every 30 minutes.
- A comparison within 5 s of the open or close (possible only for a start or restart at that moment) is now recorded
  as **not compared, ok=false**. Under the existing rules (N4 for the final check, N5 for a periodic check) it cannot
  count as verified.
- On-time sessions are unaffected. Their required comparisons are positive: at 08:45 and 09:25, the broker's next
  open equals the XNYS open; in session, both sides are open and the broker's next close equals the XNYS close.

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
9. (From 2026-11-11, see the amendment) A VERIFIED_NONE broker exposure observation at the closing phase, for
   the same account as the earlier verified observation that session.

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
