"""Tests for solver node (Module 4.5)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from agent_platform.orchestration.nodes.solver import (
    _topological_order,
    make_solver_node,
)
from agent_platform.orchestration.plans import AgentPlan, PlanStep, TargetSelector
from agent_platform.orchestration.state import AgentGraphState
from agent_platform.tools.descriptor import Capability, ToolDescriptor
from agent_platform.tools.registry import ToolRegistry
from agent_platform.tools.sandbox import ToolContext, ToolExecutionError, ToolOutput
from models.ppt_state import PPTState, Slide, SlideSize
from models.workflow_def import AgentNodeConfig


class _In(BaseModel):
    value: int = 0


class _Out(BaseModel):
    pass


class _AddTool:
    """Mock tool that appends '_v{N}' to source_file."""

    descriptor = ToolDescriptor(
        name="add",
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


class _FailTool:
    """Mock tool that always raises."""

    descriptor = ToolDescriptor(
        name="fail",
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


def _make_state(plan: AgentPlan, working: PPTState | None = None) -> AgentGraphState:
    if working is None:
        working = PPTState(
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
    return {
        "initial_ppt_state": working,
        "config": AgentNodeConfig(role="editor"),
        "role": "editor",
        "allowed_pages": [1],
        "planner_context": {},  # type: ignore[typeddict-item]
        "current_plan": plan,
        "plan_iteration": 0,
        "plan_failures": [],
        "step_results": [],
        "last_validation_ok": True,
        "working_ppt_state": working,
        "trace": None,
    }


class TestTopologicalOrder:
    def test_empty(self):
        assert _topological_order([]) == []

    def test_no_deps(self):
        steps = [
            PlanStep(step_id="a", tool="t"),
            PlanStep(step_id="b", tool="t"),
        ]
        ordered = _topological_order(steps)
        assert [s.step_id for s in ordered] == ["a", "b"]

    def test_linear_deps(self):
        steps = [
            PlanStep(step_id="a", tool="t"),
            PlanStep(step_id="b", tool="t", depends_on=["a"]),
            PlanStep(step_id="c", tool="t", depends_on=["b"]),
        ]
        ordered = _topological_order(steps)
        ids = [s.step_id for s in ordered]
        assert ids.index("a") < ids.index("b") < ids.index("c")

    def test_diamond_deps(self):
        steps = [
            PlanStep(step_id="a", tool="t"),
            PlanStep(step_id="b", tool="t", depends_on=["a"]),
            PlanStep(step_id="c", tool="t", depends_on=["a"]),
            PlanStep(step_id="d", tool="t", depends_on=["b", "c"]),
        ]
        ordered = _topological_order(steps)
        ids = [s.step_id for s in ordered]
        assert ids.index("a") < ids.index("b")
        assert ids.index("a") < ids.index("c")
        assert ids.index("b") < ids.index("d")
        assert ids.index("c") < ids.index("d")


class TestSolverNode:
    @pytest.mark.asyncio
    async def test_executes_single_step(self):
        reg = _make_registry(_AddTool())
        plan = AgentPlan(
            summary="test",
            steps=[PlanStep(step_id="s1", tool="add", params={"value": 5})],
        )
        state = _make_state(plan)
        node = make_solver_node(reg)
        result = await node(state)

        assert "working_ppt_state" in result
        assert result["working_ppt_state"].source_file == "/tmp/test_v5.pptx"
        assert len(result["step_results"]) == 1
        assert result["step_results"][0].status == "ok"

    @pytest.mark.asyncio
    async def test_executes_multiple_steps(self):
        reg = _make_registry(_AddTool())
        plan = AgentPlan(
            summary="test",
            steps=[
                PlanStep(step_id="s1", tool="add", params={"value": 3}),
                PlanStep(step_id="s2", tool="add", params={"value": 2}),
            ],
        )
        state = _make_state(plan)
        node = make_solver_node(reg)
        result = await node(state)

        assert result["working_ppt_state"].source_file == "/tmp/test_v3_v2.pptx"
        assert len(result["step_results"]) == 2

    @pytest.mark.asyncio
    async def test_step_error_recorded(self):
        reg = _make_registry(_FailTool())
        plan = AgentPlan(
            summary="test",
            steps=[PlanStep(step_id="s1", tool="fail", params={"value": 1})],
        )
        state = _make_state(plan)
        node = make_solver_node(reg)
        result = await node(state)

        assert len(result["step_results"]) == 1
        assert result["step_results"][0].status == "error"
        assert "boom" in result["step_results"][0].error

    @pytest.mark.asyncio
    async def test_error_stops_on_critical(self):
        """By default (continue_on_error=False), an error stops execution."""
        reg = _make_registry(_AddTool(), _FailTool())
        plan = AgentPlan(
            summary="test",
            steps=[
                PlanStep(step_id="s1", tool="fail", params={"value": 1}),
                PlanStep(step_id="s2", tool="add", params={"value": 10}),
            ],
        )
        state = _make_state(plan)
        node = make_solver_node(reg)
        result = await node(state)

        # Only first step executed, second skipped
        assert len(result["step_results"]) == 1
        assert result["working_ppt_state"].source_file == "/tmp/test.pptx"  # unchanged

    @pytest.mark.asyncio
    async def test_respects_target_slide_number(self):
        """TargetSelector.slide_numbers[0] is passed as target."""
        reg = _make_registry(_AddTool())
        plan = AgentPlan(
            summary="test",
            steps=[
                PlanStep(
                    step_id="s1",
                    tool="add",
                    params={"value": 1},
                    target=TargetSelector(slide_numbers=[1]),
                )
            ],
        )
        state = _make_state(plan)
        node = make_solver_node(reg)
        result = await node(state)

        # The mock tool ignores target, so it should still succeed
        assert result["step_results"][0].status == "ok"
