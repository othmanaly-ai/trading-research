# Automated second review (model-powered reviewer)

Status: **implemented and tested with mocked responses only. UNAVAILABLE**, waiting for the
owner's provider/model choice, budget authorization, and one approved verification call.

## What it is, and what it is not

The `model_review` step of the research-job pipeline (`trading/reviewer/`) sends a language model
a selected, sanitized evidence package from a closed experiment's saved artifacts. The model is
asked to:
- explain the failed gates
- list methodological limitations
- note discrepancies between artifacts

It is an **automated second review**, not proof of independent correctness. The deterministic
checks (`reconcile`, `rule_checks`) stay the authority for arithmetic and pass/fail:
- a review whose gate results differ from them is rejected
- the review cannot change anything they produced

### What the reviewer receives

The reviewer gets text only. It has no tools, so it cannot:
- run code or read files
- see credentials, fetch data, or touch held-out periods
- change rules, approve strategies, or place orders

The evidence package (`evidence.py`) is built from named fields of:
- `STATUS.json`
- `EXPERIMENT_LOCK.json`
- the saved development run report
- selected sections of `RESULTS_development.md`
- the deterministic check outputs

It never includes `data/`, market data, validation or final data, or account information.

### How text from the artifacts is handled

- secret-looking values and local paths are redacted
- long strings are truncated, and each truncation is recorded
- instruction-like text is **flagged and kept as data**; the system prompt says everything
  inside `<evidence>` is untrusted

### What makes a response valid

Every fact and deduction must cite an evidence item, and each citation is resolved against the
package. Findings are labelled:
- RECORDED FACT
- DEDUCTION
- SUGGESTION (speculative)

## Provider options

| Option | Status here | Billing |
|---|---|---|
| Anthropic API (first party), via the official `anthropic` Python SDK | **Implemented**, not verified | Claude Console account with prepaid API credits, billed per token |
| Claude on Amazon Bedrock / Google Vertex AI / Microsoft Foundry | Not implemented | Cloud account, partner pricing |
| Other vendors | Not implemented | Separate accounts and terms |

A Claude.ai or Claude Code subscription does **not** include API usage. API calls need a separate
Console account with credits, and a key created there.

Models with price entries (USD per 1M tokens, input / output; Anthropic list prices as cached
2026-10-06, re-check before authorizing):

| Model | Input | Output | Worst case per call at the proposed limits (30k in / 8k out) |
|---|---|---|---|
| `claude-haiku-5-5` | $0.10 | $0.50 | $0.007 |
| `claude-sonnet-5-5` | $2.00 | $10.00 | $0.14 |
| `claude-opus-5-5` | $4.00 | $20.00 | $0.28 |
| `claude-fable-5-1` | $10.00 | $50.00 | $0.70 (exceeds the proposed $0.50 per-run cap) |

The real evidence packages measure about 18k characters, roughly 5–7k input tokens. Output
tokens include the model's thinking, and `max_output_tokens` caps them.

## Proposed limits (not yet authorized)

| Limit | Proposed | Code ceiling |
|---|---|---|
| max_input_tokens | 30,000 | 60,000 |
| max_output_tokens | 8,000 | 16,000 |
| max_calls_per_run (billable calls per pipeline) | 1 | 2 |
| max_attempts_per_call (retries only for unbilled 429/529) | 3 | 3 |
| max_usd_per_run | $0.50 | $2.00 |
| max_usd_per_month | $5.00 | $25.00 |

Completed reviews are cached by evidence fingerprint, prompt version, provider and model. With
both closed experiments reviewed once, further runs cost $0 until the evidence or prompt changes.

## How cost enforcement works

### Before each call
1. The worst case is reserved: `max_input_tokens × input price + max_output_tokens × output price`.
2. In one SQLite write transaction (`BEGIN IMMEDIATE`), the reservation is checked against the
   per-run and monthly caps and recorded. Concurrent processes therefore cannot both pass.

### After the call
- **Completed or billed-but-unusable responses:** the reservation is replaced by provider-reported
  token usage × the local price table.
- **Rejected requests (4xx), rate limits (429) and overload (529):** charged $0, since the
  provider does not bill error responses.
- **Uncertain outcomes (timeout, dropped connection, other 5xx, or a process restart mid-call):**
  the full reservation stays charged and the call is **not repeated**. A new attempt needs
  `python -m trading.reviewer acknowledge <review_id>`.
- **Billed-but-unusable responses (malformed JSON, failed validation, refusal, truncation):** also
  never repeated automatically.

### Retries
Only unbilled 429/529 responses are retried, at most 3 attempts in total, after waits of 2 s and
8 s (or the provider's retry-after, capped at 30 s). The SDK's own retries are disabled.

### Limitations
- The price table is local and can go stale. The provider invoice is the truth.
- The ledger only sees calls made by this code. Set a spend limit in the Claude Console as well.
- The input-token estimate is conservative (about 2 characters per token). The reservation uses
  the authorized maximum, not the estimate.

## Records

Each attempt is stored in `data/reviews/reviews.sqlite` (git-ignored) with:
- provider, model, prompt version and evidence fingerprint
- the full sanitized package
- timestamps, attempts, HTTP status, request id and stop reason
- token usage, cost, cost basis, reserved and charged amounts
- errors, validation errors, and the raw response text (capped)

## To enable it (owner steps; nothing here is done automatically)

1. Choose a provider and model (only Anthropic is implemented) and a budget.
2. Create a Claude Console API key and set `ANTHROPIC_API_KEY` in your own environment. Never
   paste it into chat.
3. Install the SDK: `.venv\Scripts\python -m pip install anthropic`, then update
   `requirements.lock`.
4. Write `research/MODEL_REVIEW_AUTHORIZATION.json` with your values. Template:

```json
{"provider": "anthropic", "model": "<your choice>", "effort": "medium",
 "max_input_tokens": 30000, "max_output_tokens": 8000, "max_calls_per_run": 1,
 "max_attempts_per_call": 3, "max_usd_per_run": 0.50, "max_usd_per_month": 5.00,
 "authorized_by": "<your name>", "authorized_utc": "<UTC timestamp>", "expires_utc": "<optional>"}
```

5. Check readiness without spending: `python -m trading.reviewer status`, then
   `python -m trading.reviewer preview --experiment 002_opening_range_breakout`.
6. The first paid call, which verifies the integration:
   `python -m trading.reviewer verify --experiment 002_opening_range_breakout --i-authorize-one-paid-call`.
   Only a real, validated, non-mock response marks the integration verified. Until then the job
   step stays UNAVAILABLE.
