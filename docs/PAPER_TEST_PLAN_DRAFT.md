# Paper-order integration test plan: DRAFT, NOT AUTHORIZED, NOT EXECUTED

**Status:**
- **Drafted** 2026-11-10; **updated** 2026-11-11 for owner review.
- **It authorizes nothing.**
- **Adapter:** an **offline** paper adapter exists (`trading/paper_adapter/`). It has a fixture transport only, and
  **no network transport**.
- **No orders yet:** no order has been or may be submitted until the owner approves the decisions in
  `docs/PAPER_TEST_DECISION_SHEET.md` (long form: Group A of `docs/EXECUTION_POLICY_DECISIONS.md`) and gives explicit
  written authorization.
- Everything in brackets is an owner decision.
- The test uses the **paper** endpoint only. Live trading stays unreachable by construction.

**Purpose:** establish how Alpaca's paper environment actually behaves for the order lifecycle the execution lab
rehearses, with tiny, scripted orders and no strategy. This is not a performance test, and its fills say nothing
about real slippage. Paper "is only a simulation" (Alpaca).

---

## Part 1: safety controls required BEFORE the first test order

Each control must exist and be verified offline, in the execution lab or by tests, before the first submission. If
any is missing, the test does not start.

**C1. Separation from the dry run.**
- The adapter lives outside `trading/operations/`, `trading/sessions.py`, `trading/safety.py` (except calling it),
  `trading/alpaca_client.py` and `config/approved_strategies.json`, so the operations fingerprint stays unchanged.
  It was measured as `6cc6999855edd4f1` on 2026-11-11 (commit `1ed518e`); always re-measure it, never assume it.
- The test runs **either** after Milestone 1 is accepted and never during a dry-run session, **or** in a separate
  paper account [owner: which; separate account availability UNVERIFIED].
- **Reason** (corrected 2026-11-11): since commit `95e130f` the dry run's closing check `exposure_none` reads broker
  evidence. Test positions in the same account during a dry-run session would therefore make that session fail its
  exposure check. That is correct detection, but it costs a dry-run day.

**C2. Write path gated.**
- Every submit and cancel call first calls `trading.safety.require_order_submission_allowed()`.
- `ORDER_SUBMISSION_ENABLED=true` and `TRADING_MODE=paper` are set **only** in the test process's environment, never
  in `.env`.
- The read-only client stays GET-only. The adapter is a separate module with its own host allowlist: the paper
  trading host only. A test proves the live host is unreachable.

**C3. Hard limits checked locally before every submission.**
- [max shares per order], [max notional per order], [max orders per test session], [symbols].
- Limit orders only, with a price bound [owner: how far from the reference quote].
- Any violation refuses the submission and stops the test.

**C4. Ledger first.**
- The intent and the `submit_requested` event are written to an append-only test ledger **before** each broker call,
  as in the lab.
- Client order ids are deterministic and never reused, except a probe approved under A9.

**C5. Unknown-outcome rule (decision A4).**
- No response leads to UNKNOWN: entries are blocked, exposure is counted, evidence rounds start.
- No automatic resolution, and no resubmission.

**C6. Unprotected-exposure bound (decision A3).**
- A maximum unprotected time [owner], and the action when it's exceeded [owner].
- The test stops and alerts on any breach.

**C7. Stop controls.**
- The existing kill switch, checked before every submission, blocks it.
- The lab's emergency-stop procedure: block, cancel, confirm, reconcile. The exposure action follows decision A6.
- Reset follows A7.

**C8. Reconciliation before and after every step.**
- Account status, positions, all open orders and fill activity are compared with the test ledger.
- Any mismatch or foreign order stops the test (A8).

**C9. Owner presence.** The owner watches each test session, with the Alpaca paper dashboard open as an
independent view, and can stop the process.

**C10. Records.**
- Every request, response (with HTTP status), stream event, reconciliation and decision goes to the test ledger.
- No keys are written. Account identifiers are excluded as in the existing snapshots.

**C11. Offline rehearsal passed.**
- The execution core passes all 18 lab scenarios and 7 fresh-process crash drills (done 2026-11-11). The adapter
  passes its fixture tests through the same broker port (done).
- The adapter's own tests prove: no live host, the gate is called before every write, ledger before broker call,
  no resubmission of UNKNOWN.

**C12. Authorization.** A written, dated owner authorization naming the paper account, the time window, A1-A10 and
this plan's version.

---

## Part 2: broker behaviours the test itself must establish

Each test is listed as **goal → steps → evidence → pass condition**. Expected behaviour is marked DOCUMENTED or
UNVERIFIED; the test result, not the expectation, decides. Steps use only the owner-approved size [A1].

