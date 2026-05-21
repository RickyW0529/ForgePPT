"""Base interfaces and exception hierarchy for provider adapters.

Adapters wrap third-party LLM SDKs (OpenAI, Anthropic, DeepSeek, ...) behind a
single Protocol so upstream code never imports a specific vendor SDK.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agent_platform.providers.models import LLMRequest, LLMResponse


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProviderError(Exception):
    """Base error for any failure inside an adapter call."""

    retryable: bool = False

    def __init__(self, message: str, *, retryable: bool | None = None) -> None:
        super().__init__(message)
        if retryable is not None:
            self.retryable = retryable


class TimeoutError(ProviderError):  # noqa: A001 - intentional shadowing of builtin
    """Adapter call exceeded its budget."""

    retryable = True


class RateLimitError(ProviderError):
    """Upstream returned a 429 or equivalent."""

    retryable = True


class ServerError(ProviderError):
    """Upstream returned a 5xx."""

    retryable = True


class AuthError(ProviderError):
    """API key invalid / missing."""

    retryable = False


class AllProvidersExhausted(ProviderError):
    """Router tried every candidate and all of them failed."""

    retryable = False

    def __init__(self, message: str, last_error: ProviderError | None = None) -> None:
        super().__init__(message)
        self.last_error = last_error


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ProviderAdapter(Protocol):
    """Vendor-specific adapter.

    Concrete adapters MUST set the class-level attributes and implement
    `complete` and `health_check`.
    """

    name: str
    supported_models: list[str]
    supports_structured_output: bool
    supports_tool_calling: bool
    supports_streaming: bool

    async def complete(self, request: LLMRequest) -> LLMResponse: ...

    async def health_check(self) -> bool: ...
