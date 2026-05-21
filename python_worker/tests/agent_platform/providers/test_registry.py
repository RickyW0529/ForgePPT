"""Unit tests for ProviderRegistry (Module 1.3)."""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import AsyncMock

import pytest

from agent_platform.providers.adapters import ProviderAdapter
from agent_platform.providers.models import LLMRequest, LLMResponse
from agent_platform.providers.registry import ProviderRegistry


class _StubAdapter:
    """Minimal ProviderAdapter implementation for tests."""

    def __init__(
        self,
        name: str,
        models: list[str],
        *,
        structured: bool = True,
        tools: bool = True,
    ) -> None:
        self.name = name
        self.supported_models = list(models)
        self.supports_structured_output = structured
        self.supports_tool_calling = tools
        self.supports_streaming = False
        self.complete = AsyncMock()
        self.health_check = AsyncMock(return_value=True)


class TestProviderRegistry:
    def test_register_and_get_by_name(self):
        reg = ProviderRegistry()
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        reg.register(a)

        assert reg.get("openai") is a

    def test_get_unknown_raises(self):
        reg = ProviderRegistry()
        with pytest.raises(KeyError):
            reg.get("nope")

    def test_register_duplicate_raises(self):
        reg = ProviderRegistry()
        reg.register(_StubAdapter("openai", ["gpt-4o-mini"]))
        with pytest.raises(ValueError):
            reg.register(_StubAdapter("openai", ["gpt-4o-mini"]))

    def test_find_by_model(self):
        reg = ProviderRegistry()
        a = _StubAdapter("openai", ["gpt-4o-mini", "gpt-5"])
        b = _StubAdapter("deepseek", ["deepseek-chat"])
        reg.register(a)
        reg.register(b)

        assert reg.find_by_model("gpt-4o-mini") == [a]
        assert reg.find_by_model("deepseek-chat") == [b]
        assert reg.find_by_model("unknown") == []

    def test_find_by_model_returns_all_supporting_adapters(self):
        # Two adapters can support the same model alias (e.g. an Azure mirror).
        reg = ProviderRegistry()
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        b = _StubAdapter("openai-mirror", ["gpt-4o-mini"])
        reg.register(a)
        reg.register(b)

        found = reg.find_by_model("gpt-4o-mini")
        assert set(found) == {a, b}

    def test_runtime_checkable_protocol_satisfied(self):
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        assert isinstance(a, ProviderAdapter)