**T1. Normal round trip.**
- **Goal:** a submission is acknowledged and becomes visible by client order id; fills carry execution ids.
- **Steps:** one marketable limit buy, then a limit sell to close.
- **Evidence:** REST order record, stream events and positions.
- **Pass:** ledger, REST and positions agree; time to visibility by client order id is recorded.

**T2. Lookup timing.**
- **Goal:** how quickly a new order is visible by client order id (UNVERIFIED). This feeds the A4 schedule.
- **Steps:** submit a non-marketable limit, then look it up immediately and repeatedly.
- **Evidence:** first-seen time.
- **Pass:** the timing is recorded over [n] repetitions.

**T3. Cancel behaviour.**
- **Goal:** a cancel request versus confirmation; 422 on a filled order (DOCUMENTED); how often `pending_cancel`
  appears.
- **Steps:** non-marketable limit, cancel, read back; then a marketable order, cancel after the fill.
- **Pass:** the ledger never marks CANCELLED without a broker confirmation.

**T4. Partial fill.**
- **Goal:** partial fills and their execution ids.
- **Note:** paper partial-fills randomly about 10% of the time, so this may need several attempts within the A1 cap.
- **Pass:** filled + remaining + cancelled always equals the ordered quantity, from execution ids.

**T5. Bracket protection (P1).**
- **Goal:** confirm the legs stay inactive while the entry is partially filled (DOCUMENTED), and what cancelling the
  remainder does to the legs (DOCUMENTED: the group is cancelled).
- **Note:** only if A2 allows brackets.
- **Pass:** the unprotected interval is measured and stays within A3, or the test stops.

**T6. OTO activation on partial fill (P2).** UNVERIFIED; same procedure as T5.

**T7. Protecting a filled quantity (P3, P4).**
- **Goal:** time from fill to an acknowledged stop/OCO, and whether a stop for the filled quantity is accepted while
  the remainder is pending cancel. The wash-trade table suggests rejection.
- **Pass:** the interval is measured, within A3.

**T8. Wash-trade protection.**
- **Goal:** confirm that an opposite order while an entry is open gets a 403 (DOCUMENTED), and that the adapter
  treats a 403 as REJECTED, not UNKNOWN.

**T9. Stream disconnect (P5).**
- **Goal:** fills during a stream disconnect are recovered through REST reconciliation, by execution id with no
  double count.
- **Steps:** a deliberate local disconnect while an order is working.

**T10. Simulated lost response.**
- **Goal:** the unknown-outcome path works against the real broker.
- **Steps:** a local fault injection drops the HTTP response after the broker accepts the order. The adapter must
  mark UNKNOWN, block entries, find the order by evidence rounds, and never resubmit.
- **Pass:** exactly one broker order per intent.

**T11. Client order id reuse (A9, only if approved).**
- **Goal:** what Alpaca does with a reused id (UNVERIFIED).
- **Steps:** one non-marketable limit, then a second submission with the same id.
- **Evidence:** the HTTP status and body.

**T12. Emergency stop with an open order.**
- **Goal:** cancellation is requested, then confirmed, then reconciled. The exposure action follows A6. The report
  stays INCOMPLETE while anything is unresolved.

**T13. Restart.**
- **Goal:** recovery after a stop with a working order.
- **Steps:** stop the test process (a real new process) while an order is working; restart.
- **Pass:** the ledger rebuilds; entries stay blocked until reconciliation; no resubmission. This closes the lab's
  same-process restart limitation.

---

## Part 3: stop conditions (any one ends the session; the owner reviews before any further test)

- **Mismatches:** any reconciliation mismatch, foreign order or position.
- **Unknown outcomes:** any UNKNOWN still unresolved at the A4 escalation time.
- **Unprotected exposure:** any unprotected quantity beyond the A3 time.
- **Limits:** any hard-limit refusal (C3); this indicates a bug.
- **Unexpected broker responses:** any response other than 2xx, 403 (wash trade, expected in T8), 404 on a lookup, or
  422 on a cancel (expected in T3).
- **Owner instruction**, or the kill switch turned on.

## Part 4: exit criteria for the test campaign

- **T1-T10 and T12-T13 completed** (T11 only if approved), with evidence in the test ledger.
- **Lab model updated where paper behaved differently,** and the lab scenarios re-run.
- **Group B decisions** in `docs/EXECUTION_POLICY_DECISIONS.md` can then be informed by measured behaviour.
- **A written report** separating DOCUMENTED expectations that held, those that didn't, and newly established
  behaviour.

Strategy-driven paper trading is a separate later step needing an approved strategy and Group B decisions.

---

## Part 5: control status today, and the exact session script (PROPOSAL, UNEXECUTED)

### Controls that must work before the first order: status on 2026-11-11

