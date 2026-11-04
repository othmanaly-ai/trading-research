"""Orchestration of one automated second review.

Order of checks (every blocker is reported, not just the first):
  evidence package builds and fits -> owner authorization valid -> provider usable (SDK + key
  presence) -> real integration verified (unless this IS the verification call) -> no
  unacknowledged uncertain/failed billed attempt for the same cache key -> estimated input within
  max_input_tokens -> worst case fits the run and monthly budgets (reserved atomically).
A completed review with the same cache key (evidence fingerprint + prompt version + provider +
model) is reused at no cost.

Retry rules: only "not_processed" answers (429/529, not billed) are retried, at most
max_attempts_per_call attempts in total with 2 s / 8 s waits (or the provider's retry-after, capped
at 30 s). Rejected requests are not retried. Uncertain outcomes (timeouts, dropped connections,
other 5xx) are recorded with the full reservation charged and are never repeated automatically.
"""

import hashlib
import json
import math
import time
import uuid
from pathlib import Path

from trading import jobs
from trading.reviewer import budget, evidence, prompt, providers, validate

TIMEOUT_S = 180.0
RETRY_DELAYS = (2.0, 8.0)
MAX_RETRY_AFTER = 30.0
SLEEP = time.sleep                  # replaced in tests
COST_BASIS = "measured: provider-reported token usage x local price table (estimate; invoice is authoritative)"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_key(provider: str, model: str, fingerprint: str) -> str:
    schema = json.dumps(prompt.OUTPUT_SCHEMA, sort_keys=True)
    return _sha(json.dumps([provider, model, prompt.PROMPT_VERSION, _sha(prompt.SYSTEM + schema), fingerprint]))


def estimate_input_tokens(system: str, user: str) -> int:
    """Conservative: about 2 characters per token (real JSON-heavy text is usually 3-4)."""
    return math.ceil((len(system) + len(user) + len(json.dumps(prompt.OUTPUT_SCHEMA))) / 2)


def readiness(env: dict, store: budget.ReviewStore, auth_path: Path | None = None) -> dict:
    """What stands between now and a real review. Reads presence only; never prints secrets."""
    auth, problems = budget.load_authorization(auth_path)
    model = auth["model"] if auth else None
    prov = providers.AnthropicProvider(model or "unset", env)
    checks = [
        {"check": "reviewer implementation (evidence, prompt, validation, budget, cache)", "ok": True,
         "detail": f"present; prompt {prompt.PROMPT_VERSION}"},
        {"check": "owner authorization (provider, model, budget)", "ok": auth is not None,
         "detail": "valid" if auth else "; ".join(problems)},
        {"check": "provider SDK installed", "ok": providers.sdk_installed(),
         "detail": "installed" if providers.sdk_installed() else "not installed"},
        {"check": "API key present in environment", "ok": bool(env.get("ANTHROPIC_API_KEY")),
         "detail": "present (value not read here)" if env.get("ANTHROPIC_API_KEY") else "ANTHROPIC_API_KEY not set"},
    ]
    ver = store.verified("anthropic", model, prompt.PROMPT_VERSION) if model else None
    checks.append({"check": "real integration verified by one owner-approved paid call", "ok": ver is not None,
                   "detail": f"verified {ver['verified_utc']} (review {ver['review_id']})" if ver
                   else "not verified; model review stays UNAVAILABLE"})
    del prov
    return {"available": all(c["ok"] for c in checks), "checks": checks, "authorization": auth,
            "month_spent_usd": round(store.month_spent(), 6), "prices_per_million": budget.PRICES,
            "price_source": budget.PRICE_SOURCE, "proposed_limits": budget.PROPOSED,
            "hard_limits": budget.HARD_LIMITS, "prompt_version": prompt.PROMPT_VERSION}


def gate_fingerprint(env: dict, store: budget.ReviewStore, auth_path: Path | None = None) -> str:
    """Changes whenever a gate could change (used in the job input key), without exposing secrets."""
    path = auth_path or budget.AUTH_PATH
    auth_sha = _sha(path.read_text(encoding="utf-8")) if path.is_file() else None
    r = readiness(env, store, auth_path)
    return _sha(json.dumps([auth_sha, [c["ok"] for c in r["checks"]], prompt.PROMPT_VERSION]))


def _blocked(reasons: list[str], **extra) -> dict:
    return {"status": "blocked", "reasons": reasons, "review": None, **extra}


