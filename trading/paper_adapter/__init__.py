"""PROPOSED Alpaca paper-order adapter: OFFLINE ONLY.

- It implements the execution core's broker port (submit, poll, lookup, request_cancel, positions, open_orders,
  account) by translating to Alpaca's documented paper Trading API request formats.
- It talks only to an injected transport. **No network transport exists in this repository**: the only transport is
  `FixtureTransport`, which replays recorded-style JSON fixtures written from the official documentation. A real
  transport is a later, separately authorized step.
- Every write (order submission, cancellation) calls `trading.safety.require_order_submission_allowed()` first; with
  the default environment that refuses, and the adapter records a LOCAL refusal without touching the transport.
- It is not imported by the dashboard, the dry run (trading.operations) or the execution lab; tests enforce this.
- Fixtures cannot prove real broker behaviour. Undocumented behaviour is marked UNVERIFIED in alpaca_orders.py.
"""
