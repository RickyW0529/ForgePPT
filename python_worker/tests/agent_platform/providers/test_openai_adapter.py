"""Unit tests for the OpenAI adapter (Module 1.2).

These tests inject a mock `AsyncOpenAI` client into the adapter to keep them
hermetic — no network calls and no API keys required.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import openai
import pytest
from pydantic import BaseModel

from agent_platform.providers.adapters import (
    AuthError,
    ProviderError,
    RateLimitError,
    ServerError,
    TimeoutError,
)
from agent_platform.providers.adapters.openai_adapter import OpenAIAdapter
from agent_platform.providers.models import (
    ChatMessage,
    LLMRequest,
    RequestMetadata,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _meta() -> RequestMetadata:
    return RequestMetadata(
        purpose="planner",
        trace_id="t-1",
        workflow_id="w-1",
        cost_budget_remaining=1.0,
    )


def _req(model: str = "gpt-4o-mini", **kwargs) -> LLMRequest:
    return LLMRequest(
        model=model,
        messages=[ChatMessage(role="user", content="hi")],
        metadata=_meta(),
        **kwargs,
    )


def _fake_completion(
    *,
    content: str = "hello",
    finish_reason: str = "stop",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    cached_tokens: int = 0,
    reasoning_tokens: int = 0,
    tool_calls: list | None = None,
    model: str = "gpt-4o-mini",
) -> SimpleNamespace:
    """Build a SimpleNamespace shaped like an openai ChatCompletion."""
    message = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        parsed=None,
    )
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    prompt_details = SimpleNamespace(cached_tokens=cached_tokens)
    completion_details = SimpleNamespace(reasoning_tokens=reasoning_tokens)
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        prompt_tokens_details=prompt_details,
        completion_tokens_details=completion_details,
    )
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


def _fake_request_obj():
    """openai SDK errors require a `request` object on construction."""
    import httpx

    return httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def _fake_response_obj(status_code: int):
    import httpx

    return httpx.Response(status_code, request=_fake_request_obj())


def _build_adapter(client) -> OpenAIAdapter:
    return OpenAIAdapter(api_key="sk-test", client=client)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


class TestTextPath:
    @pytest.mark.asyncio
    async def test_basic_completion(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_fake_completion())
        adapter = _build_adapter(client)

        resp = await adapter.complete(_req())

        assert resp.text == "hello"
        assert resp.parsed is None
        assert resp.tool_calls == []
        assert resp.tokens.input_tokens == 10
        assert resp.tokens.output_tokens == 5
        assert resp.provider == "openai"
        assert resp.finish_reason == "stop"
        assert resp.latency_ms >= 0
        # gpt-4o-mini has known pricing → cost should be > 0
        assert resp.cost_usd > 0

    @pytest.mark.asyncio
    async def test_cached_and_reasoning_tokens_extracted(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            return_value=_fake_completion(
                prompt_tokens=1000,
                completion_tokens=400,
                cached_tokens=600,
                reasoning_tokens=350,
            )
        )
        adapter = _build_adapter(client)

        resp = await adapter.complete(_req())

        assert resp.tokens.input_tokens == 1000
        assert resp.tokens.cached_input_tokens == 600
        assert resp.tokens.output_tokens == 400
        assert resp.tokens.reasoning_output_tokens == 350

    @pytest.mark.asyncio
    async def test_unknown_model_costs_zero(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            return_value=_fake_completion(model="some-unlisted-model")
        )
        adapter = _build_adapter(client)

        resp = await adapter.complete(_req(model="some-unlisted-model"))

        assert resp.cost_usd == 0.0


# ---------------------------------------------------------------------------
# Structured output
# ---------------------------------------------------------------------------


class _Plan(BaseModel):
    summary: str


class TestStructuredOutput:
    @pytest.mark.asyncio
    async def test_uses_parse_endpoint_when_output_schema_given(self):
        plan_obj = _Plan(summary="ok")
        fake = _fake_completion(content='{"summary":"ok"}')
        fake.choices[0].message.parsed = plan_obj

        client = MagicMock()
        client.chat.completions.parse = AsyncMock(return_value=fake)
        client.chat.completions.create = AsyncMock(
            side_effect=AssertionError("create() must not be called when parsing")
        )
        adapter = _build_adapter(client)

        req = _req(output_schema=_Plan)
        resp = await adapter.complete(req)

        assert isinstance(resp.parsed, _Plan)
        assert resp.parsed.summary == "ok"
        assert resp.text == '{"summary":"ok"}'
        # parse() should have received response_format=_Plan
        kwargs = client.chat.completions.parse.call_args.kwargs
        assert kwargs["response_format"] is _Plan


# ---------------------------------------------------------------------------
# Tool calls
# ---------------------------------------------------------------------------


class TestToolCalls:
    @pytest.mark.asyncio
    async def test_tool_calls_extracted(self):
        tc = SimpleNamespace(
            id="call-abc",
            function=SimpleNamespace(
                name="ppt_apply_style",
                arguments='{"font_color":"#0F2A5C"}',
            ),
        )
        fake = _fake_completion(
            content="", finish_reason="tool_calls", tool_calls=[tc]
        )
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=fake)
        adapter = _build_adapter(client)

        resp = await adapter.complete(_req())

        assert resp.finish_reason == "tool_calls"
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].call_id == "call-abc"
        assert resp.tool_calls[0].name == "ppt_apply_style"
        assert resp.tool_calls[0].arguments == {"font_color": "#0F2A5C"}


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


class TestErrorMapping:
    @pytest.mark.asyncio
    async def test_rate_limit_is_mapped(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError(
                "rate limit",
                response=_fake_response_obj(429),
                body=None,
            )
        )
        adapter = _build_adapter(client)

        with pytest.raises(RateLimitError) as exc:
            await adapter.complete(_req())
        assert exc.value.retryable is True

    @pytest.mark.asyncio
    async def test_auth_error_is_mapped(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=openai.AuthenticationError(
                "bad key",
                response=_fake_response_obj(401),
                body=None,
            )
        )
        adapter = _build_adapter(client)

        with pytest.raises(AuthError) as exc:
            await adapter.complete(_req())
        assert exc.value.retryable is False

    @pytest.mark.asyncio
    async def test_server_error_is_mapped(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=openai.InternalServerError(
                "boom",
                response=_fake_response_obj(500),
                body=None,
            )
        )
        adapter = _build_adapter(client)

        with pytest.raises(ServerError) as exc:
            await adapter.complete(_req())
        assert exc.value.retryable is True

    @pytest.mark.asyncio
    async def test_timeout_is_mapped(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=openai.APITimeoutError(request=_fake_request_obj())
        )
        adapter = _build_adapter(client)

        with pytest.raises(TimeoutError) as exc:
            await adapter.complete(_req())
        assert exc.value.retryable is True

    @pytest.mark.asyncio
    async def test_unexpected_error_wrapped_as_provider_error(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=RuntimeError("???"))
        adapter = _build_adapter(client)

        with pytest.raises(ProviderError):
            await adapter.complete(_req())

    @pytest.mark.asyncio
    async def test_bad_request_is_non_retryable_provider_error(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=openai.BadRequestError(
                "bad",
                response=_fake_response_obj(400),
                body=None,
            )
        )
        adapter = _build_adapter(client)

        with pytest.raises(ProviderError) as exc:
            await adapter.complete(_req())
        assert exc.value.retryable is False
        # Specifically NOT the retryable subclasses
        assert not isinstance(exc.value, RateLimitError)
        assert not isinstance(exc.value, ServerError)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_usage_none_yields_zero_tokens(self):
        client = MagicMock()
        fake = _fake_completion()
        fake.usage = None
        client.chat.completions.create = AsyncMock(return_value=fake)
        adapter = _build_adapter(client)

        resp = await adapter.complete(_req())
        assert resp.tokens.input_tokens == 0
        assert resp.tokens.output_tokens == 0
        assert resp.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_content_filter_finish_reason_preserved(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            return_value=_fake_completion(finish_reason="content_filter")
        )
        adapter = _build_adapter(client)

        resp = await adapter.complete(_req())
        assert resp.finish_reason == "content_filter"

    @pytest.mark.asyncio
    async def test_unknown_finish_reason_becomes_error(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            return_value=_fake_completion(finish_reason="something_new")
        )
        adapter = _build_adapter(client)

        resp = await adapter.complete(_req())
        assert resp.finish_reason == "error"

    @pytest.mark.asyncio
    async def test_versioned_model_falls_back_to_request_model_for_pricing(self):
        # Server returns a versioned alias unknown to the pricing table; we
        # should fall back to the canonical model the caller requested.
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            return_value=_fake_completion(model="gpt-4o-mini-2024-07-18")
        )
        adapter = _build_adapter(client)

        resp = await adapter.complete(_req(model="gpt-4o-mini"))
        assert resp.cost_usd > 0

    @pytest.mark.asyncio
    async def test_kwargs_forwarded_to_sdk(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_fake_completion())
        adapter = _build_adapter(client)

        req = _req(temperature=0.7, seed=99, tools=[{"type": "function"}])
        await adapter.complete(req)

        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["temperature"] == 0.7
        assert kwargs["seed"] == 99
        assert kwargs["tools"] == [{"type": "function"}]
        assert kwargs["model"] == "gpt-4o-mini"
        assert "response_format" not in kwargs  # text path → no response_format

    @pytest.mark.asyncio
    async def test_json_response_format_forwarded(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_fake_completion())
        adapter = _build_adapter(client)

        await adapter.complete(_req(response_format="json"))

        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["response_format"] == {"type": "json_object"}


# ---------------------------------------------------------------------------
# Class-level metadata
# ---------------------------------------------------------------------------


class TestAdapterMetadata:
    def test_class_attributes(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        assert adapter.name == "openai"
        assert "gpt-4o-mini" in adapter.supported_models
        assert adapter.supports_structured_output is True
        assert adapter.supports_tool_calling is True

    @pytest.mark.asyncio
    async def test_health_check_uses_client(self):
        client = MagicMock()
        client.models.list = AsyncMock(return_value=SimpleNamespace(data=[]))
        adapter = _build_adapter(client)

        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_false_on_failure(self):
        client = MagicMock()
        client.models.list = AsyncMock(side_effect=RuntimeError("down"))
        adapter = _build_adapter(client)

        assert await adapter.health_check() is False
