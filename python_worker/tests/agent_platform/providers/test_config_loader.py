"""Tests for ProviderConfig + build_router_from_env (Module 1.4)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from agent_platform.providers.adapters import OpenAIAdapter, DeepSeekAdapter
from agent_platform.providers.config_loader import ProviderConfig, build_router
from agent_platform.providers.models import RequestPurpose
from agent_platform.providers.router import RoutingPolicy


class TestProviderConfig:
    def test_from_env_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = ProviderConfig.from_env()
        assert cfg.openai_api_key == ""
        assert cfg.deepseek_api_key == ""
        assert cfg.default_provider == "openai"
        assert cfg.default_model == "gpt-4o-mini"
        assert cfg.budget_usd_per_run == 2.0

    def test_from_env_reads_vars(self):
        env = {
            "PPT_OPENAI_API_KEY": "sk-test",
            "PPT_DEEPSEEK_API_KEY": "ds-test",
            "PPT_DEFAULT_PROVIDER": "deepseek",
            "PPT_DEFAULT_MODEL": "deepseek-chat",
            "PPT_BUDGET_USD_PER_RUN": "5.0",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = ProviderConfig.from_env()
        assert cfg.openai_api_key == "sk-test"
        assert cfg.deepseek_api_key == "ds-test"
        assert cfg.default_provider == "deepseek"
        assert cfg.default_model == "deepseek-chat"
        assert cfg.budget_usd_per_run == 5.0

    def test_env_prefix_stripped(self):
        # Pydantic-settings with env_prefix="PPT_" should map
        # PPT_OPENAI_API_KEY → openai_api_key automatically.
        env = {"PPT_OPENAI_API_KEY": "sk-x"}
        with patch.dict(os.environ, env, clear=True):
            cfg = ProviderConfig.from_env()
        assert cfg.openai_api_key == "sk-x"


class TestBuildRouter:
    def test_builds_openai_only(self):
        env = {
            "PPT_OPENAI_API_KEY": "sk-test",
            "PPT_DEFAULT_PROVIDER": "openai",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = ProviderConfig.from_env()
            router = build_router(cfg)

        # Should have openai registered
        assert router._registry.has("openai")
        # DeepSeek should NOT be registered (no key)
        assert not router._registry.has("deepseek")
        # Budget should exist
        assert router._budget is not None
        assert router._budget.initial == 2.0

    def test_builds_both_when_keys_present(self):
        env = {
            "PPT_OPENAI_API_KEY": "sk-test",
            "PPT_DEEPSEEK_API_KEY": "ds-test",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = ProviderConfig.from_env()
            router = build_router(cfg)

        assert router._registry.has("openai")
        assert router._registry.has("deepseek")

    def test_builds_with_custom_budget(self):
        env = {
            "PPT_OPENAI_API_KEY": "sk-test",
            "PPT_BUDGET_USD_PER_RUN": "0.5",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = ProviderConfig.from_env()
            router = build_router(cfg)

        assert router._budget is not None
        assert router._budget.initial == 0.5

    def test_no_adapters_when_no_keys(self):
        env = {}
        with patch.dict(os.environ, env, clear=True):
            cfg = ProviderConfig.from_env()
            # No keys → should still build but registry is empty
            router = build_router(cfg)

        assert not router._registry.has("openai")
        assert not router._registry.has("deepseek")

    def test_default_chain_uses_default_provider_first(self):
        env = {
            "PPT_OPENAI_API_KEY": "sk-test",
            "PPT_DEEPSEEK_API_KEY": "ds-test",
            "PPT_DEFAULT_PROVIDER": "deepseek",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = ProviderConfig.from_env()
            router = build_router(cfg)

        policy: RoutingPolicy = router._policy
        # The default chain should start with the configured default provider
        assert policy.default_chain[0] == "deepseek"
