import pytest
from unittest.mock import patch, MagicMock

from agent_platform.orchestration.plans import AgentTrace
from models.ppt_state import PPTState, Slide, TextBox, SlideSize, Position, Size, TextStyle
from models.workflow_def import WorkflowDef, WorkflowNode, WorkflowEdge, CanvasPosition, AgentNodeConfig
from workflow.orchestrator import execute_workflow


def _agent_trace() -> AgentTrace:
    return AgentTrace(status="success")


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

    state = _make_simple_state()
    with patch("workflow.executors.parse_pptx") as mock_parse, \
         patch("workflow.executors.recompose_pptx") as mock_recompose, \
         patch("workflow.executors.run_agent_subgraph", return_value=(state, _agent_trace())) as mock_agent:

        mock_parse.return_value = state
        mock_recompose.return_value = "/tmp/output.pptx"

        result = await execute_workflow(wf, "/tmp/test.pptx")
        assert result == "/tmp/forgeppt_output__tmp_test.pptx"
        mock_parse.assert_called_once_with("/tmp/test.pptx")
        mock_recompose.assert_called_once()


@pytest.mark.asyncio
async def test_execute_single_upload_to_merge():
    """T1: single upload → merge → export (backward compat, merge has single input)."""
    wf = WorkflowDef(
        workflow_id="wf0",
        nodes=[
            WorkflowNode(id="upload", type="upload", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="merge", type="merge", position=CanvasPosition(x=0, y=0), data={}),
            WorkflowNode(id="export", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="upload", target="merge"),
            WorkflowEdge(id="e2", source="merge", target="export"),
        ],
    )

    state = _make_simple_state()
    with patch("workflow.executors.parse_pptx") as mock_parse, \
         patch("workflow.executors.recompose_pptx") as mock_recompose, \
         patch("workflow.executors.run_merge_subgraph", return_value=(state, _agent_trace())) as mock_merge:

        mock_parse.return_value = state
        mock_recompose.return_value = "/tmp/output.pptx"

        result = await execute_workflow(wf, "/tmp/test.pptx")
        assert result == "/tmp/forgeppt_output__tmp_test.pptx"
        mock_parse.assert_called_once_with("/tmp/test.pptx")
        mock_merge.assert_called_once()
        assert len(mock_merge.call_args[0][0]) == 1


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
            WorkflowNode(id="merge", type="merge", position=CanvasPosition(x=0, y=0), data={}),
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

    state = _make_simple_state()
    with patch("workflow.executors.parse_pptx") as mock_parse, \
         patch("workflow.executors.recompose_pptx") as mock_recompose, \
         patch("workflow.executors.run_agent_subgraph", return_value=(state, _agent_trace())) as mock_agent, \
         patch("workflow.executors.run_merge_subgraph", return_value=(state, _agent_trace())) as mock_merge:

        mock_parse.return_value = state
        mock_recompose.return_value = "/tmp/output.pptx"

        result = await execute_workflow(wf, "/tmp/test.pptx")
        assert result == "/tmp/forgeppt_output__tmp_test.pptx"
        assert mock_agent.call_count == 2
        mock_merge.assert_called_once()


@pytest.mark.asyncio
async def test_execute_multi_upload_merge():
    """upload1 -> agent_a -> merge -> export
       upload2 -> agent_b -> merge -> export"""
    wf = WorkflowDef(
        workflow_id="wf3",
        nodes=[
            WorkflowNode(id="upload1", type="upload", position=CanvasPosition(x=0, y=0), data={"filePath": "/tmp/main.pptx"}),
            WorkflowNode(id="upload2", type="upload", position=CanvasPosition(x=0, y=0), data={"filePath": "/tmp/extra.pptx"}),
            WorkflowNode(
                id="agent_a",
                type="agent",
                position=CanvasPosition(x=0, y=0),
                data=AgentNodeConfig(role="text_refiner", prompt="refine main").model_dump(),
            ),
            WorkflowNode(
                id="agent_b",
                type="agent",
                position=CanvasPosition(x=0, y=0),
                data=AgentNodeConfig(role="color_optimizer", prompt="dark blue extra").model_dump(),
            ),
            WorkflowNode(id="merge", type="merge", position=CanvasPosition(x=0, y=0), data={"prompt": "combine slides"}),
            WorkflowNode(id="export", type="export", position=CanvasPosition(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="upload1", target="agent_a"),
            WorkflowEdge(id="e2", source="upload2", target="agent_b"),
            WorkflowEdge(id="e3a", source="agent_a", target="merge"),
            WorkflowEdge(id="e3b", source="agent_b", target="merge"),
            WorkflowEdge(id="e4", source="merge", target="export"),
        ],
    )

    merged_state = _make_simple_state()
    with patch("workflow.executors.parse_pptx") as mock_parse, \
         patch("workflow.executors.recompose_pptx") as mock_recompose, \
         patch("workflow.executors.run_agent_subgraph", return_value=(_make_simple_state(), _agent_trace())) as mock_agent, \
         patch("workflow.executors.run_merge_subgraph", return_value=(merged_state, _agent_trace())) as mock_merge:

        state1 = _make_simple_state("main")
        state2 = _make_simple_state("extra")
        mock_parse.side_effect = [state1, state2]
        mock_recompose.return_value = "/tmp/output.pptx"

        result = await execute_workflow(wf, "/tmp/fallback.pptx")
        assert result == "/tmp/forgeppt_output__tmp_test.pptx"
        assert mock_parse.call_count == 2
        mock_parse.assert_any_call("/tmp/main.pptx")
        mock_parse.assert_any_call("/tmp/extra.pptx")
        assert mock_agent.call_count == 2
        assert mock_merge.call_count == 1
        mock_merge.assert_called_once()
        call_args = mock_merge.call_args
        assert len(call_args[0][0]) == 2  # two inputs
        assert call_args[0][1].prompt == "combine slides"
