# Operational incidents (evidence only; causes stated only when records support them)

## 2026-11-10 ~21:49 ET: production city server (port 8765) stopped without a clean stop. CAUSE UNKNOWN

**Raw evidence (local, git-ignored):** `data/incidents/2026-11-10_production_server_stop.json`, a read-only copy of
the monitoring-store rows taken 2026-11-10 ~22:3x ET. The originals are unchanged.

**What the records show:**
- **Server run #6:** pid 29208, port 8765, started 21:28:28 ET, code `1ed518e+dirty`.
  - Last "alive" mark 21:49:30 ET; `stopped_utc` empty. No clean stop was recorded: a clean stop (Ctrl+C or a normal
    exit) writes a stop time.
- **Last checks:** the server's last readiness evaluation was at 21:48:43 ET, with every check PASS at that time.
- **Launch:** its parent was a Python launcher (pid 20656) whose own parent had already exited. That pattern is
  **consistent with** a start by `python -m trading.startup` in its own console window; it was not recorded as
  such. Neither process existed afterwards.
- **Monitoring worker:** pid 25856, started 21:28 ET, kept running with fresh heartbeats, unsupervised. Desired state
  stays "running".
- **No events:** the monitoring store has no event between 21:40 and 22:10 ET (no crash, refusal or supervisor
  error).
- **Windows logs, 21:35-22:05 ET:**
  - no shutdown, sleep, power, crash, hang, Windows Error Reporting or resource-exhaustion event
  - one unrelated DistributedCOM permission warning at 22:04:40

**Activity on this computer around the stop (from this session's own record):**
- **21:40:26:** the read-only preview on port 8770 was stopped and restarted (a different process and port).
- **21:43:26 to about 21:54:30:** the full offline test suite ran (562 tests, about 11 minutes). It includes:
  - fresh-process crash drills (subprocesses that exit with `os._exit`)
  - test servers on random ports
  - SQLite work in temporary folders
- **About 21:50-21:52:** isolation checks imported `trading.dashboard.server` in fresh processes. Importing does not
  start a server.

**Not established:**
- **Ruled out by direct evidence:** none of the tests addresses port 8765 or the production processes, or stops
  processes by name. No test or check here sent anything to 8765.
- **Not excluded, but no record supports it:** indirect effects (CPU or memory pressure, file or database contention,
  console or process-group signals), or a window closed by hand.
- **Cause: UNKNOWN.** The server prints errors only to its own console window, which no longer exists, so its last
  output is lost.

**Gap this exposes (no change made):** the server records start, alive and clean stop, but not its console output.
An abnormal end therefore leaves no message. A future fix would be to also write the server's output to a log file
(a proposal, not done).

**Recovery:** see "Recovering the production city server" in `docs/OPERATIONS.md`.
