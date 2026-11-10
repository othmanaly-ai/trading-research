# Read-only market monitoring

Status (2026-11-04):
- implemented, tested with labelled synthetic fixtures
- verified against real Alpaca data in the city

It is **monitoring only**: it creates no orders, no signals and no recommendations, and does not
use the two closed strategies.

## What runs where

| Part | Process | Credentials |
|---|---|---|
| Worker (`python -m trading.monitor run`) | separate background process | loads Alpaca paper keys itself (environment, or `.env`) |
| City server (`trading.dashboard.server`) | dashboard | never loads credentials or broker code; reads `data/monitoring/monitor.sqlite` |
| Supervisor (thread in the city server) | dashboard | launches the worker process only; never reads keys |

Data goes to `data/monitoring/monitor.sqlite`, which is git-ignored and separate from
`data/history/` and `data/alpaca/`. No research code reads it (a test enforces this).

## Data permissions measured on 2026-11-04

- **IEX feed:** real-time 1-minute bars accepted.
  - IEX is a single exchange, so volume is partial.
  - A minute with no IEX trades has no bar, so a gap is not necessarily an outage.
- **SIP feed:** recent data refused (HTTP 403, "subscription does not permit querying recent SIP
  data"). SIP is only available 15 minutes delayed. The worker never switches feeds on its own.
- **Polling:** one multi-symbol request per 60 s. The free plan allows 200 requests per minute.

## Behaviour

- **Exchange calendar (XNYS):**
  - polls only during the regular session, including early closes
  - makes one catch-up poll after the close
  - makes no API calls on weekends, holidays or outside hours
- **What is requested:**
  - the minute still in progress is never requested
  - each poll asks only for minutes after the last stored bar
- **Duplicates:** bars are keyed by (symbol, feed, bar start); repeats are ignored and counted.
- **Freshness, computed from source timestamps:**

| Label | Meaning |
|---|---|
| FRESH | last bar ended at most 3 minutes ago, beyond the feed's expected delay |
| STALE | longer than that (shown with the IEX note) |
| NO DATA YET | the session is open but nothing stored for it yet |
| MARKET CLOSED | outside the regular session |
| PAUSED | the worker is paused |
| STOPPED | the worker was stopped, or never started |
| DISCONNECTED | the worker is not responding (no heartbeat for 20 s), or is in an error or backoff state |

- **Failures:**

| Failure | Wait before retry |
|---|---|
| Connection errors, 5xx, 429 | 5, 10, 20, 40, 80, 160, then 300 s (cap) |
| 401/403 (access refused) | 600 s |
| Missing keys | 300 s |

  Every failure is recorded as an event, and the session is re-created after a dropped connection.

- **Reserved periods:**
  - the worker refuses to request any date on or before 2026-10-30 (the end of the final period)
  - it discards any such bar a response contains
  - current monitoring (from 2026-11-02) does not overlap them

## Controls

| Control | Effect |
|---|---|
| Start | desired state becomes running; launches one worker if none is alive |
| Pause | the worker stays alive and makes no API calls |
| Stop | the worker exits within about a second; nothing relaunches it until Start |

The same controls are available from the command line: `python -m trading.monitor start|pause|stop|status`.

- **One worker at a time:** an OS file lock prevents a second worker, which exits immediately and
  records why.
- **Restart recovery:** the supervisor checks every 15 s and at dashboard start-up. If the desired
  state is running and no worker is alive, it launches one: at most one launch per 20 s and 6 per
  hour, each recorded. The new worker continues after the last stored bar.

## What runs automatically, and what doesn't

- **While the city server runs with desired state "running":** the worker polls every trading
  minute, and is relaunched after a crash or a dashboard restart.
- **Not automatic:**
  - nothing starts when Windows starts; the city server must be running for supervision
  - stopping the city server through the desktop app also stops its worker; it resumes when the
    server starts again

### Startup and recovery (what happens when…)

There is no always-on service. Monitoring runs only while this computer is on, awake and online,
and the city server is running.

| Event | What happens | What you do |
|---|---|---|
| You start the server and one is already running | The new start finds the existing server on 127.0.0.1:8765 (it asks `/api/meta`), prints its address and exits **without starting a second server**. If another program holds the port, it says so and exits. | Open http://127.0.0.1:8765 |
| You press Start and a worker is alive | Nothing new is launched ("worker already running"). The OS lock lets only one worker poll. | Nothing |
| Browser tab closed | Nothing changes: the server and worker keep running. The browser only displays records. | Reopen the address any time |
| Desktop app closed, or server stopped | The server stops, and with it the supervision. The worker stops too when the app stops it. Live minutes are missed, and are never recovered later. | Start the server again; the supervisor relaunches the worker if the desired state is "running" |
| Computer sleeps | All processes pause. No data is collected, and the missed live minutes are lost. On wake, heartbeats resume; a wake mid-session shows a stale-heartbeat or stopped incident until the next poll. | Keep the PC on mains power and awake during the session (it sleeps after 10 min on battery) |
| Computer restarts or Windows updates | Nothing starts by itself (no startup task). | Start the server again before the open |
| Worker crashes | While the server runs, the supervisor relaunches it within about 15-20 s (at most 6 per hour). The incident is recorded, then resolved as "service recovered". | Check Market readiness |

Unfinished sessions within the last 5 trading sessions are re-compared and finalized when the worker
runs again. Live capture gaps stay gaps.

### Market readiness panel (`trading/monitor/readiness.py`, `GET /api/monitor/readiness`)

The top of the city's **Market monitor** view. Each check is computed from real records at request
time, and then every 60 s by the server's supervisor. The latest result per check is stored in the
`readiness` table, with when it was checked and since when its status holds.

**Statuses:**
- PASS, WARNING, FAIL or UNKNOWN.
- **Missing evidence is UNKNOWN, never PASS.**
- A closed market is expected, not a failure.

| Check | PASS when | Otherwise |
|---|---|---|
| Server responding | the server answers with its pid and start time | the browser shows FAIL if it cannot reach the server |
| Exactly one intended worker | one worker process tree, matching the recorded pid. A venv's `python.exe` launcher plus its child interpreter count as one. | FAIL for two or more workers, or for none while desired is running; WARNING when stopped or paused by request; UNKNOWN if the process list is unavailable |
| Worker heartbeat | at most 20 s old | FAIL if stale; UNKNOWN if never recorded |
| Desired vs actual | desired running, actual running or market closed | WARNING when paused or stopped by request, or disconnected; FAIL on a mismatch |
| Exchange calendar | the next session is known, and the latest broker clock cross-check (recorded by the dry-run preflight) agreed within 7 days | WARNING with no recent cross-check; FAIL if it disagreed |
| Latest data | open market: all symbols FRESH. Closed market: the newest bar comes from the last session. | WARNING or FAIL accordingly; UNKNOWN with no successful request |
| Backoff and refusals | no backoff, no refusal, no unresolved incident | FAIL on an access refusal; WARNING on backoff, failures or an open incident |
| Database | a write and read-back probe succeeds | FAIL (then the dependent checks are UNKNOWN) |
| Disk | at least 1 GB free (the same floor as the dry run) | FAIL |
| Unfinished sessions | none pending | WARNING while an after-close recheck is pending |
| Code version | the worker, the server and the repository are the same commit, with no uncommitted changes | WARNING otherwise (a running process keeps old code until restarted); UNKNOWN if not available |

**Incidents (`incidents` table):**
- **Kinds:** worker stopped unexpectedly, heartbeat stale, provider access refused, storage
  failure.
- **One open incident per kind:** repeats only update "last seen" and the count.
- **Acknowledge** marks it seen. It stays unresolved until the condition clears; it is then
  **resolved**, with "service recovered" in the event log.
- **Database outages:** a storage failure seen while the database is unwritable is kept in memory
  and written once the database works again.
- Each incident shows a recovery explanation. No secrets are shown.

**Dry-run runner check** (added 2026-11-09):
- **FAIL during the session window** when no runner process exists, or when a runner process exists
  but has not refreshed `runner_status.json` for over 60 s (**STALLED**, with its last start-up
  step).
- **WARNING** while it is still starting (up to 120 s), or before 08:45 ET.
- **PASS** when it is running, on non-session days, and after its report is written.

**Corrections to the evidence reports (2026-11-09)** were found and fixed:
- **Request failures** are now counted only from explicit request outcomes: live-poll failure
  events of kind `error` or `disconnected`, and comparison runs with status `access_failure` or
  `error`. Every other error-level event (`incident`, `supervisor`, `crash`, `quality-*`) is
  reported as an "other error", by kind.
- **Finalized wording:** a finalized report always says "compared through the close; post-close
  re-observation done". `finalize()` had built the report before updating that description.
- **Stored reports are corrected amend-only**, with
  `python -m trading.monitor correct-reports --reason "..." [--apply]` (a preview without
  `--apply`):
  - each correction is a new version, derived only from the stored report
  - the reason is in the new report's `correction` block and in `q_report_corrections`
  - earlier versions are untouched
  - applied 2026-11-09 to Nov 5, 6 and 9 (version 2 each)

**City-server lifecycle** (`server_runs`): the server records its start, a "last alive" time every
15 s, and a clean stop. A run without a stop time ended without a clean stop, and its cause is not
recorded.

**Report completion** (formerly labelled "session reliability"):
- **The criterion:** the existing written one, from the checklist below, unchanged. Five
  consecutive scheduled sessions, each FINALIZED or INCOMPLETE with a stated reason.
- **What it counts:** completed evidence reports, not live-capture reliability. A prospective
  reliability gate is proposed in `docs/RELIABILITY_GATE_PROPOSAL.md`; it is not active.
- A scheduled session with no monitoring is **not monitored**, does not qualify, and breaks the
  streak.
- **Gap:** this criterion has no capture-quality threshold, so a finalized session with large live
  gaps still qualifies. No such threshold is applied until the owner sets one.

## Data quality: delayed SIP vs IEX (`trading/monitor/quality.py`)

Runs inside the worker process and reuses its read-only client.

**Access check (2026-11-04 16:51 UTC):** delayed SIP was accepted when the newest requested minute
ended 20 minutes earlier (HTTP 200, 5 of 5 SPY bars).

**Delay rule:** a minute is compared only once its end is at least **20 minutes old**: the plan's
15-minute SIP delay plus a **5-minute safety margin**.

**Requests:**
- every 5 minutes, two GETs (SIP, then IEX) for the window since the last comparison
- each window is at most 120 minutes, so a backlog is worked off chunk by chunk
- one end-of-day re-observation of the whole session, 45 minutes after the close
- failures back off 60 s, then 120, 300 and 600 s; access refusals (401/403) wait 1800 s
- SIP is never replaced by another feed

**Evidence:**
- every observation is kept with `retrieved_utc` and `provider_available_utc`; for SIP that is bar
  end + 15 min, the earliest moment this plan allows the bar to be known
- a changed bar becomes a new **revision**, and earlier revisions are never overwritten
- comparisons name the exact revisions they used
- identical repeats are counted as duplicates
- the live IEX bars are never modified

**Categories** (deterministic rules, no invented tolerances):

| Category | Meaning |
|---|---|
| consistent subset | IEX inside the SIP range and volume |
| expected coverage difference | SIP bar, no IEX bar |
| both absent | no bar in either feed |
| unresolved anomaly | SIP missing while IEX present, or IEX outside the SIP range or volume; plausibly trade-condition filtering differences, not proven defects |
| structural defect | a bar violates its own OHLC, volume or timestamp invariants, or conflicting duplicates arrive in one response |

Access failures are recorded per run; their minutes stay pending.

**No look-ahead:** results are labelled with when each SIP bar became available. They never change
freshness, live bars or any research data, and nothing consumes them for decisions.

**Scope limits:**
- only the current session is compared; earlier days are not backfilled
- the end-of-day re-observation needs the worker running after the close
- a day restarted after midnight ET is not finished

**First measurements (2026-11-04, 09:30–11:38 ET, 128 minutes per symbol):**

| Symbol | IEX share of consolidated volume | Median close difference | Largest close difference |
|---|---|---|---|
| SPY | 4.1% | 0.39 bps | 3.3 bps ($0.25) |
| QQQ | 1.5% | 0.83 bps | 11.2 bps ($0.78) |
| IWM | 3.7% | 0.88 bps | 5.2 bps ($0.15) |

- Every compared minute was a consistent subset. There were no missing minutes in either feed, no
  anomalies, defects or corrections, and no zero-volume minutes.
- These are one morning's observations. They are not a suitability verdict, and not evidence of
  any strategy's profitability.

## Multi-session recovery and daily evidence reports

### Session states

| State | Meaning |
|---|---|
| IN PROGRESS | the session is open and being monitored |
| PROVISIONAL | the session has closed; comparison or post-close re-observation still pending |
| FINALIZED | compared through the close and re-observed after the close; report stored |
| INCOMPLETE | cannot be completed; report stored with the reason and the unresolved intervals |

A session can become INCOMPLETE in three ways:
- it is beyond the 5-session lookback
- historical access was refused 3 times
- it is not a comparable session

### Recovery

When the worker starts, every unfinished monitored session in the last 5 opened trading sessions is
resumed, oldest first, with the current session first. "Monitored" means the live worker polled it.
- **Calendar:** weekends, holidays and early closes come from the exchange calendar.
- **Midnight:** sessions are tracked by date, so neither midnight UTC nor midnight ET abandons one.
- **Bounds:**
  - 120-minute request windows, with a 5 s pause between backlog chunks
  - at most 120 comparison requests per rolling hour
  - nothing on or before 2026-10-30 (reserved)
- **What can't be recovered:** live capture. A later re-fetch is a different observation and is
  never written into the live record.

### Finalization

Finalization is idempotent. The report's evidence is hashed:
- repeating finalization with unchanged evidence stores nothing
- changed evidence becomes a new version that amends the old one, and old versions are kept

### Daily report sections

1. **Live capture:** minutes received; normal arrivals vs catch-up arrivals (bar end to receipt above
   180 s); stale intervals with worker-alive share; minutes missed while SIP had a bar.
2. **Later IEX revisions:** the provider's re-fetch compared with what was received live.
3. **Delayed SIP comparison:**
   - categories, labelled without implying identical prices or suitability
   - close differences vs re-fetched IEX and vs live IEX
   - high/low differences and volume share
   - "eligible" (bar end + 15 min) vs "received", split into normal and catch-up
4. **Operations:**
   - worker runs, with process id and code version
   - downtime intervals, labelled planned (stopped by request) or unplanned (no clean stop)
   - unrecorded intervals (before worker-run recording existed)
   - restarts, request failures, access refusals, comparison runs by kind
5. **Unresolved:** minutes not compared, post-close re-observation not done, failed runs,
   unrecoverable live gaps.
6. **Provenance:** endpoint, feeds, adjustment, rules, thresholds, code versions.

## Operating instructions

The commands are the same in PowerShell; use `.venv\Scripts\python` instead of `.venv/Scripts/python`.

1. Start the city server. The desktop app's launch configuration does this, or run:
   `.venv/Scripts/python -m trading.dashboard.server` (it binds to 127.0.0.1:8765 only).
2. Open http://127.0.0.1:8765, then **Market monitor**, then **Start**. The worker runs while the
   server runs.
3. Keep the computer awake and the server running through the session. Ideally keep it running until
   about 45 minutes after the close, so the post-close re-observation and finalization happen the
   same day. If it was off, starting the server the next day recovers the unfinished session, as
   long as it is within the last 5 sessions.
4. **Stop** halts the worker. Nothing restarts it until Start.
5. Command-line equivalents: `.venv/Scripts/python -m trading.monitor status|start|pause|stop`.
6. The supervisor launches at most 6 workers per hour. If you restart the server many times in an
   hour, the worker resumes automatically when the oldest launch is an hour old.

There is no Windows startup task. Monitoring is **not** a 24/7 service: it runs only while this
computer is on and the city server is running.

## Checklist for observing several consecutive sessions

Each trading day:
- [ ] Before 09:30 ET, the server is running and the city shows Worker health: RUNNING (or MARKET
      CLOSED before the open).
- [ ] During the session, all symbols show FRESH most of the time. Note any STALE or
      DISCONNECTED periods.
- [ ] Mid-session, Session history shows the day IN PROGRESS, with "Compared with SIP" growing about
      20 minutes behind the clock.
- [ ] After the close, keep the server running about 45 minutes. The day should become FINALIZED
      with report version 1.
- [ ] The next morning, check the previous session is FINALIZED. If it is PROVISIONAL, confirm it
      finalizes shortly after the worker starts.
- [ ] In each report, record: received normal vs catch-up, downtime (unplanned), request failures
      and access refusals, live vs re-fetch differences, SIP revisions, and unresolved items.
- [ ] Over a weekend or holiday, the next session's start should recover the last session.
- [ ] Before drawing conclusions, collect at least 5 consecutive sessions, each FINALIZED or
      INCOMPLETE with a stated reason.

## Limitations

- **Live capture cannot be recovered.** Minutes the live monitor missed stay missing in section 1.
- **Run history:** worker-run recording began 2026-11-04 17:16 UTC; earlier intervals that day are
  "unrecorded".
- **Lookback:** recovery covers the last 5 opened sessions; anything older is reported INCOMPLETE.
- **Downtime labels:** "planned" means a recorded stop request. A server stopped from the desktop
  app, a computer shutdown or a crash all appear as unplanned.
- **Latency:** catch-up latency (a backlog fetched after a gap) is reported separately from normal
  latency. Normal live latency is bounded below by the 60 s poll.
- **No suitability claims:** the reports state what was observed. They do not certify either feed
  for trading or show that any strategy would be profitable.
