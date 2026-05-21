"""Integration tests for the agent Plan-Solve subgraph (Module 4.8)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from agent_platform.orchestration.agent_graph import build_agent_subgraph
from agent_platform.orchestration.plans import AgentPlan, PlanStep, AgentTrace
from agent_platform.orchestration.runner import run_agent_subgraph
from agent_platform.orchestration.state import AgentGraphState
from agent_platform.context.builders import PlannerContext
from agent_platform.providers.models import LLMResponse, TokenUsage
from agent_platform.providers.router import ProviderRouter
from agent_platform.tools.descriptor import Capability, ToolDescriptor
from agent_platform.tools.registry import ToolRegistry
from agent_platform.tools.sandbox import ToolContext, ToolExecutionError, ToolOutput
from models.ppt_state import PPTState, Slide, SlideSize
from models.workflow_def import AgentNodeConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_ppt() -> PPTState:
    return PPTState(
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


class _In(BaseModel):
    value: int = 0


class _Out(BaseModel):
    pass


class _MockAddTool:
    """Mock tool that appends '_v{N}' to source_file."""

    descriptor = ToolDescriptor(
        name="mock_add",
        description="adds value",
        input_schema=_In,
        output_schema=_Out,
        capabilities=[Capability.READ_TEXT],
    )

    async def execute(
        self,
        ppt_state: dict[str, Any],
        params: _In,
        target: Any,
        ctx: ToolContext,
    ) -> ToolOutput:
        new_state = dict(ppt_state)
        base = new_state["source_file"].replace(".pptx", "")
        new_state["source_file"] = f"{base}_v{params.value}.pptx"
        return ToolOutput(new_state=new_state, summary={"added": params.value})


class _MockFailTool:
    """Mock tool that always raises ToolExecutionError."""

    descriptor = ToolDescriptor(
        name="mock_fail",
        description="always fails",
        input_schema=_In,
        output_schema=_Out,
        capabilities=[Capability.READ_TEXT],
    )

    async def execute(
        self,
        ppt_state: dict[str, Any],
        params: _In,
        target: Any,
        ctx: ToolContext,
    ) -> ToolOutput:
        raise ToolExecutionError(code="internal_error", message="boom")


def _make_registry(*tools: Any) -> ToolRegistry:
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    return reg


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


def _make_initial_state(ppt: PPTState | None = None) -> AgentGraphState:
    if ppt is None:
        ppt = _minimal_ppt()
    planner_ctx = PlannerContext(
        deck_meta={"slide_count": ppt.slide_count},
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
        "plan_iteration": 0,
        "plan_failures": [],
        "step_results": [],
        "last_validation_ok": True,
        "working_ppt_state": ppt,
        "trace": None,
    }


# ---------------------------------------------------------------------------
# Test 1: Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Happy path: valid plan -> solver executes -> success trace."""
        tool = _MockAddTool()
        reg = _make_registry(tool)
        plan = AgentPlan(
            summary="test",
            steps=[PlanStep(step_id="s1", tool="mock_add", params={"value": 5})],
        )
        router = _mock_router(plan)
        graph = build_agent_subgraph(reg, router)

        initial_state = _make_initial_state()
        final_state = await graph.ainvoke(initial_state)

        trace = final_state["trace"]
        assert trace is not None
        assert trace.status == "success"
        assert len(trace.step_results) == 1
        assert trace.step_results[0].status == "ok"

        working = final_state["working_ppt_state"]
        assert working.source_file == "/tmp/test_v5.pptx"


# ---------------------------------------------------------------------------
# Test 2: Validation failure + retry
# ---------------------------------------------------------------------------


