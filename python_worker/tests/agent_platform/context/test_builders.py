"""Tests for context builders (Module 3.2)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from agent_platform.providers.models import ChatMessage
from agent_platform.tools.descriptor import Capability, ToolDescriptor
from agent_platform.tools.registry import ToolRegistry
from models.ppt_state import (
    Image,
    Position,
    PPTState,
    Size,
    Slide,
    SlideSize,
    TextBox,
    TextStyle,
)
from agent_platform.context.builders import (
    FailureFeedback,
    PlannerContext,
    build_failure_feedback,
    build_planner_context,
    build_text_refine_context,
)
from agent_platform.context.digests import StateDiffDigest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _In(BaseModel):
    v: int


class _Out(BaseModel):
    r: str


class _FakeTool:
    def __init__(
        self,
        name: str,
        capabilities: list[Capability] | None = None,
        roles: list[str] | None = None,
    ):
        self.descriptor = ToolDescriptor(
            name=name,
            description=f"tool {name}",
            input_schema=_In,
            output_schema=_Out,
            capabilities=capabilities or [],
            required_role_grants=roles or ["editor"],
        )


def _minimal_ppt_state() -> PPTState:
    return PPTState(
        source_file="test.pptx",
        slide_count=2,
        slides=[
            Slide(
                page_num=1,
                size=SlideSize(
                    width_emu=9_144_000,
                    height_emu=6_858_000,
                    width_px=960.0,
                    height_px=720.0,
                ),
                elements=[
                    TextBox(
                        text_id="t1",
                        content="Hello World",
                        position=Position(
                            x_emu=0, y_emu=0, x_px=0.0, y_px=0.0
                        ),
                        size=Size(
                            width_emu=1_000_000,
                            height_emu=1_000_000,
                            width_px=100.0,
                            height_px=100.0,
                        ),
                        style=TextStyle(font_color="#000000"),
                    )
                ],
            ),
            Slide(
                page_num=2,
                size=SlideSize(
                    width_emu=9_144_000,
                    height_emu=6_858_000,
                    width_px=960.0,
                    height_px=720.0,
                ),
                elements=[
                    TextBox(
                        text_id="t2",
                        content="Second slide",
                        position=Position(
                            x_emu=0, y_emu=0, x_px=0.0, y_px=0.0
                        ),
                        size=Size(
                            width_emu=1_000_000,
                            height_emu=1_000_000,
                            width_px=100.0,
                            height_px=100.0,
                        ),
                        style=TextStyle(font_color="#FF0000"),
                    )
                ],
            ),
        ],
        global_props=SlideSize(
            width_emu=9_144_000,
            height_emu=6_858_000,
            width_px=960.0,
            height_px=720.0,
        ),
    )


# ---------------------------------------------------------------------------
# PlannerContext
# ---------------------------------------------------------------------------


class TestBuildPlannerContext:
    def test_builds_with_all_slides(self):
        state = _minimal_ppt_state()
        registry = ToolRegistry()
        registry.register(_FakeTool("tool_a", roles=["editor"]))

        ctx = build_planner_context(
            state=state,
            scope=[1, 2],
            role="editor",
            prompt="Make it better",
            tool_registry=registry,
        )

        assert isinstance(ctx, PlannerContext)
        assert ctx.deck_meta["source_file"] == "test.pptx"
        assert ctx.deck_meta["slide_count"] == 2
        assert len(ctx.slides_in_scope) == 2
        assert ctx.slides_in_scope[0].page_num == 1
        assert ctx.slides_in_scope[1].page_num == 2
        assert len(ctx.available_tools) == 1
        assert ctx.available_tools[0].name == "tool_a"
        assert ctx.role_system_prompt == "editor"
        assert ctx.user_prompt == "Make it better"
        assert ctx.memory_snippets == []
        assert ctx.previous_attempts == []
        assert ctx.constraints == []

    def test_respects_scope(self):
        state = _minimal_ppt_state()
        registry = ToolRegistry()

        ctx = build_planner_context(
            state=state,
            scope=[1],
            role="editor",
            prompt="Fix slide 1",
            tool_registry=registry,
        )

        assert len(ctx.slides_in_scope) == 1
        assert ctx.slides_in_scope[0].page_num == 1

    def test_with_memories_and_attempts(self):
        state = _minimal_ppt_state()
        registry = ToolRegistry()

        ctx = build_planner_context(
            state=state,
            scope=[1, 2],
            role="editor",
            prompt="Test",
            tool_registry=registry,
            memories=["memory1", "memory2"],
            attempts=["attempt1"],
        )

        assert ctx.memory_snippets == ["memory1", "memory2"]
        assert ctx.previous_attempts == ["attempt1"]

    def test_budget_allocation(self):
        state = _minimal_ppt_state()
        registry = ToolRegistry()

        ctx = build_planner_context(
            state=state,
            scope=[1, 2],
            role="editor",
            prompt="Test",
            tool_registry=registry,
        )

        # With scope_size=2, per_slide = max(15, 1100//2) = 550,
        # sample_chars = min(60, 1650) = 60
        assert ctx.slides_in_scope[0].sample_text == "Hello World"
        assert ctx.slides_in_scope[1].sample_text == "Second slide"

    def test_empty_registry(self):
        state = _minimal_ppt_state()
        registry = ToolRegistry()

        ctx = build_planner_context(
            state=state,
            scope=[1, 2],
            role="editor",
            prompt="Test",
            tool_registry=registry,
        )

        assert ctx.available_tools == []


# ---------------------------------------------------------------------------
# Text refine context
# ---------------------------------------------------------------------------


class TestBuildTextRefineContext:
    def test_basic(self):
        messages = build_text_refine_context(
            original="Original text",
            instruction="Make it shorter",
        )
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert "PPT text refinement assistant" in messages[0].content
        assert messages[1].role == "user"
        assert "Original text" in messages[1].content
        assert "Make it shorter" in messages[1].content

    def test_with_style_hint(self):
        messages = build_text_refine_context(
            original="Original text",
            instruction="Make it shorter",
            style_hint="professional",
        )
        assert len(messages) == 2
        assert messages[1].role == "user"
        assert "professional" in messages[1].content


# ---------------------------------------------------------------------------
# Failure feedback
# ---------------------------------------------------------------------------


class TestBuildFailureFeedback:
    def test_empty_failures(self):
        feedback = build_failure_feedback(
            plan={"steps": []},
            failures=[],
        )
        assert isinstance(feedback, FailureFeedback)
        assert feedback.previous_plan_summary == {"steps": []}
        assert feedback.failures == []
        assert feedback.state_diff is None

    def test_few_failures_no_truncation(self):
        failures = ["f1", "f2", "f3"]
        feedback = build_failure_feedback(
            plan={"steps": []},
            failures=failures,
        )
        assert feedback.failures == ["f1", "f2", "f3"]

    def test_many_failures_truncated(self):
        failures = ["f1", "f2", "f3", "f4", "f5", "f6", "f7"]
        feedback = build_failure_feedback(
            plan={"steps": []},
            failures=failures,
        )
        assert feedback.failures == ["f1", "f2", "f3", "...", "f6", "f7"]
        assert len(feedback.failures) == 6

    def test_with_diff(self):
        diff = StateDiffDigest(
            pages_changed=[1],
            text_ids_changed=["t1"],
            style_summary=0,
            elements_added=0,
            elements_removed=0,
        )
        feedback = build_failure_feedback(
            plan={"steps": []},
            failures=["f1"],
            diff=diff,
        )
        assert feedback.state_diff == diff
