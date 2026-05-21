"""Tests for plan repair node (Module 4.4)."""

from __future__ import annotations

from agent_platform.orchestration.nodes.repair import MAX_REPLAN, repair_node, route_repair
from agent_platform.orchestration.plans import AgentPlan, AgentTrace, PlanFailure
from agent_platform.orchestration.state import AgentGraphState
from models.ppt_state import PPTState, Slide, SlideSize
from models.workflow_def import AgentNodeConfig


def _minimal_state(
    plan_iteration: int = 0,
    plan_failures: list | None = None,
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
        "plan_iteration": plan_iteration,
        "plan_failures": plan_failures or [],
        "step_results": [],
        "last_validation_ok": False,
        "working_ppt_state": ppt,
        "trace": trace,
    }


class TestRepairNode:
    def test_allows_retry_when_under_budget(self):
        state = _minimal_state(plan_iteration=1)
        result = repair_node(state)
        assert "trace" not in result

    def test_aborts_when_max_replan_reached(self):
        failures = [
            PlanFailure(iteration=2, failure_type="tool_unknown", detail="missing")
        ]
        plan = AgentPlan(summary="test", steps=[])
        state = _minimal_state(plan_iteration=MAX_REPLAN, plan_failures=failures, current_plan=plan)
        result = repair_node(state)
        assert "trace" in result
        trace = result["trace"]
        assert isinstance(trace, AgentTrace)
        assert trace.status == "failed"
        assert trace.plan is plan
        assert trace.plan_failures == failures

    def test_aborts_when_over_budget(self):
        state = _minimal_state(plan_iteration=MAX_REPLAN + 1)
        result = repair_node(state)
        assert "trace" in result
        assert result["trace"].status == "failed"


class TestRouteRepair:
    def test_routes_to_assemble_when_trace_present(self):
        state = _minimal_state(trace=AgentTrace())
        assert route_repair(state) == "assemble"

    def test_routes_to_planner_when_no_trace(self):
        state = _minimal_state()
        assert route_repair(state) == "planner"
