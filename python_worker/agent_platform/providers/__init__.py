"""LLM provider management: unified request/response, adapters, routing.

See `docs/superpowers/specs/2026-05-21-agent-platform/03-llm-provider-management.md`.
"""

from agent_platform.providers.budget import BudgetExhausted, BudgetTracker
from agent_platform.providers.config_loader import build_router
from agent_platform.providers.models import (
    ChatMessage,
    LLMRequest,
    LLMResponse,
    RequestMetadata,
    RequestPurpose,
    TokenUsage,
    ToolCall,
)
from agent_platform.providers.registry import ProviderRegistry
from agent_platform.providers.router import ProviderRouter, RoutingPolicy

_router_instance: ProviderRouter | None = None


def get_router() -> ProviderRouter:
    """Return a lazily-initialized singleton ProviderRouter.

    The router is built from environment variables on first call and cached
    for the lifetime of the process.
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = build_router()
    return _router_instance


__all__ = [
    "BudgetExhausted",
    "BudgetTracker",
    "ChatMessage",
    "LLMRequest",
    "LLMResponse",
    "ProviderRegistry",
    "ProviderRouter",
    "RequestMetadata",
    "RequestPurpose",
    "RoutingPolicy",
    "TokenUsage",
    "ToolCall",
    "build_router",
    "get_router",
]
