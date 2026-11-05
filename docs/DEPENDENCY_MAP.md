# Dependency-and-health map (2026-11-05)

**Where:** the city's **Dependencies** view (real records). The data comes from
`trading/dashboard/depmap.py` through `GET /api/depmap`.

**Read-only:** it starts nothing, restarts nothing and changes nothing. It reads existing stores only:
- the monitoring store
- the job store
- review readiness
- experiment STATUS files
- the history manifest summary
- Graphify's graph file

It reads no secrets and lists no files.

## What is backed by what

| Item | Source |
|---|---|
| **Components and declared connections** | Code and config: the `NODES` and `EDGES` lists in `depmap.py`, each with a file and symbol, plus `trading/jobs.py` `WORKERS[..].depends_on` |
| **Statuses** | Runtime records only: worker record, monitor events, spawns, `q_runs`, `q_health`, `q_reports`, the bars table, job store, reviewer readiness, `STATUS.json`, the history manifest. **With no record a status is UNKNOWN.** |
| **Recorded handoffs** | Runtime records with timestamps: last successful IEX poll, newest stored bar, last worker launch, last successful comparison run, last stored daily report, job-to-job consumption in the latest pipeline (including reused results), report written |
| **Proposed connections** | `trading/jobs.py` `UNIMPLEMENTED_ROLES` only (news analysis to analysis; monitoring store to live performance monitoring). Broker reconciliation is listed with no connection. |
| **Static code** | Graphify (`graphify-out/graph.json`): the number of static relations between the two files. Shown separately; never used for status. |

**Historical handoffs:** a handoff older than one hour is labelled historical. Only a job record in
`running` is ever shown as running.

**No execution path:** no order or trading execution system exists, so none is drawn.

## Statuses and reasoning

**Statuses:**

| Status | Meaning |
|---|---|
| OK | The record shows the component working |
| IDLE | Idle by design: market closed, paused or stopped by request |
| STALE | Market open, but no recent success |
| FAILED | An error or refusal is in the records |
| UNKNOWN | No record |
| DISABLED | The optional model review |
| CLOSED | Historical research records |
| NOT IMPLEMENTED | A role listed as unimplemented |

**Why blocked?:**
- It applies only when the component's own record is FAILED, STALE or UNKNOWN.
- It traces that component's evidence, then upstream components whose records are bad (up to
  depth 4).
- Missing evidence is stated as "UNKNOWN: no evidence recorded".

**Upstream issues:** a component whose own record is OK, but whose dependency has a problem. This is
not called blocked.

**Dependency impact:** downstream components of a bad component, each with its own record status. It
is labelled *not proof of failure*.

**Work mode:** continuous, manually started (predefined pipeline), cached or reused result,
disabled, external service, stored evidence, read on request, or not implemented.

**Next available action:** fixed advice text per component and status. It never performs anything.

## Interaction

- Only the selected component's connections are drawn: solid tube = recorded handoff, dashed =
  declared, dotted = proposed. "Show all connections" gives an overview.
- Labels are compact with no selection. With a selection, only the component and its direct
  neighbours are labelled.
- The Components and Connections tables carry the same information and are keyboard-accessible.
- A current (non-historical) recorded handoff into a component plays its arrival effect once per
  handoff id. Ids are stable for the same record, so polling and reconnects never repeat it.

## Tests (`tests/test_depmap.py`, synthetic fixtures only)

Covered:
- healthy dependencies
- upstream failure (refused access traced, impact listed)
- stale data
- market closed is idle, with historical handoffs
- missing evidence is UNKNOWN
- disabled optional review is not a blocker
- cached or reused results
- a failed step's impact is not proof of failure
- recovery keeps links unique and handoff ids stable
- no execution path; proposed edges carry no status
- static code is kept separate from status
- an OK component with a failed upstream is not called blocked
- `collect()` is read-only

**Endpoint test:** `tests/test_dashboard.py`.

## Verification

**Failure view:** the failure rendering was checked in the browser with a synthetic fixture fed
through a fetch override in one tab (screenshot `docs/city/depmap-why-blocked-SYNTHETIC-fixture.jpg`).
No failure was injected into the real monitor.

**Real records:** screenshot `docs/city/depmap-selected-model-review.jpg`.
