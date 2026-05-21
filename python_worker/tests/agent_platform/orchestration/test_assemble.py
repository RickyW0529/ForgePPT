"""Tests for assemble node (Module 4.7)."""

from __future__ import annotations

from agent_platform.orchestration.nodes.assemble import assemble_node
from agent_platform.orchestration.plans import AgentPlan, AgentTrace, PlanFailure, StepResult
from agent_platform.orchestration.state import AgentGraphState
from models.ppt_state import PPTState, Slide, SlideSize
from models.workflow_def import AgentNodeConfig


def _make_state(
    step_results: list[StepResult] | None = None,
    plan_failures: list[PlanFailure] | None = None,
    current_plan: AgentPlan | None = None,
    trace: AgentTrace | None = None,
) -> AgentGraphState:
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
    return {
        "initial_ppt_state": ppt,
        "config": AgentNodeConfig(role="editor"),
        "role": "editor",
        "allowed_pages": [1],
        "planner_context": {},  # type: ignore[typeddict-item]
        "current_plan": current_plan,
        "plan_iteration": 0,
        "plan_failures": plan_failures or [],
        "step_results": step_results or [],
        "last_validation_ok": True,
        "working_ppt_state": ppt,
        "trace": trace,
    }


class TestAssembleNode:
    def test_success_when_all_ok(self):
        state = _make_state(
            step_results=[
                StepResult(step_id="s1", status="ok"),
                StepResult(step_id="s2", status="ok"),
            ]
        )
        result = assemble_node(state)
        assert result["trace"].status == "success"
        assert result["trace"].node_id == "editor"

    def test_partial_when_some_failed(self):
        state = _make_state(
            step_results=[
                StepResult(step_id="s1", status="ok"),
                StepResult(step_id="s2", status="error", error="boom"),
            ]
        )
        result = assemble_node(state)
        assert result["trace"].status == "partial"

    def test_preserves_abort_trace(self):
        abort_trace = AgentTrace(status="failed", node_id="editor")
        state = _make_state(trace=abort_trace)
        result = assemble_node(state)
        assert result == {}

    def test_includes_plan_and_failures(self):
        plan = AgentPlan(summary="test", steps=[])
        failures = [PlanFailure(iteration=1, failure_type="tool_unknown", detail="x")]
        state = _make_state(current_plan=plan, plan_failures=failures)
        result = assemble_node(state)
        assert result["trace"].plan is plan
        assert result["trace"].plan_failures == failures