class TestValidationFailureRetry:
    @pytest.mark.asyncio
    async def test_replan_and_succeed(self):
        """Validator rejects first plan, repair retries, second plan succeeds."""
        tool = _MockAddTool()
        reg = _make_registry(tool)

        invalid_plan = AgentPlan(
            summary="bad",
            steps=[PlanStep(step_id="s1", tool="unknown_tool", params={})],
        )
        valid_plan = AgentPlan(
            summary="good",
            steps=[PlanStep(step_id="s1", tool="mock_add", params={"value": 3})],
        )

        router = AsyncMock(spec=ProviderRouter)
        router.complete.side_effect = [
            LLMResponse(
                text="",
                parsed=invalid_plan,
                tokens=TokenUsage(),
                latency_ms=100,
                provider="openai",
                model="gpt-4o-mini",
                cost_usd=0.001,
                finish_reason="stop",
            ),
            LLMResponse(
                text="",
                parsed=valid_plan,
                tokens=TokenUsage(),
                latency_ms=100,
                provider="openai",
                model="gpt-4o-mini",
                cost_usd=0.001,
                finish_reason="stop",
            ),
        ]

        graph = build_agent_subgraph(reg, router)
        initial_state = _make_initial_state()
        final_state = await graph.ainvoke(initial_state)

        trace = final_state["trace"]
        assert trace is not None
        assert trace.status == "success"
        assert final_state["plan_iteration"] == 2
        assert len(trace.plan_failures) == 1
        assert trace.plan_failures[0].failure_type == "tool_unknown"
        assert final_state["working_ppt_state"].source_file == "/tmp/test_v3.pptx"


# ---------------------------------------------------------------------------
# Test 3: Max replan exhausted
# ---------------------------------------------------------------------------


class TestMaxReplanExhausted:
    @pytest.mark.asyncio
    async def test_abort_after_max_replan(self):
        """Router always returns invalid plan; repair aborts after MAX_REPLAN."""
        reg = ToolRegistry()  # empty registry, so any tool is unknown

        bad_plan = AgentPlan(
            summary="bad",
            steps=[PlanStep(step_id="s1", tool="nonexistent", params={})],
        )
        router = _mock_router(bad_plan)
        graph = build_agent_subgraph(reg, router)

        initial_state = _make_initial_state()
        final_state = await graph.ainvoke(initial_state)

        trace = final_state["trace"]
        assert trace is not None
        assert trace.status == "failed"
        assert final_state["plan_iteration"] == 2  # MAX_REPLAN


# ---------------------------------------------------------------------------
# Test 4: Solver error
# ---------------------------------------------------------------------------


class TestSolverError:
    @pytest.mark.asyncio
    async def test_partial_status_on_tool_error(self):
        """Valid plan but tool raises -> partial trace with error recorded."""
        tool = _MockFailTool()
        reg = _make_registry(tool)
        plan = AgentPlan(
            summary="test",
            steps=[PlanStep(step_id="s1", tool="mock_fail", params={"value": 1})],
        )
        router = _mock_router(plan)
        graph = build_agent_subgraph(reg, router)

        initial_state = _make_initial_state()
        final_state = await graph.ainvoke(initial_state)

        trace = final_state["trace"]
        assert trace is not None
        assert trace.status == "partial"
        assert len(trace.step_results) == 1
        assert trace.step_results[0].status == "error"
        assert "boom" in (trace.step_results[0].error or "")


# ---------------------------------------------------------------------------
# Test 5: Runner entry point
# ---------------------------------------------------------------------------


class TestRunnerEntryPoint:
    @pytest.mark.asyncio
    async def test_run_agent_subgraph_returns_tuple(self):
        """run_agent_subgraph patches get_router and returns (PPTState, AgentTrace)."""
        ppt = _minimal_ppt()
        config = AgentNodeConfig(role="text_refiner", prompt="Make it better")

        # Use a real builtin tool in the plan so solver can execute it
        plan = AgentPlan(
            summary="apply style",
            steps=[
                PlanStep(
                    step_id="s1",
                    tool="ppt_apply_style",
                    params={"font_color": "#00FF00"},
                )
            ],
        )
        router = _mock_router(plan)

        with patch(
            "agent_platform.orchestration.runner.get_router", return_value=router
        ):
            working, trace = await run_agent_subgraph(ppt, config)

        assert isinstance(working, PPTState)
        assert isinstance(trace, AgentTrace)
        assert trace.status == "success"
        assert len(trace.step_results) == 1
        assert trace.step_results[0].status == "ok"
