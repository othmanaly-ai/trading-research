# Execution-policy decisions (PROPOSED, all inactive)

**Status:** revised 2026-11-10. Nothing here is approved, active or implemented. No broker adapter exists and no
order can be submitted. The execution lab (`docs/EXECUTION_LAB.md`) does not enforce any of this. Numerical limits
and material exposure choices are left to the owner; where this document offers a default, it is a suggestion only.
The paper test plan draft is in `docs/PAPER_TEST_PLAN_DRAFT.md`.

**Three kinds of statement are kept apart:**
- **RESEARCH:** what the approved experiment specifications assumed in simulation.
- **LAB:** what `trading/execution_lab` does today.
- **PROPOSED:** what a broker policy could be. Inactive; for owner decision.

**Broker statements are labelled too:**
- **DOCUMENTED:** quoted from Alpaca's official documentation, checked 2026-11-10.
- **UNVERIFIED:** an assumption; not stated in the documentation.
- **PAPER TEST:** can only be settled by a later, separately authorized paper test.

---

## 1. Breach policy: research rules, lab behaviour and a broker policy are three different things

### RESEARCH (approved for the experiments)
From `research/001_intraday_momentum/SPEC.md` section 7 and item 7 (v1.2), and `research/002_opening_range_breakout/SPEC.md`:
- **Daily-loss breach (0.50% of session-start equity):** cancels pending entries, blocks new entries for the rest of
  the session, **and requests a risk-reducing exit at the next modeled executable opportunity**.
  - The position exits at the **next bar's open**: the same one-minute delay as entries, with gap and costs.
  - If no later bar remains, the exit happens at the next session's first bar, as an "involuntary overnight carry"
    labelled *unresolved: halt or missing data*.
  - A stop touched inside a bar takes priority over a breach marked at that bar's close.
  - A breach on the scheduled exit bar uses the already-scheduled time exit.
- **Drawdown breach (3% from the peak):** the same exit, then a **permanent halt** with no automatic reset.
  "Risk-reducing exits stay allowed."
- **Implemented in** `trading/backtest.py` (001) and `trading/engine.py` (002): `RiskState.observe` on each
  completed-bar mark, then an exit at the next bar's open.
- **Evaluation depends on it.** The recorded results of 001 and 002 assume that every breach was followed by an
  exit one minute later at the modeled open price.

### LAB (execution rehearsal)
- Reuses `RiskState`, so a daily breach blocks new entries and a drawdown breach halts them.
- **Does not exit.** No exit order is created after a breach (scenario s10 shows the block only).
- The lab is therefore *more passive than the research rule*. That is a known gap, not consistency.

### PROPOSED broker policy (the earlier draft was wrong)
The earlier draft proposed "hold under broker-side protective stops, flatten only by owner command" and called it
consistent with the approved rules. **That was incorrect.** Holding is materially different from the research rule:
- **Research assumed an exit within about one minute.** Holding could leave the position open until the stop, the
  scheduled exit or the owner acts. The loss after a breach is then bounded by the stop distance and gaps, not by an
  immediate exit.
- **Live results would not match the tested assumptions.** Results from 001/002, both failed and closed, assumed
  exit-on-breach. Any future strategy evaluated under the same SPEC rules would also assume it.
- **An automated exit has its own risks:** it sells into the move that caused the breach, it may act on stale data
  (the roadmap forbids "exits based on stale data"), and paper fills are idealised.

**The decision, left to the owner:**
- **(a) Match the research rule:** after a breach, automatically send a risk-reducing exit at the next executable
  opportunity. It must be gated on fresh data, and on confirmed cancellation of any open entry first (wash-trade
  protection).
- **(b) Hold:** keep the position under protective orders and exit only by owner command.

Either choice must then be written into future strategy SPECs, so evaluation and execution agree. No default is
selected here. Note that with (b), the protective orders must already exist and be confirmed (section 2).

---

## 2. Partial fills: what actually protects a filled quantity

### DOCUMENTED (Alpaca, "Placing Orders", Bracket / OTO / OCO sections)
- **Bracket legs wait for a complete fill.** Quote: the take-profit and stop-loss orders "won't be active until the
  first order is completely filled". **A partially filled bracket entry therefore leaves its filled shares without
  an active stop.**
- **Cancelling one order cancels the group.** "If any one of the orders is canceled, any remaining open order in the
  group is canceled." Cancelling the unfilled remainder of a partially filled bracket entry is documented to cancel
  the (not yet active) legs too, leaving the filled shares with **no** broker-side protection.
