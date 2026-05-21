"""Construct a fully-wired ProviderRouter from environment variables.

This module bridges the legacy `LLMConfig` (Pydantic-settings with env_prefix)
with the new provider-management stack. It is the single entry-point for
bootstrapping adapters, registry, policy, and budget in production.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import ConfigDict
from pydantic_settings import BaseSettings

from agent_platform.providers.adapters.openai_adapter import OpenAIAdapter
from agent_platform.providers.adapters.deepseek_adapter import DeepSeekAdapter
from agent_platform.providers.budget import BudgetTracker
from agent_platform.providers.registry import ProviderRegistry
from agent_platform.providers.router import ProviderRouter, RoutingPolicy


class ProviderConfig(BaseSettings):
    """Environment-driven configuration for the provider stack.

    Variable names follow the existing `PPT_` prefix convention.
    """

    model_config = ConfigDict(
        env_prefix="PPT_",
        extra="ignore",  # coexist with legacy LLMConfig fields
    )

    openai_api_key: str = ""
    deepseek_api_key: str = ""
    default_provider: str = "openai"
    default_model: str = "gpt-4o-mini"
    budget_usd_per_run: float = 2.0

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        return cls()


def _build_registry(cfg: ProviderConfig) -> ProviderRegistry:
    """Register every adapter whose API key is present."""
    reg = ProviderRegistry()

    if cfg.openai_api_key:
        reg.register(OpenAIAdapter(api_key=cfg.openai_api_key))

    if cfg.deepseek_api_key:
        reg.register(DeepSeekAdapter(api_key=cfg.deepseek_api_key))

    return reg


def _build_policy(cfg: ProviderConfig, registry: ProviderRegistry) -> RoutingPolicy:
    """Build a RoutingPolicy that prefers the default provider."""
    available = [a.name for a in registry.all()]
    if not available:
        return RoutingPolicy(default_chain=[])

    # Default provider first, then every other registered adapter.
    default = cfg.default_provider
    chain = []
    if default in available:
        chain.append(default)
    for name in available:
        if name != default:
            chain.append(name)

    return RoutingPolicy(default_chain=chain)


def build_router(cfg: ProviderConfig | None = None) -> ProviderRouter:
    """Factory: assemble registry → policy → router with budget.

    Usage::

        from agent_platform.providers.config_loader import build_router
        router = build_router()
        response = await router.complete(request)
    """
    cfg = cfg or ProviderConfig.from_env()
    registry = _build_registry(cfg)
    policy = _build_policy(cfg, registry)
    budget = BudgetTracker(initial_usd=cfg.budget_usd_per_run)
    return ProviderRouter(registry, policy, budget=budget)
