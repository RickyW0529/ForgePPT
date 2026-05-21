"""Tests for plan models (Module 4.1)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from agent_platform.orchestration.plans import (
    AgentPlan,
    AgentTrace,
    PlanFailure,
    PlanStep,
    StepResult,
    TargetSelector,
)


class TestTargetSelector:
    def test_defaults_empty(self):
        t = TargetSelector()
        assert t.slide_numbers == []
        assert t.text_ids == []
        assert t.element_ids == []

    def test_with_values(self):
        t = TargetSelector(slide_numbers=[1, 2], text_ids=["t1"])
        assert t.slide_numbers == [1, 2]
        assert t.text_ids == ["t1"]


class TestPlanStep:
    def test_minimal(self):
        s = PlanStep(step_id="s1", tool="ppt_apply_text")
        assert s.step_id == "s1"
        assert s.tool == "ppt_apply_text"
        assert s.params == {}
        assert s.depends_on == []
        assert isinstance(s.target, TargetSelector)

    def test_with_target(self):
        s = PlanStep(
            step_id="s1",
            tool="ppt_apply_style",
            params={"font_color": "#000000"},
            target=TargetSelector(slide_numbers=[1]),
            rationale="make it dark",
            depends_on=["s0"],
        )
        assert s.target.slide_numbers == [1]
        assert s.rationale == "make it dark"
        assert s.depends_on == ["s0"]


class TestAgentPlan:
    def test_minimal(self):
        p = AgentPlan(summary="Dark theme", steps=[])
        assert p.summary == "Dark theme"
        assert p.steps == []
        assert p.plan_version == 1
        assert p.estimated_token_cost == 0

    def test_with_steps(self):
        p = AgentPlan(
            summary="Dark theme",
            steps=[
                PlanStep(step_id="s1", tool="ppt_apply_style"),
                PlanStep(step_id="s2", tool="ppt_apply_text"),
            ],
            rationale="User asked for dark mode",
            estimated_token_cost=500,
        )
        assert len(p.steps) == 2
        assert p.rationale == "User asked for dark mode"
        assert p.estimated_token_cost == 500


class TestPlanFailure:
    def test_basic(self):
        f = PlanFailure(
            iteration=1,
            failure_type="tool_unknown",
            step_index=0,
            detail="tool 'foo' not found",
        )
        assert f.iteration == 1
        assert f.failure_type == "tool_unknown"
        assert f.step_index == 0

    def test_invalid_failure_type(self):
        with pytest.raises(ValidationError):
            PlanFailure(
                iteration=1,
                failure_type="bogus",
                detail="x",
            )


class TestStepResult:
    def test_ok(self):
        r = StepResult(step_id="s1", status="ok", output={"changed": True})
        assert r.status == "ok"
        assert r.output == {"changed": True}
        assert r.error is None

    def test_error(self):
        r = StepResult(step_id="s1", status="error", error="timeout")
        assert r.status == "error"
        assert r.error == "timeout"

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            StepResult(step_id="s1", status="unknown")


class TestAgentTrace:
    def test_defaults(self):
        t = AgentTrace()
        assert t.node_id == ""
        assert t.plan is None
        assert t.step_results == []
        assert t.plan_failures == []
        assert t.status == "failed"

    def test_with_plan(self):
        plan = AgentPlan(summary="test", steps=[])
        t = AgentTrace(node_id="agent-1", plan=plan, status="success")
        assert t.node_id == "agent-1"
        assert t.plan is plan
        assert t.status == "success"