- **Exit orders need an existing position.** "Alpaca's system only accepts exit orders for existing positions", and
  two separate closing orders would be seen as "exceeding the available position quantity".
- **OCO** covers an already-open position with a take-profit and a stop submitted together. Bracket legs (and OCO)
  can fill together in fast markets: "both orders may fill before the cancellation occurs".
- **Bracket rules:** time-in-force must be day or gtc; extended hours are not supported. If the take-profit partially
  fills, the stop is reduced to the remaining quantity.
- **OTO:** "Either of take_profit or stop_loss must be present ... the rest of requirements are the same as the
  bracket orders."
- **Wash-trade protection (paper too):** an order that could interact with your own open opposite order is rejected
  with HTTP 403. For example, a stop sell while a limit buy is open is "always rejected"; a limit sell while a limit
  buy is open is rejected if the buy limit is at or above the sell limit.
- **Paper fills:** eligible orders receive a random-size partial fill 10% of the time; order size isn't checked
  against displayed liquidity.

### UNVERIFIED (assumptions; not stated)
- That OTO legs also wait for a complete fill (the documentation says only that the requirements are "the same").
- How long it takes, after a cancel is confirmed, before a new stop or OCO for the filled quantity is accepted.
- Whether a stop for the filled quantity is accepted while the remainder of the entry is in `pending_cancel` (the
  wash-trade table suggests it is rejected while the buy is open).
- Whether the trade-update stream redelivers fills missed during a disconnect. Reconciliation must not rely on it.

### What protects a filled quantity in each situation

| Situation | Broker-side protection | What remains |
|---|---|---|
| Entry completely filled, bracket/OTO legs acknowledged as active | The stop leg (DOCUMENTED for bracket) | Gaps through the stop; a stop is not a price guarantee |
| Entry **partially** filled, remainder open | **None** (bracket legs inactive; a separate stop sell would be wash-trade rejected while the buy is open) | All filled shares are unprotected until the remainder is resolved |
| Remainder cancel requested, not confirmed | **None** | Same, plus the remainder may still fill |
| Remainder cancel confirmed, protective order submitted but not acknowledged | **None** until acknowledged | Same; the submission can itself have an unknown outcome |
| Broker unreachable | Only orders the broker already holds; nothing new can be placed or confirmed | Local code can't protect anything; the owner must be alerted |

**Conclusion:** attaching a stop does **not** protect partial fills. Every design has an unprotected interval, and
that interval must be **bounded and reported**, never left open-ended.

### Ways to bound the unprotected interval (options, not decisions)
1. **Fill-or-kill limit entry (DOCUMENTED: `fok` exists).** No partial fill can exist. After the full fill, submit an
   OCO or stop for the full quantity. The unprotected interval runs from fill to stop acknowledgement. FOK can't be a
   bracket (bracket time-in-force must be day or gtc).
2. **Immediate-or-cancel entry (`ioc`).** Partial fills are possible, but the remainder is cancelled by the broker at
   once. Then protect the filled quantity with a stop or OCO. Same interval as option 1.
3. **Bracket with day time-in-force.** Protection is active only after a complete fill. A partial fill needs
   cancel-confirm-protect, during which the filled shares are unprotected, and the cancel also removes the legs.

**For all three:** if protection is not acknowledged within a maximum unprotected time, entries are blocked and the
owner is alerted. **Whether to then close the unprotected shares automatically is a material exposure decision for
the owner.** No default is selected, and indefinite unprotected exposure is **not** an acceptable default: whichever
option is chosen, the maximum unprotected time and the action when it's exceeded must be decided before any test.

### PAPER TEST (must be established, not assumed)
- **P1:** a partially filled bracket entry; confirm the legs stay inactive, and what cancelling the remainder does to
  the legs.
- **P2:** whether OTO legs activate on a partial fill.
- **P3:** whether a stop for the filled quantity is accepted while the remainder is pending cancel.
- **P4:** time from fill to protective-order acknowledgement, for FOK or IOC plus OCO/stop.
- **P5:** stream versus REST: whether fills during a stream disconnect are visible afterwards through REST.

---

## 3. Unknown submission outcomes

**Principle:** a timeout, or a single "not found" response, is **not** proof that the broker never received an order.
- The order may be in transit (`pending_new` exists).
- The lookup itself may fail.
- Visibility after submission is undocumented (UNVERIFIED).

The intent is therefore never resubmitted, and its quantity counts as live exposure until resolved.

**PROPOSED reconciliation (inactive):**
1. **Mark UNKNOWN immediately** when no response arrives. Block all new entries. Count the full quantity as pending
   exposure.
