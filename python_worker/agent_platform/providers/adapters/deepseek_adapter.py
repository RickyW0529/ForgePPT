"""DeepSeek adapter.

DeepSeek exposes an OpenAI-compatible REST API, so we subclass OpenAIAdapter
and only override metadata, pricing, and the default base URL.
"""

from __future__ import annotations

from typing import ClassVar

from agent_platform.providers.adapters.openai_adapter import OpenAIAdapter
from agent_platform.providers.pricing import DEEPSEEK_PRICING, ModelPrice


class DeepSeekAdapter(OpenAIAdapter):
    name: ClassVar[str] = "deepseek"
    supported_models: ClassVar[list[str]] = ["deepseek-chat", "deepseek-reasoner"]
    supports_structured_output: ClassVar[bool] = False  # parse() helper unreliable
    supports_tool_calling: ClassVar[bool] = True
    supports_streaming: ClassVar[bool] = False

    _pricing: ClassVar[dict[str, ModelPrice]] = DEEPSEEK_PRICING
    _default_base_url: ClassVar[str | None] = "https://api.deepseek.com"
