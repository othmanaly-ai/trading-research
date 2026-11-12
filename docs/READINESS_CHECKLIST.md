# Readiness checklist while awaiting Alpaca (2026-11-11)

**What this is:** a planning list. It authorizes nothing, starts nothing and changes no rule.

**Current state:**
- H4 is unapproved.
- The pre-holiday candidate is rejected (R1).
- Risk limits are unchanged (`OWNER_BASELINE_2026_11_03`).
- Order submission is disabled.
- The Milestone 1 dry run continues unchanged (operations fingerprint `6cc6999855edd4f1`). Its count is 1 of 5 by
  the stored reports; the official number comes from `python -m trading.operations acceptance` in a normal
  PowerShell window.

## A. Blocked by the historical-quote questions

| Task | Why it waits | What a reply would and would not do |
|---|---|---|
| Relying more firmly on the spread pilot (`feasibility/spread_measurement/FINDINGS_pilot.md`) | Its figures assume quotes are eligible NBBO records with a known clock | A reply may clarify the quotes. It does **not** by itself validate every estimate. The pilot still covers 6 calm days and selected windows, and the estimates must be re-checked against the answers. |
| Resuming the gap-down candidate (DEFERRED_DATA_SEMANTICS) | Its checklist A1-A5 needs written answers | Even complete answers allow only a new owner decision. They approve no rule. |
| Any strategy whose result depends on a spread at specific minutes | Same quote semantics | Same limits |
| Proposing a change to the **spread** part of `trading/costs.py` | It would rest on the pilot | Any change is a separate owner decision and breaks the experiment locks |

## B. Can proceed independently now

| Task | Who | Needs |
|---|---|---|
| Run the dry run each session (`python -m trading.startup`, normal PowerShell window, before 08:45 ET); read each day's report | Owner starts it; Claude can read reports | Nothing new; no code changes to fingerprinted files |
| Restart the city server on 8765 when wanted (same startup command) | Owner | Nothing |
| Review the execution-policy decisions A1-A10 (`docs/PAPER_TEST_DECISION_SHEET.md`) | Owner | Time |
| Review the paper-mechanics test proposal (`docs/PAPER_MECHANICS_TEST_PROPOSAL.md`) | Owner | Time; implementing anything needs a later decision |
| Set a date to revisit if Alpaca does not reply, so research is not paused indefinitely | Owner | A date |
| Decide whether to adopt a "minimum edge" rule for future specs: an expected gross effect that clears the stress cost with margin, fixed before any data is seen | Owner | No data |
| Decide what to do with the stale app-private copy of `operations.sqlite` (left in place, `docs/OPERATIONS.md`) | Owner | Nothing |
| Offline engineering that touches no fingerprinted file. Example: wiring the kill switch into the execution core, plan control C7, currently NOT CONNECTED. | Claude, on request | A test-first change in `trading/execution_lab/`; no order code is enabled |

## C. Blocked by something other than Alpaca

| Task | Blocked by |
|---|---|
| Any new strategy experiment | No hypothesis has supporting evidence for our data (H4 not supported; pre-holiday rejected). Development data is partly used up. Spec approval comes first. |
| Shadow observation (Milestone 2) | An approved strategy (none) and Milestone 1 acceptance |
| Any paper order, including a mechanics test | Every readiness item in `trading/dashboard/execution_readiness.py`, plus the decisions and the build step in the proposal |
| **Real-world slippage** | Real-money fills only. Neither quotes nor paper fills can establish it. Paper fills test order handling and simulated execution. |
| Any live trading | A separate future proposal, with written authorization, its own limits and legal checks |
