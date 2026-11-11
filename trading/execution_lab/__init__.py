"""LOCAL EXECUTION SIMULATION: an order-lifecycle rehearsal lab with a fake, in-memory broker.

Boundary (enforced by tests/test_execution_lab.py):
- No network, no broker client, no credentials: nothing here imports trading.alpaca_client, requests, urllib,
  http or socket, and nothing reads credential files. The fake broker is a plain in-memory object.
- Not operational: it is not used by trading.operations (the dry run), it is not an order integration and it
  validates no strategy. All instruments, prices and dates are SYNTHETIC.
- It reuses the approved risk definitions (trading.risk.OWNER_BASELINE_2026_11_03, size_position, RiskState) and
  the cost model (trading.costs.BASE) without changing them.
- Records are written only to an in-memory ledger or to a temporary file given by the caller (the restart
  scenario); never to the project's data stores.
"""
