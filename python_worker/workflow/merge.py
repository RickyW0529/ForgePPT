import copy
from typing import Literal

from models.ppt_state import PPTState


def detect_modified_pages(base: PPTState, modified: PPTState) -> list[int]:
    """Return list of 1-based page numbers that differ between base and modified."""
    changed = []
    for i, (base_slide, mod_slide) in enumerate(zip(base.slides, modified.slides)):
        if base_slide.model_dump_json() != mod_slide.model_dump_json():
            changed.append(i + 1)
    return changed


def merge_states(
    inputs: list[PPTState],
    strategy: Literal["last_write_wins", "error_on_conflict"] = "last_write_wins",
) -> PPTState:
    """Merge multiple branch outputs into a single PPTState.

    Args:
        inputs: List of PPTStates from upstream branches. The first is the base.
        strategy: How to handle overlapping page modifications.

    Returns:
        Merged PPTState.
    """
    if not inputs:
        raise ValueError("No inputs to merge")

    base = copy.deepcopy(inputs[0])
    base_modified = {p: False for p in range(1, len(base.slides) + 1)}

    for branch_state in inputs[1:]:
        modified_pages = detect_modified_pages(inputs[0], branch_state)
        for page_num in modified_pages:
            if strategy == "error_on_conflict" and base_modified[page_num]:
                raise ValueError(
                    f"Merge conflict: page {page_num} modified by multiple branches"
                )
            base.slides[page_num - 1] = copy.deepcopy(branch_state.slides[page_num - 1])
            base_modified[page_num] = True

    return base
