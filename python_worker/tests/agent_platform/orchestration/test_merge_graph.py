"""Integration tests for the merge Plan-Solve subgraph (Module 5)."""

from __future__ import annotations

import copy
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agent_platform.orchestration.merge_graph import build_merge_subgraph
from agent_platform.orchestration.plans import (
    AgentTrace,
    MergePlan,
    MergeSlideRef,
    PlanFailure,
)
from agent_platform.orchestration.runner import run_merge_subgraph
from agent_platform.orchestration.state import MergeGraphState
from agent_platform.providers.models import LLMResponse, TokenUsage
from agent_platform.providers.router import ProviderRouter
from models.ppt_state import PPTState, Slide, SlideSize, TextBox, Position, Size, TextStyle
from models.workflow_def import MergeNodeConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_ppt(slide_count: int = 2) -> PPTState:
    slides: list[Slide] = []
    for i in range(1, slide_count + 1):
        slides.append(
            Slide(
                page_num=i,
                size=SlideSize(
                    width_emu=9_144_000,
                    height_emu=6_858_000,
                    width_px=960.0,
                    height_px=720.0,
                ),
                elements=[],
            )
        )
    return PPTState(
        source_file="/tmp/test.pptx",
        slide_count=slide_count,
        slides=slides,
        global_props=SlideSize(
            width_emu=9_144_000,
            height_emu=6_858_000,
            width_px=960.0,
            height_px=720.0,
        ),
    )


def _modify_slide(ppt: PPTState, page_num: int) -> PPTState:
    """Return a copy of ppt with an extra text box added to the given page."""
    import copy

    new_ppt = copy.deepcopy(ppt)
    slide = new_ppt.slides[page_num - 1]
    slide.elements.append(
        TextBox(
            content=f"modified-page-{page_num}",
            position=Position(x_emu=0, y_emu=0, x_px=0, y_px=0),
            size=Size(width_emu=1_000_000, height_emu=500_000, width_px=100, height_px=50),
            style=TextStyle(),
        )
    )
    return new_ppt


def _make_llm_response(parsed: MergePlan | None = None) -> LLMResponse:
    return LLMResponse(
        text="",
        parsed=parsed,
        tokens=TokenUsage(),
        latency_ms=100,
        provider="openai",
        model="gpt-4o-mini",
        cost_usd=0.001,
        finish_reason="stop",
    )


def _mock_router(return_plan: MergePlan | None = None) -> ProviderRouter:
    router = AsyncMock(spec=ProviderRouter)
    router.complete.return_value = _make_llm_response(return_plan)
    return router


def _make_initial_state(
    inputs: list[PPTState] | None = None,
    prompt: str = "Merge branches",
) -> MergeGraphState:
    if inputs is None:
        base = _minimal_ppt(2)
        inputs = [base, _modify_slide(base, 2)]
    return {
        "inputs": inputs,
        "config": MergeNodeConfig(prompt=prompt),
        "prompt": prompt,
        "current_plan": None,
        "plan_iteration": 0,
        "plan_failures": [],
        "step_results": [],
        "last_validation_ok": True,
        "branch_diffs": [],
        "working_ppt_state": inputs[0],
        "trace": None,
    }


# ---------------------------------------------------------------------------
# Test 1: Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_successful_merge(self):
        """Happy path: valid plan -> solver executes -> success trace."""
        base = _minimal_ppt(2)
        branch1 = _modify_slide(base, 2)

        plan = MergePlan(
            summary="keep base page 1, use branch1 page 2",
            slides=[
                MergeSlideRef(source_branch=0, source_page=1, target_page=1),
                MergeSlideRef(source_branch=1, source_page=2, target_page=2),
            ],
        )
        router = _mock_router(plan)
        graph = build_merge_subgraph(router)

        initial_state = _make_initial_state(inputs=[base, branch1])
        final_state = await graph.ainvoke(initial_state)

        trace = final_state["trace"]
        assert trace is not None
        assert trace.status == "success"
        assert len(trace.step_results) == 1
        assert trace.step_results[0].status == "ok"

        working = final_state["working_ppt_state"]
        # Page 1 should be from base (no elements)
        assert working.slides[0].elements == []
        # Page 2 should be from branch1 (has modified element)
        assert len(working.slides[1].elements) == 1
        assert working.slides[1].elements[0].content == "modified-page-2"


# ---------------------------------------------------------------------------
# Test 2: Validation failure + retry
# ---------------------------------------------------------------------------


