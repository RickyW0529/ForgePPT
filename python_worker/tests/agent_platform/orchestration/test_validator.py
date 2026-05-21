"""Tests for plan validator node (Module 4.3)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from agent_platform.orchestration.nodes.validator import validate_plan
from agent_platform.orchestration.plans import AgentPlan, PlanStep, TargetSelector
from agent_platform.tools.descriptor import Capability, ToolDescriptor
from agent_platform.tools.registry import ToolRegistry


class _In(BaseModel):
    v: int


class _Out(BaseModel):
    r: str


class _FakeTool:
    def __init__(self, name: str):
        self.descriptor = ToolDescriptor(
            name=name,
            description=f"tool {name}",
            input_schema=_In,
            output_schema=_Out,
            capabilities=[Capability.READ_TEXT],
        )


def _registry_with_tools(*names: str) -> ToolRegistry:
    reg = ToolRegistry()
    for name in names:
        reg.register(_FakeTool(name))
    return reg


def _plan_with_steps(*tools: str) -> AgentPlan:
    return AgentPlan(
        summary="test",
        steps=[
            PlanStep(step_id=f"s{i}", tool=t, params={"v": 1})
            for i, t in enumerate(tools)
        ],
    )


class TestValidatePlan:
    def test_empty_plan_is_ok(self):
        plan = AgentPlan(summary="empty", steps=[])
        ok, failures = validate_plan(plan, _registry_with_tools())
        assert ok is True
        assert failures == []

    def test_valid_plan(self):
        plan = _plan_with_steps("tool_a")
        ok, failures = validate_plan(plan, _registry_with_tools("tool_a"))
        assert ok is True
        assert failures == []

    def test_unknown_tool(self):
        plan = _plan_with_steps("missing")
        ok, failures = validate_plan(plan, _registry_with_tools("tool_a"))
        assert ok is False
        assert len(failures) == 1
        assert failures[0].failure_type == "tool_unknown"
        assert "missing" in failures[0].detail

    def test_invalid_params(self):
        plan = AgentPlan(
            summary="test",
            steps=[
                PlanStep(
                    step_id="s1",
                    tool="tool_a",
                    params={"v": "not_an_int"},
                )
            ],
        )
        ok, failures = validate_plan(plan, _registry_with_tools("tool_a"))
        assert ok is False
        assert len(failures) == 1
        assert failures[0].failure_type == "param_invalid"
        assert "s1" in failures[0].detail or "input" in failures[0].detail.lower()

    def test_scope_violation(self):
        plan = AgentPlan(
            summary="test",
            steps=[
                PlanStep(
                    step_id="s1",
                    tool="tool_a",
                    params={"v": 1},
                    target=TargetSelector(slide_numbers=[3, 4]),
                )
            ],
        )
        ok, failures = validate_plan(
            plan, _registry_with_tools("tool_a"), allowed_pages=[1, 2]
        )
        assert ok is False
        assert len(failures) == 1
        assert failures[0].failure_type == "scope_violation"
        assert "3" in failures[0].detail

    def test_scope_allowed_when_empty(self):
        """If allowed_pages is empty, any slide number is permitted."""
        plan = AgentPlan(
            summary="test",
            steps=[
                PlanStep(
                    step_id="s1",
                    tool="tool_a",
                    params={"v": 1},
                    target=TargetSelector(slide_numbers=[99]),
                )
            ],
        )
        ok, failures = validate_plan(
            plan, _registry_with_tools("tool_a"), allowed_pages=[]
        )
        assert ok is True
        assert failures == []

    def test_dependency_missing(self):
        plan = AgentPlan(
            summary="test",
            steps=[
                PlanStep(
                    step_id="s1",
                    tool="tool_a",
                    params={"v": 1},
                    depends_on=["s0"],
                )
            ],
        )
        ok, failures = validate_plan(plan, _registry_with_tools("tool_a"))
        assert ok is False
        assert len(failures) == 1
        assert failures[0].failure_type == "dependency_invalid"
        assert "s0" in failures[0].detail

    def test_dependency_cycle(self):
        plan = AgentPlan(
            summary="test",
            steps=[
                PlanStep(
                    step_id="s1",
                    tool="tool_a",
                    params={"v": 1},
                    depends_on=["s2"],
                ),
                PlanStep(
                    step_id="s2",
                    tool="tool_a",
                    params={"v": 1},
                    depends_on=["s1"],
                ),
            ],
        )
        ok, failures = validate_plan(plan, _registry_with_tools("tool_a"))
        assert ok is False
        assert any(f.failure_type == "dependency_invalid" for f in failures)

    def test_multiple_failures_reported(self):
        plan = AgentPlan(
            summary="test",
            steps=[
                PlanStep(step_id="s1", tool="missing_a", params={}),
                PlanStep(step_id="s2", tool="missing_b", params={}),
            ],
        )
        ok, failures = validate_plan(plan, _registry_with_tools())
        assert ok is False
        assert len(failures) == 2

    def test_step_index_set(self):
        plan = _plan_with_steps("missing")
        ok, failures = validate_plan(plan, _registry_with_tools())
        assert failures[0].step_index == 0
