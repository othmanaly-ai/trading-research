# Milestone 1: running the automatic session dry run

**What it is:**
- a program (`trading/operations/`) that follows one trading day by itself
- it checks health before the open
- it decides every minute whether an entry would be allowed: in DRY_RUN the answer is always
  **DENIED**, with the reasons
- it writes a report after the close

**What it is not:**
- **It contains no order code.** It cannot place, change or cancel orders.
- **No strategy is approved.** `config/approved_strategies.json` is empty.
- **It is not a background service.** You start it by hand each trading day (owner decision,
  2026-11-09). No scheduled task or startup entry exists.

**Rules for pass, fail, interruption and incomplete:** `docs/DRY_RUN_ACCEPTANCE.md`.

**Where the records are:**
- `%LOCALAPPDATA%\TradingProject\operations\` (outside OneDrive)
- `operations.sqlite`
- `reports\<date>.json`
- `KILL_SWITCH.json` (exists only while the kill switch is ON)

## Each trading day

1. **Before 09:25 ET**, start the city server, if it is not already running. It keeps the
   market-data monitor alive, which the dry run checks:
   - In the desktop app: the `demo-dashboard` launch configuration.
   - Or in a terminal: `.venv\Scripts\python -m trading.dashboard.server`.
   - In the city, Market monitor should show the worker RUNNING (or MARKET CLOSED before the
     open). If it shows STOPPED, press Start.
2. **Before 09:25 ET**, in a separate PowerShell window in the project folder, run:

   ```powershell
   .venv\Scripts\python -m trading.operations run
   ```

   Leave that window open until it prints the report: about 16:20 ET, or 13:20 ET on an early-close
   day. Then it exits by itself.
3. **Keep the computer awake and online.**
   - On battery, this PC sleeps after 10 minutes, which would interrupt the session.
   - Closing the desktop app stops the city server and with it the monitor.
4. **After it exits**, check the result with
   `.venv\Scripts\python -m trading.operations acceptance`, or open the city's **Operations** view.

## Other commands (none of them place orders)

| Command | What it does |
|---|---|
| `python -m trading.operations status` | today's phase, the latest run, the kill switch (no network) |
| `python -m trading.operations preflight` | runs the pre-open checks once now; read-only GETs to the broker clock and account |
| `python -m trading.operations report --date 2026-11-10` | recomputes and stores that session's classification |
| `python -m trading.operations acceptance` | the five-consecutive-PASS tracker |
| `python -m trading.operations kill-switch on --reason "..."` | blocks entries (in DRY_RUN they are blocked anyway; useful as a drill) |
| `python -m trading.operations kill-switch off --reason "..."` | owner only; a reason is required |

Prefix each with `.venv\Scripts\` when running from PowerShell.

**Stopping:**
- Ctrl+C in the runner window stops it cleanly. That session is then INTERRUPTED.
- Starting it again the same day continues. Minutes already decided are never duplicated, and
  minutes it was not running for stay missing.
- **Only one runner at a time:** a second one exits immediately.

## What it checks

| When | Checks |
|---|---|
| Start | order guard disabled and `TRADING_MODE=paper`; environment DRY_RUN; records outside OneDrive. **Any failure: the runner refuses (a FAIL).** |
| 08:45 and 09:25 ET | records writable, disk at least 1 GB free, approvals file readable, kill switch readable, monitor worker alive, credentials present (names only), broker clock skew 2 s or less, calendar agrees with the broker clock, paper account ACTIVE and not blocked |
| Every minute, 09:30-15:55 ET | entry permission with all reasons: environment, approvals (re-read each minute), phase, data freshness and suitability, risk state, kill switch, clock, records |
| Every 30 min | broker clock skew and calendar agreement |
| 15:55 ET | closing: confirms no exposure (DRY_RUN holds none) |
| 16:20 ET | after-close report and classification |

## Known limitations

- **Clock margin:**
  - On 2026-11-09 this PC's clock was about **1.1 s ahead** of the broker clock, inside the 2 s
    tolerance but close.
  - If Windows time drifts further, sessions will be INTERRUPTED (N4/N5).
  - Re-syncing Windows time is a system setting for you to change. The project does not change it.
- **The data dependency is the IEX monitor:**
  - Freshness is reported, but "suitable for execution" is never claimed.
  - The monitor runs only while the city server runs.
- **Manual start:** a day you do not start it counts as NOT RUN (INCOMPLETE), which resets the
  five-session count.
- **What a pass covers:** a PASS shows the machinery operated as specified. It is not evidence
  about any strategy.
