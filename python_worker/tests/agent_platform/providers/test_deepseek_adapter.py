"""Unit tests for the DeepSeek adapter (Module 1.2).

DeepSeek's API is OpenAI-compatible, so the adapter subclasses OpenAIAdapter
and just changes defaults (base_url, supported_models, pricing).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from agent_platform.providers.adapters import ProviderError
from agent_platform.providers.adapters.deepseek_adapter import DeepSeekAdapter
from agent_platform.providers.models import ChatMessage, LLMRequest, RequestMetadata


def _meta() -> RequestMetadata:
    return RequestMetadata(
        purpose="planner",
        trace_id="t",
        workflow_id="w",
        cost_budget_remaining=1.0,
    )


def _fake_completion() -> SimpleNamespace:
    message = SimpleNamespace(content="hello", tool_calls=None, parsed=None)
    choice = SimpleNamespace(message=message, finish_reason="stop")
    usage = SimpleNamespace(
        prompt_tokens=10,
        completion_tokens=5,
        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )
    return SimpleNamespace(choices=[choice], usage=usage, model="deepseek-chat")


class TestDeepSeekAdapter:
    def test_metadata(self):
        adapter = DeepSeekAdapter(api_key="ds-test")
        assert adapter.name == "deepseek"
        assert "deepseek-chat" in adapter.supported_models
        assert "deepseek-reasoner" in adapter.supported_models

    @pytest.mark.asyncio
    async def test_basic_completion(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_fake_completion())
        adapter = DeepSeekAdapter(api_key="ds-test", client=client)

        req = LLMRequest(
            model="deepseek-chat",
            messages=[ChatMessage(role="user", content="hi")],
            metadata=_meta(),
        )
        resp = await adapter.complete(req)

        assert resp.text == "hello"
        assert resp.provider == "deepseek"
        # deepseek-chat is priced → cost > 0
        assert resp.cost_usd > 0

    def test_default_base_url_is_deepseek(self):
        # When no explicit client is injected, the constructed client should
        # point at DeepSeek's endpoint.
        adapter = DeepSeekAdapter(api_key="ds-test")
        # AsyncOpenAI exposes base_url on the client
        assert "deepseek" in str(adapter._client.base_url)

    @pytest.mark.asyncio
    async def test_refuses_structured_output(self):
        class _Plan(BaseModel):
            summary: str

        client = MagicMock()
        # parse() must NOT be called — adapter should reject before dispatch.
        client.chat.completions.parse = AsyncMock(
            side_effect=AssertionError("parse() must not be called")
        )
        adapter = DeepSeekAdapter(api_key="ds-test", client=client)

        req = LLMRequest(
            model="deepseek-chat",
            messages=[ChatMessage(role="user", content="hi")],
            metadata=_meta(),
            output_schema=_Plan,
        )
        with pytest.raises(ProviderError) as exc:
            await adapter.complete(req)
        assert exc.value.retryable is False
        assert "structured output" in str(exc.value)
