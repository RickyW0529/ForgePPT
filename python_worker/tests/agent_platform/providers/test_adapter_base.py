"""Unit tests for ProviderAdapter base interfaces (Module 1.1)."""

import pytest

from agent_platform.providers.adapters.base import (
    AllProvidersExhausted,
    ProviderAdapter,
    ProviderError,
    RateLimitError,
    ServerError,
    TimeoutError as ProviderTimeoutError,
)


class TestErrors:
    def test_provider_error_default_retryable_false(self):
        err = ProviderError("boom")
        assert err.retryable is False

    def test_rate_limit_is_retryable(self):
        err = RateLimitError("slow down")
        assert err.retryable is True

    def test_timeout_is_retryable(self):
        err = ProviderTimeoutError("timed out")
        assert err.retryable is True

    def test_server_error_is_retryable(self):
        err = ServerError("500")
        assert err.retryable is True

    def test_all_providers_exhausted_wraps_last(self):
        last = RateLimitError("nope")
        err = AllProvidersExhausted("all done", last_error=last)
        assert err.last_error is last


class TestProtocolShape:
    """ProviderAdapter is a Protocol; assert expected attributes exist on subclasses."""

    def test_dummy_subclass_satisfies(self):
        class _Dummy:
            name = "dummy"
            supported_models = ["m1"]
            supports_structured_output = False
            supports_tool_calling = False
            supports_streaming = False

            async def complete(self, request):  # pragma: no cover - shape only
                raise NotImplementedError

            async def health_check(self) -> bool:  # pragma: no cover
                return True

        instance: ProviderAdapter = _Dummy()  # type: ignore[assignment]
        assert instance.name == "dummy"
        assert "m1" in instance.supported_models
