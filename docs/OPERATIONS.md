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

## Each trading day: one start-up command (2026-11-09)

Before 09:25 ET, in PowerShell:

```powershell
Set-Location "C:\Users\othma\OneDrive\Documents\TradingProject"
.\.venv\Scripts\python.exe -m trading.startup
```

It prints each step as OK / WAIT / WARN / FAIL / SKIP and ends with **READY** (exit code 0) or
**NOT READY** (exit code 1), with the reasons.

1. **Environment:** the project's `.venv` interpreter, and order submission blocked.
2. **City server:** reused if it already answers on 127.0.0.1:8765. Otherwise it is started in its
   own window and awaited. Anything else on the port is a FAIL.
3. **Market monitor:** waits until readiness shows one worker with a fresh heartbeat, and prints
   every readiness check. A paused or stopped desired state is reported, never overridden.
4. **Dry-run runner:**
   - reused if healthy, and started in its own window if none is running
   - it is awaited until it reports "running", showing each start-up step
   - **a stalled runner is FAIL and is never killed or duplicated:** close its window (Ctrl+C) and
     run the command again

It never stops or restarts anything that is already healthy. Leave the windows it opens running, and
keep the computer on mains power and awake, until about 16:45 ET.

**After the session:** `.\.venv\Scripts\python.exe -m trading.operations acceptance`, or the city's
**Operations** and **Market monitor** views.

### When something looks wrong: where the evidence is

| Question | Where to look |
|---|---|
| Is the runner healthy, or stalled? | Market readiness, check "Dry-run runner (operations)": FAIL "STALLED" if the process exists but has not reported for over 60 s |
| At which start-up step did it stop? | `%LOCALAPPDATA%\TradingProject\operations\runner_startup.json`. Each step is written **before** it starts: 1/4 loading code, 2/4 lock, 3/4 records, 4/4 loop. |
| What did the runner print? | `runner.log` in the same folder (a copy of the window's output) |
| Where was it stuck? | `runner_faults.log`: Python stack traces, written automatically if start-up takes over 60 s or one loop step takes over 5 min |
| Did the city server stop cleanly? | the `server_runs` table and `server` events in the monitor database. A run with no `stopped_utc` ended without a clean stop (cause not recorded). |

## Start from a normal PowerShell window, not a Claude desktop terminal (2026-11-10)

Windows keeps a private copy of `%LOCALAPPDATA%` files for processes started inside a packaged app such as the
Claude desktop app. On 2026-11-08 an operations command run from a Claude terminal created such a copy of
`operations.sqlite`. From then on, every process inside the app (the city server, Claude Code) read that frozen copy.
Meanwhile the runner, started in a normal window, wrote the real file: 335 decisions on 11-09 and the 11-10 run
were recorded but invisible to the city.

- Every `python -m trading.operations` command now refuses (exit 3) when its view of the records is an app-private
  copy, or when its writes would land in one (`paths.virtualization_problem`). This covers the kill switch: one
  set from inside the app would never reach the runner.
- The readiness "Dry-run runner" check now needs recorded progress, not just a live process and a fresh status
  file. The run named by the status file must be in the records, with a heartbeat at most 3 minutes older than
  the status file, and after the close a stored report must exist. Otherwise it is FAIL ("alive but NO RECORDED
  PROGRESS").
- The city's operations view shows "records NOT VISIBLE" when the server itself runs inside the app.
- Start the city server and the runner the same way (`python -m trading.startup` in a normal PowerShell window),
  so they see the same files.
- The stale app copy is still at `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\TradingProject\operations\`.
  It holds only the two 11-08 preflight and no-session records. It was left in place pending an owner decision.

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
| 08:45 and 09:25 ET | records writable, disk at least 1 GB free, approvals file readable, kill switch readable, monitor worker alive, credentials present (names only), broker clock skew 2 s or less, calendar agrees with the broker clock, paper account ACTIVE and not blocked, no positions and no open orders by broker evidence |
| Every minute, 09:30-15:55 ET | entry permission with all reasons: environment, approvals (re-read each minute), phase, data freshness and suitability, risk state, kill switch, clock, records |
| Every 30 min | broker clock skew and calendar agreement |
| 15:55 ET | closing: broker evidence (read-only GETs) of no positions and no open orders; anything else is F9 or I6 (amendment 2026-11-10 in `docs/DRY_RUN_ACCEPTANCE.md`) |
| 16:20 ET | after-close report and classification |

## Persistent background operation: PROPOSED, not installed

**What it would solve:** both of today's outages (10:24 and 13:00 ET) were the city server process
ending while Windows kept running. The worker and its supervision depend on that one process staying
alive. The cause of the ending is not recorded (see PROGRESS.md, 2026-11-09).

**Option, if you approve it:** a Windows Task Scheduler task that starts the city server at log-on
and restarts it if it exits.
- **Trigger:** "At log on of othma".
- **Action:** `C:\Users\othma\OneDrive\Documents\TradingProject\.venv\Scripts\python.exe -m trading.dashboard.server`,
  "Start in" the project folder.
- **Settings:** "If the task fails, restart every 1 minute, up to 999 times". Do not "Stop the task if
  it runs longer than…". Run only when the user is logged on (so your own environment keys are
  used, and no password is stored).
- **The dry runner stays manual**, through `python -m trading.startup`.

| Benefit | Cost or risk |
|---|---|
| Survives app or window closures and restarts the server automatically | A process runs whenever you are logged on, including outside market hours (the worker makes no API calls while the market is closed) |
| Starts after a reboot (today's 15:04 ET crash and 17:34 ET reboot) | It does not help if Windows sleeps, crashes or loses power; nothing runs until log-on |
| | A hidden process is harder to notice and stop. Stop it through Task Scheduler, or Market monitor > Stop. |
| | Code changes need the task restarted to take effect |

**Not done:** no task is installed and no power setting is changed. Both need your approval.

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