def run_review(experiment: str, research_dir: Path, env: dict, store: budget.ReviewStore, *, run_ref: str,
               provider: providers.Provider | None = None, auth: dict | None = None,
               auth_path: Path | None = None, verification_call: bool = False) -> dict:
    try:
        package = evidence.build_package(experiment, research_dir)
    except evidence.EvidenceTooLarge as exc:
        return _blocked([f"oversized input: {exc}"])
    except evidence.EvidenceError as exc:
        return {"status": "failed", "error": f"evidence package could not be built: {exc}", "review": None}

    reasons = []
    if auth is None:
        auth, problems = budget.load_authorization(auth_path)
        reasons += problems
    if auth is None:
        reasons += providers.AnthropicProvider("unset", env).unavailable_reasons()
        reasons.append("real integration not verified")
        return _blocked(reasons, evidence_fingerprint=package["fingerprint"])

    provider = provider or providers.make_provider(auth, env)
    key = cache_key(provider.name, provider.model, package["fingerprint"])
    hit = store.cached(key)
    if hit:
        return {"status": "completed", "cached": True, "review_id": hit["id"], "review": hit["review"],
                "cost_usd": 0.0, "evidence_fingerprint": package["fingerprint"], "model": hit["model"],
                "prompt_version": hit["prompt_version"], "mock": hit["mock"],
                "note": f"reused completed review {hit['id']} (same evidence, prompt and model); no new call"}

    reasons += provider.unavailable_reasons()
    if not verification_call and not provider.mock and not store.verified(provider.name, provider.model,
                                                                          prompt.PROMPT_VERSION):
        reasons.append("real integration not verified: model review stays UNAVAILABLE until one owner-approved "
                       "verification call succeeds")
    prior = store.unresolved(key)
    if prior:
        reasons.append(f"previous attempt {prior['id']} ended {prior['status'].upper()} (${prior['charged_usd']:.4f} "
                       "charged); it is not repeated automatically. Acknowledge it first: "
                       f"python -m trading.reviewer acknowledge {prior['id']}")
    user = prompt.render_user_message(package)
    est = estimate_input_tokens(prompt.SYSTEM, user)
    if est > auth["max_input_tokens"]:
        reasons.append(f"oversized input: about {est} tokens estimated > max_input_tokens {auth['max_input_tokens']}")
    run_rows = store.db.execute("SELECT COUNT(*), COALESCE(SUM(charged_usd),0) FROM reviews WHERE run_ref=? "
                                "AND charged_usd > 0", (run_ref,)).fetchone()
    if run_rows[0] >= auth["max_calls_per_run"]:
        reasons.append(f"call budget: {run_rows[0]} billable call(s) already made in this run "
                       f"(max_calls_per_run {auth['max_calls_per_run']})")
    if reasons:
        return _blocked(reasons, evidence_fingerprint=package["fingerprint"], cache_key=key)

    reservation = budget.worst_case_usd(auth)
    review_id = f"rv-{experiment[:3]}-{budget.now()[:19].replace(':', '').replace('-', '')}-{key[:8]}-{uuid.uuid4().hex[:6]}"
    fields = {"cache_key": key, "experiment": experiment, "provider": provider.name, "model": provider.model,
              "prompt_version": prompt.PROMPT_VERSION, "evidence_fingerprint": package["fingerprint"],
              "package_json": json.dumps(package, default=str), "run_ref": run_ref, "created_utc": budget.now(),
              "mock": int(provider.mock)}
    try:
        store.reserve(review_id, fields, reservation, auth, run_rows[1])
    except budget.BudgetDenied as exc:
        return _blocked([f"budget denied: {exc}"], evidence_fingerprint=package["fingerprint"], cache_key=key)

    attempts = []
    for n in range(1, int(auth["max_attempts_per_call"]) + 1):
        started = budget.now()
        try:
            res = provider.complete(prompt.SYSTEM, user, prompt.OUTPUT_SCHEMA, int(auth["max_output_tokens"]),
                                    auth["effort"], TIMEOUT_S)
        except providers.ProviderError as exc:
            attempts.append({"attempt": n, "started_utc": started, "outcome": exc.kind, "http_status": exc.http_status,
                             "error": str(exc)})
            if exc.kind == "not_processed" and n < auth["max_attempts_per_call"]:
                SLEEP(min(exc.retry_after or RETRY_DELAYS[min(n - 1, len(RETRY_DELAYS) - 1)], MAX_RETRY_AFTER))
                continue
            if exc.kind == "uncertain":
                store.finish(review_id, status="uncertain", attempts_json=json.dumps(attempts),
                             http_status=exc.http_status, cost_basis="reservation kept: outcome unknown, may be billed",
                             error=f"UNCERTAIN outcome, not retried: {exc}")
                return {"status": "uncertain", "review_id": review_id, "review": None, "charged_usd": reservation,
                        "error": f"uncertain outcome ({exc}); worst case ${reservation:.4f} charged to the ledger; "
                                 "not retried automatically"}
            store.finish(review_id, status="failed", attempts_json=json.dumps(attempts), http_status=exc.http_status,
                         charged_usd=0.0, cost_usd=0.0, cost_basis="not billed: provider did not process the request",
                         error=f"{exc.kind}: {exc} after {n} attempt(s)")
            return {"status": "failed", "review_id": review_id, "review": None, "charged_usd": 0.0,
                    "error": f"provider {exc.kind} after {n} attempt(s): {exc}"}
        except Exception as exc:                      # unknown failure mid-call: treat as uncertain
            attempts.append({"attempt": n, "started_utc": started, "outcome": "uncertain", "error": repr(exc)})
            store.finish(review_id, status="uncertain", attempts_json=json.dumps(attempts),
                         cost_basis="reservation kept: outcome unknown", error=f"UNCERTAIN: {type(exc).__name__}: {exc}")
            return {"status": "uncertain", "review_id": review_id, "review": None, "charged_usd": reservation,
                    "error": f"uncertain outcome ({type(exc).__name__}); not retried"}
        break

    attempts.append({"attempt": len(attempts) + 1, "started_utc": started, "outcome": "response",
                     "http_status": res.http_status, "stop_reason": res.stop_reason})
    cost = budget.cost_usd(provider.model, res.usage)
    common = dict(attempts_json=json.dumps(attempts), http_status=res.http_status, request_id=res.request_id,
                  stop_reason=res.stop_reason, input_tokens=res.usage.get("input_tokens"),
                  output_tokens=res.usage.get("output_tokens"),
                  cache_creation_tokens=res.usage.get("cache_creation_input_tokens", 0),
                  cache_read_tokens=res.usage.get("cache_read_input_tokens", 0), cost_usd=cost,
                  cost_basis=COST_BASIS, charged_usd=cost, response_text=(res.text or "")[:20_000])
    if res.model and res.model != provider.model:
        common["error"] = f"note: provider reported model {res.model}"
    if res.stop_reason in ("refusal", "max_tokens"):
        why = "the model declined (refusal)" if res.stop_reason == "refusal" else \
            f"output truncated at max_output_tokens {auth['max_output_tokens']}"
        store.finish(review_id, status="failed", **{**common, "error": f"unusable response: {why}"})
        return {"status": "failed", "review_id": review_id, "review": None, "charged_usd": cost,
                "error": f"unusable response: {why}; ${cost:.4f} charged"}
    review, errors = validate.validate(res.text, package)
    if errors:
        store.finish(review_id, status="failed", validation_json=json.dumps(errors),
                     **{**common, "error": f"malformed or rejected response: {errors[0]}"
                                           + (f" (+{len(errors) - 1} more)" if len(errors) > 1 else "")})
        return {"status": "failed", "review_id": review_id, "review": None, "charged_usd": cost,
                "validation_errors": errors, "error": f"response rejected by validation: {errors[0]}"}
    store.finish(review_id, status="completed", review_json=json.dumps(review), validation_json="[]", **common)
    return {"status": "completed", "cached": False, "review_id": review_id, "review": review, "cost_usd": cost,
            "usage": res.usage, "model": provider.model, "prompt_version": prompt.PROMPT_VERSION,
            "evidence_fingerprint": package["fingerprint"], "mock": provider.mock}


def verify(experiment: str, env: dict, store: budget.ReviewStore, research_dir: Path = jobs.RESEARCH_DIR,
           provider: providers.Provider | None = None) -> dict:
    """The first paid call. Marks the integration verified only if a real (non-mock) review completes."""
    result = run_review(experiment, research_dir, env, store, run_ref=f"verify:{budget.now()}",
                        provider=provider, verification_call=True)
    if result["status"] == "completed" and not result.get("mock") and not result.get("cached"):
        row = store.get(result["review_id"])
        store.mark_verified(row["provider"], row["model"], row["prompt_version"], row["id"])
        result["verified"] = True
    return result
