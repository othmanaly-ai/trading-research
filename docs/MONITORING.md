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
