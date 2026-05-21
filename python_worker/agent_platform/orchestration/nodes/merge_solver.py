"""Merge solver node — executes a MergePlan to build a merged PPTState.

MVP Boundary: The solver only supports in-place slide replacement.
It cannot add, remove, or reorder slides to new positions beyond the
base deck length. The validator enforces ``target_page <= len(base.slides)``.
"""

from __future__ import annotations

import copy
from typing import Any

from agent_platform.orchestration.plans import MergePlan, StepResult
from agent_platform.orchestration.state import MergeGraphState
from models.ppt_state import PPTState


def make_merge_solver_node():
    """Return a LangGraph node that executes ``state["current_plan"]``."""

    def merge_solver_node(state: MergeGraphState) -> dict[str, Any]:
        plan: MergePlan | None = state.get("current_plan")
        if plan is None:
            return {
                "step_results": [],
                "working_ppt_state": state["working_ppt_state"],
            }

        inputs = state["inputs"]
        merged = copy.deepcopy(inputs[0])

        for ref in plan.slides:
            source_slide = copy.deepcopy(inputs[ref.source_branch].slides[ref.source_page - 1])
            merged.slides[ref.target_page - 1] = source_slide

        # Re-validate slide_count consistency after mutation
        merged = PPTState.model_validate(merged.model_dump())

        return {
            "working_ppt_state": merged,
            "step_results": [
                StepResult(
                    step_id="merge",
                    status="ok",
                )
            ],
        }

    return merge_solver_node