class TestValidationFailureRetry:
    @pytest.mark.asyncio
    async def test_replan_and_succeed(self):
        """Validator rejects first plan, repair retries, second plan succeeds."""
        base = _minimal_ppt(2)
        branch1 = _modify_slide(base, 2)

        invalid_plan = MergePlan(
            summary="bad",
            slides=[
                MergeSlideRef(source_branch=99, source_page=1, target_page=1),
            ],
        )
        valid_plan = MergePlan(
            summary="good",
            slides=[
                MergeSlideRef(source_branch=0, source_page=1, target_page=1),
                MergeSlideRef(source_branch=1, source_page=2, target_page=2),
            ],
        )

        router = AsyncMock(spec=ProviderRouter)
        router.complete.side_effect = [
            _make_llm_response(invalid_plan),
            _make_llm_response(valid_plan),
        ]

        graph = build_merge_subgraph(router)
        initial_state = _make_initial_state(inputs=[base, branch1])
        final_state = await graph.ainvoke(initial_state)

        trace = final_state["trace"]
        assert trace is not None
        assert trace.status == "success"
        assert final_state["plan_iteration"] == 2
        assert len(trace.plan_failures) == 1
        assert trace.plan_failures[0].failure_type == "scope_violation"

        working = final_state["working_ppt_state"]
        assert len(working.slides[1].elements) == 1


# ---------------------------------------------------------------------------
# Test 3: Max replan exhausted
# ---------------------------------------------------------------------------


class TestMaxReplanExhausted:
    @pytest.mark.asyncio
    async def test_abort_after_max_replan(self):
        """Router always returns invalid plan; repair aborts after MAX_REPLAN."""
        base = _minimal_ppt(2)
        branch1 = _modify_slide(base, 2)

        bad_plan = MergePlan(
            summary="bad",
            slides=[
                MergeSlideRef(source_branch=0, source_page=1, target_page=1),
                MergeSlideRef(source_branch=0, source_page=1, target_page=1),
            ],
        )
        router = _mock_router(bad_plan)
        graph = build_merge_subgraph(router)

        initial_state = _make_initial_state(inputs=[base, branch1])
        final_state = await graph.ainvoke(initial_state)

        trace = final_state["trace"]
        assert trace is not None
        assert trace.status == "failed"
        assert final_state["plan_iteration"] == 2
        assert len(trace.plan_failures) == 2
        assert trace.plan_failures[0].failure_type == "conflict"


# ---------------------------------------------------------------------------
# Test 4: Runner entry point
# ---------------------------------------------------------------------------


class TestRunnerEntryPoint:
    @pytest.mark.asyncio
    async def test_run_merge_subgraph_returns_tuple(self):
        """run_merge_subgraph patches get_router and returns (PPTState, AgentTrace)."""
        base = _minimal_ppt(2)
        branch1 = _modify_slide(base, 2)
        config = MergeNodeConfig(prompt="Merge it")

        plan = MergePlan(
            summary="merge",
            slides=[
                MergeSlideRef(source_branch=0, source_page=1, target_page=1),
                MergeSlideRef(source_branch=1, source_page=2, target_page=2),
            ],
        )
        router = _mock_router(plan)

        with patch(
            "agent_platform.orchestration.runner.get_router", return_value=router
        ):
            working, trace = await run_merge_subgraph([base, branch1], config)

        assert isinstance(working, PPTState)
        assert isinstance(trace, AgentTrace)
        assert trace.status == "success"
        assert len(trace.step_results) == 1
        assert trace.step_results[0].status == "ok"
        assert len(working.slides[1].elements) == 1

    @pytest.mark.asyncio
    async def test_empty_inputs_raises(self):
        """run_merge_subgraph raises ValueError when inputs is empty."""
        config = MergeNodeConfig(prompt="Merge it")
        with pytest.raises(ValueError, match="requires at least one input"):
            await run_merge_subgraph([], config)


# ---------------------------------------------------------------------------
# Test 5: Diff pages reports extra slides
# ---------------------------------------------------------------------------


