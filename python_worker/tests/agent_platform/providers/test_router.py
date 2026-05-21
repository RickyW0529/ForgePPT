"""Unit tests for the provider Router (Module 1.3)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from agent_platform.providers.adapters import (
    AllProvidersExhausted,
    AuthError,
    ProviderError,
    RateLimitError,
    ServerError,
)
from agent_platform.providers.budget import BudgetExhausted, BudgetTracker
from agent_platform.providers.models import (
    ChatMessage,
    LLMRequest,
    LLMResponse,
    RequestMetadata,
    RequestPurpose,
    TokenUsage,
)
from agent_platform.providers.registry import ProviderRegistry
from agent_platform.providers.router import ProviderRouter, RoutingPolicy


def _meta(purpose: str = "planner") -> RequestMetadata:
    return RequestMetadata(
        purpose=purpose,
        trace_id="t",
        workflow_id="w",
        cost_budget_remaining=1.0,
    )


def _req(model: str = "gpt-4o-mini", purpose: str = "planner") -> LLMRequest:
    return LLMRequest(
        model=model,
        messages=[ChatMessage(role="user", content="hi")],
        metadata=_meta(purpose),
    )


def _fake_response(provider: str, cost: float = 0.001) -> LLMResponse:
    return LLMResponse(
        text="ok",
        tokens=TokenUsage(input_tokens=10, output_tokens=5),
        latency_ms=10,
        provider=provider,
        model="m",
        cost_usd=cost,
        finish_reason="stop",
    )


class _StubAdapter:
    def __init__(self, name: str, models: list[str], *, structured: bool = True):
        self.name = name
        self.supported_models = list(models)
        self.supports_structured_output = structured
        self.supports_tool_calling = True
        self.supports_streaming = False
        self.complete = AsyncMock()
        self.health_check = AsyncMock(return_value=True)


def _registry(*adapters) -> ProviderRegistry:
    reg = ProviderRegistry()
    for a in adapters:
        reg.register(a)
    return reg


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestRouterHappyPath:
    @pytest.mark.asyncio
    async def test_uses_first_adapter_from_policy(self):
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        b = _StubAdapter("deepseek", ["gpt-4o-mini"])
        a.complete.return_value = _fake_response("openai")

        policy = RoutingPolicy(
            chains={RequestPurpose.PLANNER: ["openai", "deepseek"]}
        )
        router = ProviderRouter(_registry(a, b), policy)

        resp = await router.complete(_req())

        assert resp.provider == "openai"
        a.complete.assert_awaited_once()
        b.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_on_retryable_error(self):
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        b = _StubAdapter("deepseek", ["gpt-4o-mini"])
        a.complete.side_effect = RateLimitError("rate limited")
        b.complete.return_value = _fake_response("deepseek")

        policy = RoutingPolicy(
            chains={RequestPurpose.PLANNER: ["openai", "deepseek"]}
        )
        router = ProviderRouter(_registry(a, b), policy)

        resp = await router.complete(_req())

        assert resp.provider == "deepseek"
        a.complete.assert_awaited_once()
        b.complete.assert_awaited_once()


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


class TestRouterFailures:
    @pytest.mark.asyncio
    async def test_non_retryable_error_does_not_fall_back(self):
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        b = _StubAdapter("deepseek", ["gpt-4o-mini"])
        a.complete.side_effect = AuthError("bad key")

        policy = RoutingPolicy(
            chains={RequestPurpose.PLANNER: ["openai", "deepseek"]}
        )
        router = ProviderRouter(_registry(a, b), policy)

        with pytest.raises(AuthError):
            await router.complete(_req())
        b.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_retryable_failures_raise_exhausted(self):
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        b = _StubAdapter("deepseek", ["gpt-4o-mini"])
        a.complete.side_effect = RateLimitError("a")
        b.complete.side_effect = ServerError("b")

        policy = RoutingPolicy(
            chains={RequestPurpose.PLANNER: ["openai", "deepseek"]}
        )
        router = ProviderRouter(_registry(a, b), policy)

        with pytest.raises(AllProvidersExhausted) as exc:
            await router.complete(_req())
        assert isinstance(exc.value.last_error, ServerError)

    @pytest.mark.asyncio
    async def test_purpose_with_no_chain_uses_default(self):
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        a.complete.return_value = _fake_response("openai")

        policy = RoutingPolicy(
            chains={},
            default_chain=["openai"],
        )
        router = ProviderRouter(_registry(a), policy)

        resp = await router.complete(_req(purpose="solver_inner"))
        assert resp.provider == "openai"

    @pytest.mark.asyncio
    async def test_empty_chain_raises_exhausted(self):
        policy = RoutingPolicy(chains={}, default_chain=[])
        router = ProviderRouter(ProviderRegistry(), policy)

        with pytest.raises(AllProvidersExhausted):
            await router.complete(_req())

    @pytest.mark.asyncio
    async def test_adapter_not_registered_is_skipped(self):
        # Policy lists "ghost" but registry has no such adapter — must
        # gracefully skip rather than KeyError out of the loop.
        b = _StubAdapter("deepseek", ["gpt-4o-mini"])
        b.complete.return_value = _fake_response("deepseek")

        policy = RoutingPolicy(
            chains={RequestPurpose.PLANNER: ["ghost", "deepseek"]}
        )
        router = ProviderRouter(_registry(b), policy)

        resp = await router.complete(_req())
        assert resp.provider == "deepseek"


# ---------------------------------------------------------------------------
# Budget integration
# ---------------------------------------------------------------------------


class TestRouterBudget:
    @pytest.mark.asyncio
    async def test_deducts_cost_after_success(self):
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        a.complete.return_value = _fake_response("openai", cost=0.30)
        budget = BudgetTracker(initial_usd=1.0)

        policy = RoutingPolicy(chains={RequestPurpose.PLANNER: ["openai"]})
        router = ProviderRouter(_registry(a), policy, budget=budget)

        await router.complete(_req())
        assert budget.remaining == pytest.approx(0.70)

    @pytest.mark.asyncio
    async def test_does_not_deduct_on_failure(self):
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        a.complete.side_effect = RateLimitError("nope")
        budget = BudgetTracker(initial_usd=1.0)

        policy = RoutingPolicy(chains={RequestPurpose.PLANNER: ["openai"]})
        router = ProviderRouter(_registry(a), policy, budget=budget)

        with pytest.raises(AllProvidersExhausted):
            await router.complete(_req())
        assert budget.remaining == 1.0

    @pytest.mark.asyncio
    async def test_exhausted_budget_blocks_dispatch(self):
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        a.complete.return_value = _fake_response("openai", cost=0.99)
        budget = BudgetTracker(initial_usd=1.0)
        await budget.deduct(1.0)  # drain

        policy = RoutingPolicy(chains={RequestPurpose.PLANNER: ["openai"]})
        router = ProviderRouter(_registry(a), policy, budget=budget)

        with pytest.raises(BudgetExhausted):
            await router.complete(_req())
        a.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_overspend_in_deduct_propagates_from_router(self):
        # Adapter call succeeds but the deduct itself would overspend.
        # The response must NOT be returned — BudgetExhausted must propagate
        # so the workflow halts instead of continuing with unfunded calls.
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        a.complete.return_value = _fake_response("openai", cost=0.99)
        budget = BudgetTracker(initial_usd=0.50)

        policy = RoutingPolicy(chains={RequestPurpose.PLANNER: ["openai"]})
        router = ProviderRouter(_registry(a), policy, budget=budget)

        with pytest.raises(BudgetExhausted):
            await router.complete(_req())
        assert budget.remaining == pytest.approx(0.50)  # untouched

    @pytest.mark.asyncio
    async def test_policy_accepts_string_purpose_keys(self):
        a = _StubAdapter("openai", ["gpt-4o-mini"])
        a.complete.return_value = _fake_response("openai")

        policy = RoutingPolicy(chains={"planner": ["openai"]})
        router = ProviderRouter(_registry(a), policy)

        resp = await router.complete(_req())
        assert resp.provider == "openai"