2. **Gather evidence repeatedly; no single answer decides.** Each round records the result as evidence:
   - (a) a lookup by client order id (DOCUMENTED endpoint);
   - (b) the list of all orders since the intent's creation time, matched on client order id and on
     symbol/side/quantity;
   - (c) positions;
   - (d) account fill activity since the intent.

   Rounds start immediately, then repeat at increasing intervals. The owner sets the schedule and the escalation time.
3. **Resolved only by:**
   - (a) the broker showing the order, in any status, in which case that record is adopted, with its fills applied
     by execution id; or
   - (b) an **owner decision** recorded in the ledger, after reviewing every evidence round and the broker's order
     list for the whole session.

   Absence of evidence never resolves it automatically.
4. **Escalation:** after the owner-set time, alert the owner; entries stay blocked; the evidence rounds continue.
5. **No resubmission of the same intent, ever.** A new attempt would be a new intent with a new client order id,
   created only after resolution. Because resubmitting a lost order risks a double position, a new attempt in the
   test requires owner approval each time.
6. **Not authorized here:** using a deliberate duplicate submission with the same client order id as a probe. That
   is itself an order submission, and the reuse behaviour is UNVERIFIED (decision A9).

The lab already follows steps 1, 3(a) and 5. It does not yet perform the list, position and activity cross-checks of
step 2, or the owner-decision path of step 3(b).

---

## 4. Decisions, in two groups

### Group A: needed to define a bounded paper-integration test (scripted, tiny, no strategy)

Each item is in plain language. Numbers are for the owner. **"Conflict"** means something already written that the
decision touches.

**A1. Test scope and size.**
- **What:** which symbol(s), maximum shares or notional per test order, maximum orders per test session, and which
  sessions (or a separate paper account).
- **Trade-off:** smaller is safer but may not exercise partial fills. Paper partial-fills about 10% of eligible orders
  at random, so some cases may need several attempts.
- **Conflict** (corrected 2026-11-11): since commit `95e130f` the dry run's closing check `exposure_none` reads broker
  evidence. Test positions in the *same* paper account during an acceptance session would make that session fail
  its exposure check: correct detection, but a lost dry-run day. The test must run after Milestone 1 is accepted
  and outside dry-run sessions, or in a separate paper account. Whether a separate account is available is
  UNVERIFIED.
- **Owner decides:** all the numbers, and which of the two separation options.

**A2. Order type and the protection approach (section 2).**
- **What:** FOK entry plus OCO/stop, IOC entry plus stop, or bracket with day time-in-force.
- **Trade-off:** FOK avoids partial fills but may not fill; IOC leaves a smaller remainder problem; brackets look
  protective but are documented to protect nothing until the entry is completely filled.
- **Conflict:** the roadmap says protective stops are placed "per the strategy spec", and no strategy is approved.
  The test choice is a test choice only.

**A3. Maximum unprotected time, and the action when exceeded (section 2).**
- **What:** how long filled shares may be without an acknowledged protective order, and what happens then.
- **Trade-off:** a short limit plus automatic close means more automated selling; a long limit or manual-only means
  more unprotected time.
- **Owner decides both.** No default; indefinite is excluded.

**A4. Unknown-outcome handling (section 3).**
- **What:** the evidence schedule, the escalation time, and approval of the "no automatic resolution, no
  resubmission" rule.
- **Trade-off:** long waits block testing; any automatic resolution risks a double order.

**A5. Cancellation handling.**
- **What:** how long to wait for a cancel confirmation before re-reading the order, and when to alert the owner.
- **Documented behaviour:** a 422 means "no longer cancelable" (for example, filled), so the order must be re-read,
  not assumed cancelled.
- **Trade-off:** short waits create noise; long waits leave uncertain exposure.

**A6. Emergency stop during the test, and its exposure (lab five-step procedure).**
- **What:** whether the stop may only block, cancel and reconcile (exposure left for the owner), or may also close
  exposure.
- **Documented behaviour:** "close all positions" exists and liquidates everything. Exits require confirmed
  cancellation of open opposite orders (wash-trade protection).
- **Material exposure decision: owner only.**

**A7. Emergency-stop reset.**
- **What:** who may clear it, and the conditions.
- **Existing rule:** the kill switch is cleared only by the owner via the CLI, with a reason.
- **Suggestion:** mirror that, and require a clean reconciliation first.

