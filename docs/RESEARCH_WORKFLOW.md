# Coordinator research workflow (first workflow, 2026-11-10)

**Question:** "Review our existing strategy failures and recommend the next research decision."
**Code:** `trading/coordinator.py`. **City:** the "Research workflow" view (`/api/workflows`, read-only).
**Records:** task records in `data/jobs/workflows.sqlite` (git-ignored); documents and the report in
`research/workflows/<workflow>/`.

## What it is

It reuses the research-job system's `JobStore`: its states, its rule of one completed task per input,
and its job and pipeline schema. It keeps a separate database, so the dashboard's job runner never
executes these tasks.

| Task | Who does it | Completion criteria (checked in code) |
|---|---|---|
| evidence | deterministic code | Reads an allowlist of saved research and feasibility files and `trading/costs.py`; hashes them; extracts facts. It refuses `data/`, `results/`, monitoring, held-out names, broker code and secrets. |
| strategy_analysis | **specialist role**: a submitted document | Bound to the evidence snapshot; required sections; every claim cites existing evidence; every quoted figure matches an extracted fact; only allowed requests |
| data_cost_analysis | **specialist role**: a submitted document | Same checks |
| skeptical_review | **specialist role**: a submitted document | A verdict (accept, challenge or reject), with a reason, for every claim and for the decision |
| coordinator_report | deterministic code | Assembled only from validated tasks. Rejected claims are listed apart; a rejected decision is not recommended. |

## Roles vs agents

A specialist role is a task that needs a document. It is **not** an agent running on its own.

There is no unattended model connection: the paid reviewer is OPTIONAL / DISABLED. The workflow and
the city both show this as **UNAVAILABLE**.

For the first run, all three role documents were written by Claude in the owner's interactive Claude
Code session, and recorded with that author and mode. The review is therefore a **self-review by the
same session**, not an independent one, and the report says so.

## Commands (read-only research)

```
python -m trading.coordinator start                                  # create or reuse; collects evidence
python -m trading.coordinator submit <workflow_id> <task> <doc.json>  # validates on submit
python -m trading.coordinator advance <workflow_id>                  # idempotent
python -m trading.coordinator status [<workflow_id>]
python -m trading.coordinator request <action>                       # prohibited actions exit 3 (refused)
```

## Guarantees and safety

**Duplicates:**
- An unfinished workflow is reused.
- A completed workflow for the same evidence snapshot is reused.
- Re-running `advance` creates nothing.
- A rejected document is not re-validated; a corrected one becomes a new attempt, and the failed
  attempt is kept.

**Failures:**
- Missing evidence fails the workflow.
- An upstream failure blocks its dependents, with the reason recorded.

**Refused:**
- orders (paper or live)
- experiment runs or evaluation, and reopening experiments
- downloads
- validation, final or monitoring data
- changes to risk, locks or acceptance rules
- paid model calls and purchases
- interrupting monitoring or the dry run

**Tests:** `tests/test_coordinator.py` (synthetic fixtures).
