"""Read-only market monitoring (MONITORING data, not a research dataset).

  store.py    SQLite records: worker status, desired state, bars, events. No broker imports, so the
              dashboard server may read it.
  worker.py   the background worker process (python -m trading.monitor run). Only this process
              loads Alpaca credentials and talks to the read-only client.
  control.py  start/supervise the worker process from the dashboard without importing broker code.

Rules: GET-only Alpaca access through trading.alpaca_client; never fetch or keep bars dated inside
the reserved validation/final periods; monitoring data lives in data/monitoring/ and is never read
by research code; no trading signals or recommendations are produced.
"""
