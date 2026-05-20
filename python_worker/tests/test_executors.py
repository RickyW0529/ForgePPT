from unittest.mock import patch

import pytest
from models.ppt_state import PPTState, Slide, SlideSize
from models.workflow_def import MergeNodeConfig
from workflow.executors import run_merge_node


def _make_ppt(slide_count: int, source_file: str = "/tmp/test.pptx") -> PPTState:
    """Helper to create a PPTState with a given number of empty slides."""
    size = SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0)
    slides = [
        Slide(
            page_num=i,
            size=size,
            elements=[],
        )
        for i in range(1, slide_count + 1)
    ]
    return PPTState(
        source_file=source_file,
        slide_count=slide_count,
        global_props=size,
        slides=slides,
    )


def test_run_merge_node_calls_execute_merge_with_config():
    ppt1 = _make_ppt(1)
    ppt2 = _make_ppt(1)
    config = MergeNodeConfig(merge_strategy="ai_composer", prompt="Merge these slides")
    mocked_result = _make_ppt(2)

    with (
        patch("workflow.executors.broadcast_sse") as mock_broadcast,
        patch("workflow.executors.execute_merge", return_value=mocked_result) as mock_execute_merge,
    ):
        # Access .fn to bypass Prefect task runtime
        result = run_merge_node.fn("merge-1", [ppt1, ppt2], config)

    assert result == mocked_result
    mock_execute_merge.assert_called_once_with([ppt1, ppt2], config)
    mock_broadcast.assert_any_call("merge-1", "started")
    mock_broadcast.assert_any_call("merge-1", "completed")
