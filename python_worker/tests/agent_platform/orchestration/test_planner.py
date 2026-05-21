"""Tests for planner node (Module 4.6)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from agent_platform.context.builders import PlannerContext
from agent_platform.orchestration.nodes.planner import make_planner_node
from agent_platform.orchestration.plans import AgentPlan, PlanStep
from agent_platform.orchestration.state import AgentGraphState
from agent_platform.providers.models import LLMResponse, RequestMetadata, TokenUsage
from agent_platform.providers.router import ProviderRouter
from models.ppt_state import PPTState, Slide, SlideSize
from models.workflow_def import AgentNodeConfig


def _make_state(plan_iteration: int = 0) -> AgentGraphState:
    ppt = PPTState(
        source_file="/tmp/test.pptx",
        slide_count=1,
        slides=[
            Slide(
                page_num=1,
                size=SlideSize(
                    width_emu=9_144_000,
                    height_emu=6_858_000,
                    width_px=960.0,
                    height_px=720.0,
                ),
                elements=[],
            )
        ],
        global_props=SlideSize(
            width_emu=9_144_000,
            height_emu=6_858_000,
            width_px=960.0,
            height_px=720.0,
        ),
    )
    planner_ctx = PlannerContext(
        deck_meta={"slide_count": 1},
        slides_in_scope=[],
        available_tools=[],
        role_system_prompt="editor",
        user_prompt="Make it better",
        memory_snippets=[],
        previous_attempts=[],
        constraints=[],
    )
    return {
        "initial_ppt_state": ppt,
        "config": AgentNodeConfig(role="editor", prompt="Make it better"),
        "role": "editor",
        "allowed_pages": [1],
        "planner_context": planner_ctx,
        "current_plan": None,
        "plan_iteration": plan_iteration,
        "plan_failures": [],
        "step_results": [],
        "last_validation_ok": True,
        "working_ppt_state": ppt,
        "trace": None,
    }


def _mock_router(return_plan: AgentPlan | None = None) -> ProviderRouter:
    router = AsyncMock(spec=ProviderRouter)
    response = LLMResponse(
        text="",
        parsed=return_plan,
        tokens=TokenUsage(),
        latency_ms=100,
        provider="openai",
        model="gpt-4o-mini",
        cost_usd=0.001,
        finish_reason="stop",
    )
    router.complete.return_value = response
    return router


class TestPlannerNode:
    @pytest.mark.asyncio
    async def test_increments_iteration(self):
        router = _mock_router(AgentPlan(summary="plan", steps=[]))
        node = make_planner_node(router)
        state = _make_state(plan_iteration=0)
        result = await node(state)
        assert result["plan_iteration"] == 1

    @pytest.mark.asyncio
    async def test_returns_plan_from_parsed(self):
        plan = AgentPlan(
            summary="dark theme",
            steps=[PlanStep(step_id="s1", tool="ppt_apply_style")],
        )
        router = _mock_router(plan)
        node = make_planner_node(router)
        state = _make_state()
        result = await node(state)
        assert result["current_plan"] is plan

    @pytest.mark.asyncio
    async def test_fallback_parses_text(self):
        plan = AgentPlan(
            summary="dark theme",
            steps=[PlanStep(step_id="s1", tool="ppt_apply_style")],
        )
        router = AsyncMock(spec=ProviderRouter)
        response = LLMResponse(
            text=plan.model_dump_json(),
            parsed=None,
            tokens=TokenUsage(),
            latency_ms=100,
            provider="openai",
            model="gpt-4o-mini",
            cost_usd=0.001,
            finish_reason="stop",
        )
        router.complete.return_value = response
        node = make_planner_node(router)
        state = _make_state()
        result = await node(state)
        assert result["current_plan"] is not None
        assert result["current_plan"].summary == "dark theme"

    @pytest.mark.asyncio
    async def test_none_plan_when_unparseable(self):
        router = AsyncMock(spec=ProviderRouter)
        response = LLMResponse(
            text="not json",
            parsed=None,
            tokens=TokenUsage(),
            latency_ms=100,
            provider="openai",
            model="gpt-4o-mini",
            cost_usd=0.001,
            finish_reason="stop",
        )
        router.complete.return_value = response
        node = make_planner_node(router)
        state = _make_state()
        result = await node(state)
        assert result["current_plan"] is None
