# Supervised paper-order test: minimum decisions (PROPOSED, nothing approved)

**Written** 2026-11-11, after the offline execution core was verified (see "Evidence" at the end).

**Nothing here is approved or active:**
- There is no `config/intended_paper_account.json`, no `config/paper_order_test_authorization.json`, and no approved
  execution-policy value. All 11 policy fields are UNSET.
- **NO APPROVED ACTIVE STRATEGY:** the test would use scripted test orders, not a strategy.
- The recommendations below are suggestions. The owner chooses every number.
- Long form of each item: `docs/EXECUTION_POLICY_DECISIONS.md`, Group A (ids in brackets).

**How to read each item:**
- "Existing approval" states what is already approved.
- "Broker evidence still missing" lists what only an authorized paper test, or Alpaca, can settle.

---

## 1. Intended paper account [A1, A10]

**Options:**
- **(a) The same paper account the dry run observes**, used only after Milestone 1 is accepted, and never during a
  dry-run session.
- **(b) A separate paper account,** used only for the test.

**Consequence:**
- Since commit `95e130f`, the dry run's closing check reads broker evidence (positions and open orders). Test
  positions in the same account during a dry-run session would make that session FAIL its exposure check. That
  check is correct, but it would cost a dry-run day.
- A separate account avoids the conflict entirely.

**Recommendation:** (b) if Alpaca offers it; otherwise (a), on days with no dry run. Record the chosen account's
one-way reference (the dry run already observes a 12-character reference), never its number.

**Existing approval:** none.

**Broker evidence still missing:** whether a second paper account is available on this plan (UNVERIFIED).

## 2. Instruments, maximum quantity, notional exposure, test-loss limit [A1, plus a new item]

**Options:**
- One instrument or several.
- Shares per order, notional per order, orders per session.
- **A test-loss limit:** the paper loss after which the campaign stops.

**Consequence:**
- Smaller orders are safer and produce cleaner evidence.
- The partial-fill test may need several attempts. The draft notes that paper partial-fills at random, about 10% of
  eligible orders.
- **There is currently no test-loss limit anywhere** (code or record). The status is NOT DEFINED.

**Recommendation:** a single liquid symbol the monitor already observes (SPY). Use the smallest whole-share
quantities that still exercise each behaviour, and a test-loss limit that ends the campaign. **The numbers are
yours;** none is proposed here.

**Existing approval:** the owner risk baseline (0.10% risk per trade, 5% notional, and so on) is approved for
**simulation** only. It is not a test limit.

**Broker evidence still missing:** paper partial-fill frequency for small orders, and paper fees (the lab assumes
the BASE cost model).

## 3. Entry order type and handling of partial fills [A2]

**Options** (all limit orders):

| Time in force | Behaviour |
|---|---|
| DAY | The remainder keeps working: the largest unprotected-remainder problem |
| IOC | The unfilled remainder is cancelled immediately |
| FOK | All or nothing: no partial fills, but it may not fill at all |

Protection approach:
- **Bracket:** the stop leg is documented to stay inactive until the entry is *completely* filled.
- **Stop after fill:** a stop for the filled quantity, placed only after the entry is final.

**Consequence:** the lab proves the bracket gap (scenario s13: 25 shares unprotected while the leg is HELD). Stop
after fill needs a confirmed cancellation of the remainder first, because of wash-trade protection (scenario s14).

**Recommendation:**
- **IOC limit entries with stop after fill** for the normal tests.
- One deliberate DAY limit for the partial-fill and cancellation tests.

**Existing approval:** none (`order_type`, `time_in_force` and `protection_method` are UNSET).

**Broker evidence still missing:**
- time from fill to an acknowledged stop
- whether IOC partial fills behave as documented in paper
- whether the inactive bracket-leg status is literally "held" (UNVERIFIED)

## 4. Unprotected exposure and emergency action [A3, A6]

**Options:**
- **A3: the maximum unprotected time, and the action when exceeded.**
  - "block and alert" is implemented.
  - "close exposure" is **NOT IMPLEMENTED**: no automatic liquidation code exists.
- **A6: what an emergency stop does with remaining exposure.**
  - "leave for owner" (the owner closes it by hand in the Alpaca dashboard), or "close exposure" (not implemented).

**Consequence:** with "block and alert" and "leave for owner", nothing is ever sold automatically. The owner must be
present to act.

**Recommendation:** block and alert, plus leave for owner, with the owner present for every test session. **Not
approved here:** automatic liquidation stays unavailable.

**Existing approval:** none.

**Broker evidence still missing:**
- whether a stop for the filled quantity is accepted while the remainder is pending cancel (wash-trade rules suggest
  rejection)
- the behaviour of "close all positions" (documented, never exercised)

## 5. Unknown-outcome and cancellation escalation [A4, A5]

**Already enforced in code (offline):**
- an unknown submission outcome is never resubmitted and blocks all entries
- only a broker record resolves it
- a cancel request is not a cancellation

**Options:**
- how long, and how often, to look an unknown order up by client order id before escalating (A4)
- how long to wait for a cancel confirmation before re-reading and escalating (A5)

**Consequence:** short timers stop a test session sooner. Long timers leave uncertain exposure for longer.

**Recommendation:** escalate to the owner (and stop the session) at the first unresolved timer expiry, with timers
set from the T2 lookup-timing measurement.

**Existing approval:** none (timers UNSET; the city shows them as attention items only).

**Broker evidence still missing:**
- **Lookup of an unknown client order id:** how quickly an order becomes visible by client order id, and what
  status is returned when no order matches. The adapter assumes 404 (UNVERIFIED).
- **Reused client order id:** whether Alpaca rejects it (UNVERIFIED; probing it is itself an order and needs
  approval, A9).

## 6. Reset authority and manual-account activity [A7, A8]

**Options:**
- **Reset:** who may clear an emergency stop or kill switch, and after what.
- **Manual activity:** a promise not to trade the test account by hand during a test.

**Consequence:** reconciliation already reports manual orders, positions and cash differences, never corrects them,
and blocks entries (scenario s16).

**Recommendation:**
- Reset by the owner only, through the CLI with a written reason, after a clean reconciliation (this mirrors the
  existing kill-switch rule).
- No manual trading in the test account during a test; any foreign order or position stops the test.

**Existing approval:** the dry run's kill-switch reset rule (owner only, with a reason) exists for the dry run.

**Gap:** that kill switch is **NOT CONNECTED** to the execution core. It must be connected before a first order.

---

## Evidence for "offline milestone verified" (2026-11-11)

**18 synthetic scenarios** against the fake broker, all EXPECTED, with invariants recomputed from the ledger. They
include:
- partial fills
- duplicate and out-of-order updates
- unknown outcomes
- reconciliation
- cancellation races
- restart
- emergency stop
- a live order missing at the broker

**7 fresh-process crash drills,** each recovering in a new process from the ledger and the broker file alone:
- before the intent
- after the intent record
- after validation
- after the submission record
- after the send
- during partial fills
- during a cancel

**Offline paper-adapter tests:** fixture transport only. The guard is called before every write. No module can send
an HTTP write.

**Three defects found and fixed this round:**
1. A live order missing at the broker was treated as reconciled (now a discrepancy that blocks entries).
2. A repeated cancel request after a restart was dropped as a duplicate.
3. An intent orphaned by a crash during the checks stayed open forever.