**A8. Manual activity during the test.**
- **What:** the owner agrees not to trade the test account by hand during a test.
- **Required handling:** any foreign order or position found by reconciliation stops the test.
- **Existing rule:** the roadmap says "no automatic correction; owner only".

**A9. Client order id reuse.**
- **What:** whether the test plan may include one deliberate duplicate submission (tiny, non-marketable limit) to
  learn how Alpaca treats a reused id, or whether to ask Alpaca support instead.
- **Why:** the documentation calls the id "a unique identifier" but doesn't say what happens on reuse (UNVERIFIED).
- **The probe is an order submission** and needs explicit approval.

**A10. Authorization and environment.**
- **What:** explicit written authorization for paper orders only, the time window of the authorization, and
  confirmation that live trading stays unreachable.
- **How:** the adapter is limited to the paper host and sits behind `require_order_submission_allowed()`, with
  `ORDER_SUBMISSION_ENABLED` set only for the test process.

### Group B: needed later, before any strategy-driven paper trading (can wait)

**B1. Breach behaviour (section 1).**
- **What:** exit on breach as the research rule assumed, or hold. This must agree with future strategy specs.
- **Note:** the lab currently blocks entries only.

**B2. Stale-data threshold and recovery.**
- **What:** the lab uses 180 s as a LAB PARAMETER; the roadmap leaves the recovery rule ("N consecutive minutes")
  open.
- **First:** measure, from the stored monitoring reports, how often each threshold would have blocked entries.

**B3. Requested size above the allowed size.**
- **Conflict:** research simulation **shrinks** an order to the binding cap (`size_position`), while the lab
  **refuses** larger requests.
- **Suggestion:** size once when the intent is created (as in research) and refuse anything larger that arrives
  later.

**B4. Orders per day and the entry window for a strategy.**
- **What:** the dry-run decision window exists (open to 5 minutes before the close), and `max_positions = 2` is
  approved. The daily order cap is the owner's number.

**B5. Final order type and protection for the strategy.**
- **What:** taken from the approved strategy spec, using what the paper test establishes about P1-P5.

---

## Broker facts (DOCUMENTED, checked 2026-11-10)

**Sources:** `docs.alpaca.markets/us/`:
- `reference/postorder`
- `docs/orders-at-alpaca`
- `reference/getorderbyclientorderid`
- `reference/deleteorderforaccount`
- `v1.1/reference/deleteallopenpositions-1`
- `docs/websocket-streaming`
- `docs/paper-trading`
- `docs/user-protection`
- `docs/the-intraday-margin-rule-1`
- the changelog entry of 2026-06-03 on pattern-day-trading fields

**Client order ids**
- "A unique identifier for the order", at most 128 characters; it can be retrieved by client order id.
- Reuse behaviour is not stated.

**Order statuses**
- new, accepted, pending_new, partially_filled, filled, done_for_day, canceled, expired, replaced, pending_cancel,
  pending_replace, rejected, and others.
- filled, canceled and rejected receive "no further updates".

**Cancel**
- The endpoint "attempts to cancel an open order".
- If the order is no longer cancelable (for example, filled), the reply is HTTP 422.
- pending_cancel exists, but most cancellations skip it.

**Trade-update stream**
- Sends fill and partial_fill events, each with an execution id, plus canceled and rejected.

**Bracket orders**
- Legs are inactive until the entry is completely filled.
- Cancelling one order cancels the rest of the group.
- Time-in-force must be day or gtc; no extended hours.
- Both legs can fill in fast markets.

**Order types and time-in-force (equities)**
- Time-in-force: day, gtc, opg, cls, ioc, fok.
- Order classes: simple, bracket, oco, oto.

**Close all positions**
- Liquidates every open position.

**Paper trading**
- Random partial fills 10% of the time; size not checked against liquidity.
- Wash-trade protection applies.

**Day trading**
- Alpaca states the $25,000 pattern-day-trader minimum was replaced by FINRA's intraday margin rule.
- Its PDT fields are deprecated, with removal scheduled for 2026-07-06.
- Reg T and Alpaca's equity/order-ratio and price-away checks still apply.

## Restart coverage in the lab (scenario s08)

- **What it does:** a new Ledger and Lab object, **in the same Python process**, reopen the temporary SQLite file.
  State is rebuilt only from the persisted events. The fake broker object continues across the restart, standing in
  for the remote broker.
- **Not covered:**
  - a new operating-system process;
  - a crash mid-write;
  - a crash between recording `submit_requested` and the broker call. The code records the request first, so such
    an order would be looked up, never resubmitted, but no test exercises this.
  - file locking between processes;
  - clock changes across the restart.
