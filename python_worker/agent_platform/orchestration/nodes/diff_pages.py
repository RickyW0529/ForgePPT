"""Diff pages node — detects modified pages across upstream branches."""

from __future__ import annotations

from typing import Any

from agent_platform.orchestration.state import MergeGraphState
from workflow.merge import detect_modified_pages


def diff_pages_node(state: MergeGraphState) -> dict[str, Any]:
    """For each branch (index 1..N-1), compute diff against base (index 0).

    Also reports extra slides in branches that exceed the base deck length,
    so the planner has full visibility into all available slides.
    """
    inputs = state["inputs"]
    base = inputs[0]
    branch_diffs: list[list[int]] = []
    for i in range(1, len(inputs)):
        modified = detect_modified_pages(base, inputs[i])
        # Report extra slides beyond base length so planner can select them
        for extra_page in range(len(base.slides) + 1, len(inputs[i].slides) + 1):
            modified.append(extra_page)
        branch_diffs.append(modified)
    return {"branch_diffs": branch_diffs}