class TestDiffPages:
    def test_extra_slides_beyond_base_are_reported(self):
        """diff_pages_node reports slides in branches that exceed base length."""
        from agent_platform.orchestration.nodes.diff_pages import diff_pages_node

        base = _minimal_ppt(2)
        # Build branch from base so slide_ids match for existing slides
        branch = copy.deepcopy(base)
        branch.slides.append(
            Slide(
                page_num=3,
                size=base.slides[0].size,
                elements=[
                    TextBox(
                        content="extra-slide",
                        position=Position(x_emu=0, y_emu=0, x_px=0, y_px=0),
                        size=Size(width_emu=1_000_000, height_emu=500_000, width_px=100, height_px=50),
                        style=TextStyle(),
                    )
                ],
            )
        )
        branch.slide_count = 3

        state: MergeGraphState = {
            "inputs": [base, branch],
            "config": MergeNodeConfig(),
            "prompt": "",
            "current_plan": None,
            "plan_iteration": 0,
            "plan_failures": [],
            "step_results": [],
            "last_validation_ok": True,
            "branch_diffs": [],
            "working_ppt_state": base,
            "trace": None,
        }
        result = diff_pages_node(state)
        assert result["branch_diffs"] == [[3]]


# ---------------------------------------------------------------------------
# Test 6: Custom max_replan respected
# ---------------------------------------------------------------------------


class TestCustomMaxReplan:
    @pytest.mark.asyncio
    async def test_custom_max_replan_exhausted(self):
        """A custom max_replan of 1 aborts after a single failure."""
        base = _minimal_ppt(2)
        branch1 = _modify_slide(base, 2)

        bad_plan = MergePlan(
            summary="bad",
            slides=[
                MergeSlideRef(source_branch=0, source_page=1, target_page=1),
                MergeSlideRef(source_branch=0, source_page=1, target_page=1),
            ],
        )
        router = _mock_router(bad_plan)
        graph = build_merge_subgraph(router)

        state = _make_initial_state(inputs=[base, branch1])
        state["config"] = MergeNodeConfig(prompt="Merge", max_replan=1)

        final_state = await graph.ainvoke(state)
        trace = final_state["trace"]
        assert trace is not None
        assert trace.status == "failed"
        assert final_state["plan_iteration"] == 1


# ---------------------------------------------------------------------------
# Test 7: Markdown fence stripping
# ---------------------------------------------------------------------------


class TestMarkdownFenceStripping:
    @pytest.mark.asyncio
    async def test_merge_planner_strips_fences(self):
        """merge_planner_node strips markdown fences before JSON parsing."""
        from agent_platform.orchestration.nodes.merge_planner import make_merge_planner_node

        plan = MergePlan(summary="test", slides=[MergeSlideRef(source_branch=0, source_page=1, target_page=1)])
        fenced_text = "```json\n" + plan.model_dump_json() + "\n```"

        router = AsyncMock(spec=ProviderRouter)
        router.complete.return_value = LLMResponse(
            text=fenced_text,
            parsed=None,
            tokens=TokenUsage(),
            latency_ms=100,
            provider="openai",
            model="gpt-4o-mini",
            cost_usd=0.001,
            finish_reason="stop",
        )

        node = make_merge_planner_node(router)
        state: MergeGraphState = {
            "inputs": [_minimal_ppt(1)],
            "config": MergeNodeConfig(),
            "prompt": "",
            "current_plan": None,
            "plan_iteration": 0,
            "plan_failures": [],
            "step_results": [],
            "last_validation_ok": True,
            "branch_diffs": [],
            "working_ppt_state": _minimal_ppt(1),
            "trace": None,
        }
        result = await node(state)
        assert result["current_plan"] is not None
        assert result["current_plan"].summary == "test"


# ---------------------------------------------------------------------------
# Test 8: Merge validator uses model_copy
# ---------------------------------------------------------------------------


class TestMergeValidatorCopy:
    def test_validator_sets_iteration_via_model_copy(self):
        """merge_validator_node sets iteration without mutating original PlanFailure."""
        from agent_platform.orchestration.nodes.merge_validator import make_merge_validator_node

        base = _minimal_ppt(2)
        branch = _minimal_ppt(3)

        plan = MergePlan(
            summary="bad",
            slides=[
                MergeSlideRef(source_branch=99, source_page=1, target_page=1),
            ],
        )
        state: MergeGraphState = {
            "inputs": [base, branch],
            "config": MergeNodeConfig(),
            "prompt": "",
            "current_plan": plan,
            "plan_iteration": 3,
            "plan_failures": [],
            "step_results": [],
            "last_validation_ok": True,
            "branch_diffs": [],
            "working_ppt_state": base,
            "trace": None,
        }

        node = make_merge_validator_node()
        result = node(state)
        assert result["last_validation_ok"] is False
        assert len(result["plan_failures"]) == 1
        assert result["plan_failures"][0].iteration == 3
