import pytest
from unittest.mock import patch, MagicMock

from models.ppt_state import PPTState, Slide, TextBox, SlideSize, Position, Size, TextStyle
from models.workflow_def import WorkflowDef, WorkflowNode, WorkflowEdge, CanvasPosition, AgentNodeConfig
from workflow.orchestrator import execute_workflow


def _make_simple_state(content: str = "hello") -> PPTState:
    slide_size = SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0)
    return PPTState(
        source_file="/tmp/test.pptx",
        slide_count=1,
        global_props=slide_size,
        slides=[
            Slide(
                page_num=1,
                size=slide_size,
                elements=[
                    TextBox(
                        text_id="t1",
                        content=content,
                        position=Position(x_emu=0, y_emu=0, x_px=0, y_px=0),
                        size=Size(width_emu=1000000, height_emu=500000, width_px=100, height_px=50),
                        style=TextStyle(font_size_pt=12, font_color="#000000"),
                    )
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_execute_simple_linear_workflow():
    """upload -> agent (theme) -> export"""
    wf = WorkflowDef(
        workflow_id="wf1",
        nodes=[
            WorkflowNode(id="upload", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(
                id="agent",
                type="agent",
                position=CanvasPosition(x=0, y=0),
                data=AgentNodeConfig(role="theme_designer", prompt="make it blue").model_dump(),
            ),
            WorkflowNode(id="export", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="upload", target="agent"),
            WorkflowEdge(id="e2", source="agent", target="export"),
        ],
    )

    with patch("workflow.executors.parse_pptx") as mock_parse, \
         patch("workflow.executors.recompose_pptx") as mock_recompose, \
         patch("workflow.executors.execute_agent") as mock_agent:

        mock_parse.return_value = _make_simple_state()
        mock_recompose.return_value = "/tmp/output.pptx"
        mock_agent.return_value = _make_simple_state()

        result = await execute_workflow(wf, "/tmp/test.pptx")
        assert result == "/tmp/forgeppt_output__tmp_test.pptx"
        mock_parse.assert_called_once_with("/tmp/test.pptx")
        mock_recompose.assert_called_once()


@pytest.mark.asyncio
async def test_execute_parallel_branches():
    """upload -> allocator -> [agent_a, agent_b] -> merge -> export"""
    wf = WorkflowDef(
        workflow_id="wf2",
        nodes=[
            WorkflowNode(id="upload", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(
                id="alloc",
                type="page_allocator",
                position=CanvasPosition(x=0, y=0),
                data={"branches": {"a": [1], "b": [2]}},
            ),
            WorkflowNode(
                id="agent_a",
                type="agent",
                position=CanvasPosition(x=0, y=0),
                data=AgentNodeConfig(role="text_refiner", prompt="refine").model_dump(),
            ),
            WorkflowNode(
                id="agent_b",
                type="agent",
                position=CanvasPosition(x=0, y=0),
                data=AgentNodeConfig(role="color_optimizer", prompt="dark blue").model_dump(),
            ),
            WorkflowNode(id="merge", type="merge", position=CanvasPosition(x=0, y=0), data={"mergeStrategy": "last_write_wins"}),
            WorkflowNode(id="export", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="upload", target="alloc"),
            WorkflowEdge(id="e2a", source="alloc", target="agent_a"),
            WorkflowEdge(id="e2b", source="alloc", target="agent_b"),
            WorkflowEdge(id="e3a", source="agent_a", target="merge"),
            WorkflowEdge(id="e3b", source="agent_b", target="merge"),
            WorkflowEdge(id="e4", source="merge", target="export"),
        ],
    )

    with patch("workflow.executors.parse_pptx") as mock_parse, \
         patch("workflow.executors.recompose_pptx") as mock_recompose, \
         patch("workflow.executors.execute_agent") as mock_agent:

        state = _make_simple_state()
        mock_parse.return_value = state
        mock_recompose.return_value = "/tmp/output.pptx"
        mock_agent.return_value = state

        result = await execute_workflow(wf, "/tmp/test.pptx")
        assert result == "/tmp/forgeppt_output__tmp_test.pptx"
        assert mock_agent.call_count == 2
