"""Integration tests: router wiring + singleton access (Module 1.4)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from agent_platform.providers import get_router
from agent_platform.providers.router import ProviderRouter


class TestSingletonRouter:
    def test_returns_router_instance(self):
        env = {"PPT_OPENAI_API_KEY": "sk-test"}
        with patch.dict(os.environ, env, clear=True):
            router = get_router()
        assert isinstance(router, ProviderRouter)

    def test_same_instance_on_repeated_calls(self):
        env = {"PPT_OPENAI_API_KEY": "sk-test"}
        with patch.dict(os.environ, env, clear=True):
            r1 = get_router()
            r2 = get_router()
        assert r1 is r2

    def test_router_has_budget(self):
        env = {"PPT_OPENAI_API_KEY": "sk-test"}
        with patch.dict(os.environ, env, clear=True):
            router = get_router()
        assert router._budget is not None
        assert router._budget.initial == 2.0

    def test_router_without_keys_has_empty_registry(self):
        env = {}
        # Need to clear any cached singleton from previous tests
        with patch.dict(os.environ, env, clear=True):
            # Force re-creation by clearing the module-level cache
            import agent_platform.providers as _providers
            _providers._router_instance = None
            router = get_router()
        assert not router._registry.has("openai")
