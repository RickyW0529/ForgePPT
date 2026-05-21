"""Diff pages node — detects modified pages across upstream branches."""

from __future__ import annotations

from typing import Any

from agent_platform.orchestration.state import MergeGraphState
from workflow.merge import detect_modified_pages


def diff_pages_node(state: MergeGraphState) -> dict[str, Any]:
    """For each branch (index 1..N-1), compute diff against base (index 0)."""
    inputs = state["inputs"]
    branch_diffs: list[list[int]] = []
    for i in range(1, len(inputs)):
        modified = detect_modified_pages(inputs[0], inputs[i])
        branch_diffs.append(modified)
    return {"branch_diffs": branch_diffs}
