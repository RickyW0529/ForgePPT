"""Tests for AgentGraphState TypedDict (Module 4.1)."""

from __future__ import annotations

from agent_platform.context.builders import PlannerContext
from agent_platform.orchestration.plans import AgentPlan, AgentTrace, PlanFailure, StepResult
from agent_platform.orchestration.state import AgentGraphState, _add
from models.ppt_state import PPTState, Slide, SlideSize
from models.workflow_def import AgentNodeConfig


def test_add_reducer():
    assert _add([1, 2], [3, 4]) == [1, 2, 3, 4]
    assert _add([], ["a"]) == ["a"]


def test_state_can_be_constructed():
    """TypedDict can be instantiated like a regular dict."""
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
    config = AgentNodeConfig(role="editor", prompt="test")
    planner_ctx = PlannerContext(
        deck_meta={"slide_count": 1},
        slides_in_scope=[],
        available_tools=[],
        role_system_prompt="editor",
        user_prompt="test",
        memory_snippets=[],
        previous_attempts=[],
        constraints=[],
    )

    state: AgentGraphState = {
        "initial_ppt_state": ppt,
        "config": config,
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

    assert state["initial_ppt_state"] is ppt
    assert state["config"].role == "editor"
    assert state["plan_iteration"] == 0
    assert state["last_validation_ok"] is True
