# Research desk (city view "Research desk")

Read-only. The city's six departments mapped onto what is actually implemented. Every task state comes from a
stored record; with no record the state is UNKNOWN. A building is not a worker: the only continuous processes are
the market-data worker (`trading/monitor/worker.py`) and the dry-run runner (`trading/operations/runner.py`).

- Registry and Command Centre: `trading/dashboard/desk.py` (`GET /api/desk[?run=<trace run id>]`)
- One inspectable workflow: `trading/monitor/evidence_trace.py` (task records in git-ignored `data/jobs/desk.sqlite`)
- View: `dashboard/web/src/components/DeskView.tsx`
- Tests: `tests/test_evidence_trace.py`, `tests/test_desk.py` (synthetic fixture session, temp folders)

States: NOT IMPLEMENTED, DISABLED, IDLE, RUNNING, SUCCEEDED, REUSED, FAILED, BLOCKED, CLOSED, UNKNOWN.
A department's headline is its worst state (FAILED > BLOCKED > UNKNOWN), else RUNNING, else SUCCEEDED, else IDLE.

## Department-to-implementation map

| Department | Task | Implementation | Kind | State source |
|---|---|---|---|---|
| Data Centre | Live IEX collection | `monitor/worker.py` | deterministic, continuous process | depmap + readiness heartbeat |
| | Freshness | `monitor/readiness.py` (latest_data) | deterministic | stored readiness row |
| | Capture inventory / missing minutes | `evidence_trace.h_capture` | deterministic | trace task record |
| | Structural validation | `quality.bar_defects` | deterministic | trace task record |
| | IEX / delayed-SIP comparison | `quality.QualityChecker` results | deterministic | trace task record |
| | Revision tracking | q_obs revisions | deterministic | trace task record |
| | Unresolved-item explanations | NOT CONNECTED | optional model task | DISABLED |
| Research Lab | Approved specifications | `research/<id>/SPEC.md` | owner decision | STATUS.json (both CLOSED) |
| | Replay, baselines | `trading/backtest`, `trading/evaluate.py` | deterministic | CLOSED (no approved spec) |
| | Cost assumptions | `trading/costs.py` | deterministic | BLOCKED (quote semantics A1-A5 unanswered) |
| | Evaluation | `trading/jobs.py` | deterministic | research job records |
| | Critical review | `trading/coordinator.py` | deterministic + submitted documents | workflow record (self-review, not independent) |
| | Gap-down candidate | STATUS.json | owner decision | BLOCKED (DEFERRED_DATA_SEMANTICS) |
| | Independent review | NOT CONNECTED | optional model task | DISABLED (paid calls revoked) |
| Risk Office | Sizing, exposure, loss limit, halt | `trading/risk.py` + backtest | deterministic | IDLE, **simulation only, no execution path** |
| | Order-submission gate | `trading/safety.py` | deterministic | DISABLED (nothing calls it; no order code) |
| | Dry-run entry gate | `trading/operations/gate.py` | deterministic | always denies |
| | Broker reconciliation | none | — | NOT IMPLEMENTED |
| Operations | Health checks, incidents, supervision, start-up | `monitor/readiness.py`, `monitor/control.py`, `trading/startup.py` | deterministic | readiness / incidents / server_runs |
| | Dry run and acceptance | `trading/operations` | deterministic, started by the owner | operations store + runner status file |
| | Report completion (existing criterion) | `readiness.reliability_summary` | deterministic | stored reports |
| | Reliability assessment (one session) | `reliability.daily_report` | deterministic | trace task record |
| | Reliability gate G1-G4 | `docs/RELIABILITY_GATE_PROPOSAL.md` | owner approval | NOT IMPLEMENTED (proposed) |
| Evidence Archive | Locks | `trading/experiment_lock.py` | deterministic | checked on each build |
| | Journals | append-only CSVs | deterministic | row counts |
| | Daily reports (amend-only) | q_reports | deterministic | trace task record (integrity + reproduction) |
| | Provenance | `data/history` manifest | deterministic | depmap |
| Command Centre | Next eligible task | `desk.command_centre` | deterministic | all of the above |

## Evidence trace (one session)

`python -m trading.monitor.evidence_trace run --date YYYY-MM-DD` (manual; one run at a time; `list` shows runs).

capture_inventory → structural_validation, iex_sip_comparison → revision_tracking → reliability_assessment →
report_finalization. The monitoring store is copied into memory from a read-only connection and never modified.
Each task record keeps task and run ids, implementation version, parent run, dependencies, input references and
fingerprints, configuration fingerprint, code version, queued/started/finished times, status, error, attempt,
output and output fingerprint, and `source` (real records or fixture). Unchanged inputs, configuration and code
give REUSED (pointing at the original record). An upstream failure blocks its dependants only; a session whose
comparison has not reached the close is BLOCKED, not failed. Invalid output is rejected (FAILED). A run cut off
mid-task is marked FAILED ("interrupted") by the next run, which then completes with a new attempt.

"Reproduction" recomputes the stored report at its own **evidence cutoff** (`reliability.daily_report(..., as_of=)`).
New reports record the cutoff, calculation version (`REPORT_CALC_VERSION`), code version and configuration
fingerprint in `report["reproducibility"]`. That block sits outside the evidence hash, so finalization idempotence
is unchanged. For older reports the cutoff is inferred from the creation time of the version whose evidence they
carry. Every remaining difference is classified:

| Category | Meaning |
|---|---|
| later_evidence | records written after the cutoff; removed by recomputing at the cutoff |
| time_dependent | a still-running worker's last-alive time, overwritten by later heartbeats (the stored value is the only record) |
| code_change | the calculation changed after the report was stored (field added, events classified differently) |
| amendment | a recorded amend-only correction changed the field on purpose |
| defect | the stored report is internally inconsistent; an amend-only correction is available but NOT applied |
| unexplained | none of the above: investigate |

Reports are never edited to match a new calculation.

Findings on 2026-11-10:
- **11-04:** later worker runs and code versions (later_evidence), one overwritten last-alive time (time_dependent),
  `other_error_kinds` (code_change).
- **11-05 and 11-06:** only `other_error_kinds` (code_change).
- **11-09:** the recorded v2 correction (amendment) and later worker runs (later_evidence).
- **Defect (11-09 v2):** the correction moved 2 incident events out of `request_failures` but did not add them to
  `other_errors` (116, should be 118). `correct_stored_report` now counts them. A v3 correction is previewed by
  `python -m trading.monitor correct-reports`; it has not been applied.

Task inputs fingerprint only the worker runs inside the session's report window, with last-alive capped there. The
code fingerprint includes a hash of the handler source files, so an uncommitted edit is never treated as unchanged.

## Command Centre boundary

It names the next eligible task (an owner investigation, or a trace for a finalized session that has none) and
lists blocked, failed and not-implemented tasks. It runs nothing. It cannot create or approve a strategy, relax
risk limits, reopen experiments, access validation or final data, enable orders, buy data, make paid model calls
or install integrations.

## Model assistance (DISABLED)

Two places where a model could later help are described with input, output, evaluation and cost boundary in
`desk.MODEL_ASSIST`. Both stay DISABLED until the owner authorizes a provider, model and budget. Model answers
are not independent market evidence; disagreement is shown, never averaged into a consensus.
