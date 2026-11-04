"""Provider interface. One real implementation: Anthropic's Messages API through the official
`anthropic` SDK, imported lazily (it is not installed until the owner chooses this provider).

The SDK's own automatic retries are disabled (max_retries=0): a timed-out request may already
have been processed and billed, so retry decisions are made by review.py, which never repeats
an uncertain call. No tools are sent; the model can only return text.

Error classes:
  not_processed  the provider answered that it did not process the request (429 rate limit,
                 529 overloaded). Not billed. Bounded retry is allowed.
  rejected       the request was refused (400/401/402/403/404/413). Not billed. No retry.
  uncertain      timeout, dropped connection, or other 5xx: the request may have been
                 processed and billed. Never retried automatically.
"""

from dataclasses import dataclass, field


class ProviderError(Exception):
    def __init__(self, kind: str, message: str, http_status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.kind, self.http_status, self.retry_after = kind, http_status, retry_after


@dataclass
class ProviderResult:
    stop_reason: str
    text: str
    usage: dict = field(default_factory=dict)
    request_id: str | None = None
    http_status: int = 200
    model: str | None = None


class Provider:
    name = "base"
    mock = False

    def __init__(self, model: str, env: dict):
        self.model, self.env = model, env

    def unavailable_reasons(self) -> list[str]:
        raise NotImplementedError

    def complete(self, system: str, user: str, schema: dict, max_tokens: int, effort: str,
                 timeout: float) -> ProviderResult:
        raise NotImplementedError


def sdk_installed() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


class AnthropicProvider(Provider):
    name = "anthropic"

    def unavailable_reasons(self) -> list[str]:
        out = []
        if not sdk_installed():
            out.append("anthropic SDK is not installed (adding it is part of the provider decision)")
        if not self.env.get("ANTHROPIC_API_KEY"):
            out.append("ANTHROPIC_API_KEY is not set in the environment")
        return out

    def complete(self, system, user, schema, max_tokens, effort, timeout) -> ProviderResult:
        import anthropic
        # The key is passed explicitly from the process environment so no other credential source
        # (CLI profiles, desktop configuration) is ever picked up.
        client = anthropic.Anthropic(api_key=self.env["ANTHROPIC_API_KEY"], max_retries=0, timeout=timeout)
        try:
            resp = client.messages.create(
                model=self.model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            )
        except anthropic.APITimeoutError as exc:
            raise ProviderError("uncertain", f"timeout after {timeout}s: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("uncertain", f"connection error: {exc}") from exc
        except anthropic.RateLimitError as exc:
            ra = exc.response.headers.get("retry-after") if exc.response is not None else None
            raise ProviderError("not_processed", "rate limited (429)", 429,
                                float(ra) if ra and ra.replace(".", "", 1).isdigit() else None) from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code == 529:
                raise ProviderError("not_processed", "overloaded (529)", 529) from exc
            if exc.status_code >= 500:
                raise ProviderError("uncertain", f"server error {exc.status_code}", exc.status_code) from exc
            raise ProviderError("rejected", f"request rejected ({exc.status_code}): {exc.message}",
                                exc.status_code) from exc
        text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
        u = resp.usage
        usage = {k: int(getattr(u, k, 0) or 0) for k in ("input_tokens", "output_tokens",
                                                         "cache_creation_input_tokens", "cache_read_input_tokens")}
        return ProviderResult(stop_reason=resp.stop_reason or "unknown", text=text, usage=usage,
                              request_id=getattr(resp, "_request_id", None), model=resp.model)


def make_provider(auth: dict, env: dict) -> Provider:
    if auth["provider"] == "anthropic":
        return AnthropicProvider(auth["model"], env)
    raise ValueError(f"unsupported provider {auth['provider']!r}")