| Control | Status | What is missing |
|---|---|---|
| C2 write path gated by `require_order_submission_allowed()` | DONE offline (adapter tests) | nothing offline; the flag stays false |
| Paper-only **network** transport with a host allowlist and a "live host unreachable" test | **NOT IMPLEMENTED** | a separately authorized build step; none exists by design |
| C3 hard limits (shares, notional, orders, symbols) | enforced from the execution policy | **values UNSET** (decision sheet item 2) |
| **Test-loss limit** | **NOT DEFINED** | owner number and code check |
| C4 journal first, deterministic ids, no resubmission | DONE offline (scenarios, crash drills) | none |
| C5 unknown outcome blocks entries | DONE offline | escalation timer UNSET (item 5) |
| C6 unprotected-time bound | enforced only with a value | **UNSET** (item 4) |
| C7 kill switch checked before every submission | **NOT CONNECTED** to the execution core | wiring plus a test |
| C7 emergency stop: block, cancel, confirm, reconcile | DONE offline (s11, s12) | exposure action UNSET (item 4) |
| C8 reconciliation before and after every step, incl. an order missing at the broker | DONE offline (s06, s08, s16, s18) | none |
| C1 account separation / intended account on record | **NOT MET** | item 1, plus `config/intended_paper_account.json` written by the owner |
| C12 written authorization | **NOT GIVEN** | owner only |

**First order allowed:** only when every row is DONE or owner-approved. Today 7 rows block.

### Exact session script

Every step uses the approved limits [item 2] and policy [items 3-6]. **Before and after each step:** reconcile the
account (status, positions, every open order, fill activities and cash) against the test ledger. Any mismatch is a
stop condition (Part 3).

| # | Action | Expected observation | Stop if |
|---|---|---|---|
| 0 | Pre-flight: kill switch off; flag set only in the test process; reconcile | account ACTIVE; 0 positions; 0 open orders; cash recorded; the account reference equals the approved one | anything else |
| 1 | T2: one **non-marketable** limit buy (DAY); look it up by client order id until visible | ACK; visible by client order id; nothing filled; the time to visibility is recorded | no visibility within the A4 window → UNKNOWN escalation |
| 2 | T3: cancel it; re-read | the DELETE is a request (204); status later `canceled`; the ledger shows CANCELLED only after the broker record | CANCELLED without a broker record; 422 unexplained |
| 3 | T1: one **marketable** IOC limit buy | a fill with an execution id; position = filled quantity; ledger = REST = positions | a fill without an execution id; mismatch |
| 4 | T7: stop after fill for the filled quantity | stop accepted; the unprotected interval from fill to stop acknowledgement is measured | an interval beyond A3 → block, alert, owner acts |
| 5 | Close: cancel the stop (confirmed), then a limit sell to flat | position 0; cash change = the fills ± documented fees | position not 0; unexplained cash difference |
| 6 | T4/T5: one DAY limit sized to allow a partial fill (may need repeats within the cap) | filled + remaining + cancelled = ordered, from execution ids; bracket leg inactive while partial (if A2 allows brackets) | quantity identity broken |
| 7 | T8: an opposite stop while a buy is open | 403 recorded as REJECTED (not UNKNOWN) | anything else |
| 8 | T13: stop the test process while an order works; start a fresh process | the ledger rebuilds; entries blocked until reconciliation; no resubmission | any resubmission |
| 9 | T10: fault-inject a dropped response after the broker accepts | UNKNOWN; entries blocked; found by client order id; exactly one broker order | a second order |
| 10 | T12: emergency stop with an open order | block → cancel request → broker confirmation → reconcile; INCOMPLETE until all resolved; the exposure action follows A6 (no automatic liquidation) | COMPLETE reported while anything is unresolved |
| 11 | T11 (only if A9 approves): reuse a client order id on a non-marketable limit | the HTTP status and body are recorded | — |

**Final account-state checks** (after the last step and before the session ends):
- 0 positions and 0 open orders in the test account
- broker cash = ledger cash (fees included), or every difference listed and explained
- every order in the ledger is terminal (FILLED, CANCELLED, REJECTED or BLOCKED), with no UNKNOWN and no
  CANCEL_PENDING
- a reconciliation complete event is the last ledger entry
- the session report lists which DOCUMENTED expectations held, which did not, and the newly measured values (lookup
  timing, unprotected interval, partial-fill behaviour)

**Broker behaviours this establishes:**
- visibility timing by client order id (feeds A4)
- the cancel request versus confirmation, and 422 handling
- fill and execution-id semantics
- the protection gap in time
- wash-trade rejections
- restart and unknown-outcome recovery against the real paper API
- optionally, client order id reuse

**What it does not establish:** real-money slippage or fills. Paper is a simulation.
