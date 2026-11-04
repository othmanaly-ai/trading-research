"""Model-powered research reviewer: an AUTOMATED SECOND REVIEW of saved experiment artifacts.

It is not proof of independent correctness. Deterministic checks (trading/jobs.py reconcile and
rule_checks) remain the authority for arithmetic and pass/fail rules; a review that contradicts
them is rejected. The reviewer only receives a selected, sanitized evidence package as text. It
has no tools, so it cannot run code, read files, see credentials, fetch data, change rules,
approve strategies or place orders.

Modules:
  evidence.py   deliberate selection + sanitization of saved artifacts into a package
  prompt.py     prompt version, system prompt, output schema
  validate.py   schema, citation and deterministic-authority checks on the model's answer
  budget.py     owner authorization, price table, spend ledger (SQLite)
  providers.py  provider interface; Anthropic implementation (SDK imported lazily)
  review.py     orchestration: gates, cache, reservation, bounded retry, records
"""
