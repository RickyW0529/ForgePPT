from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel
from models.ppt_state import PPTState, Slide, SlideSize, TextBox, Position, Size, TextStyle
from models.workflow import EditRequest, EditResult, GraphState, RefinerOutput
from llm.tools.registry import ToolRegistry, llm_tool
from llm.tools.ppt_apply_style import PPTApplyStyleInput, apply_style_to_ppt_state
from workflow.nodes import text_refiner_node, editor_node


class MockToolCallResponse:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


@pytest.fixture(autouse=True)
def reset_registry():
    ToolRegistry().clear()
    yield


def make_ppt_state_with_three_slides() -> PPTState:
    slide_size = SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0)
    slides = []
    for page_num in range(1, 4):
        slides.append(
            Slide(
                page_num=page_num,
                size=slide_size,
                elements=[
                    TextBox(
                        content=f"Slide {page_num} title",
                        position=Position(x_emu=0, y_emu=0, x_px=0.0, y_px=0.0),
                        size=Size(width_emu=1000000, height_emu=500000, width_px=100.0, height_px=50.0),
                        style=TextStyle(font_size_pt=20.0),
                    )
                ],
            )
        )
    return PPTState(
        source_file="test.pptx",
        slide_count=3,
        global_props=slide_size,
        slides=slides,
    )


def test_theme_refiner_node_executes_ai_tool_call_for_slide_color():
    from workflow.nodes import theme_refiner_node

    ppt_state = make_ppt_state_with_three_slides()
    state = GraphState.create(ppt_state=ppt_state)
    request = EditRequest(type="theme", prompt="把第三页整体颜色改成蓝色")

    mock_llm = MagicMock()
    bound_llm = MagicMock()
    bound_llm.invoke.return_value = MockToolCallResponse(
        [
            {
                "name": "ppt_apply_style",
                "args": {
                    "slide_number": 3,
                    "target": "all_text",
                    "font_color": "#0000FF",
                    "font_size_multiplier": None,
                    "bold": None,
                },
            }
        ]
    )
    mock_llm.bind_tools.return_value = bound_llm

    result = theme_refiner_node(state, request, mock_llm)

    assert result["edit_results"][0].status == "completed"
    assert result["ppt_state"].slides[0].elements[0].style.font_color is None
    assert result["ppt_state"].slides[1].elements[0].style.font_color is None
    assert result["ppt_state"].slides[2].elements[0].style.font_color == "#0000FF"
    mock_llm.bind_tools.assert_called_once()


def test_theme_refiner_node_fails_when_ai_does_not_call_tool():
    from workflow.nodes import theme_refiner_node

    ppt_state = make_ppt_state_with_three_slides()
    state = GraphState.create(ppt_state=ppt_state)
    request = EditRequest(type="theme", prompt="把第三页整体颜色改成蓝色")

    mock_llm = MagicMock()
    bound_llm = MagicMock()
    bound_llm.invoke.return_value = MockToolCallResponse([])
    mock_llm.bind_tools.return_value = bound_llm

    result = theme_refiner_node(state, request, mock_llm)

    assert result["edit_results"][0].status == "failed"
    assert "did not call" in result["edit_results"][0].error

def test_text_refiner_node_returns_edit_result():
    """text_refiner_node should return an EditResult with new content."""
    ppt_state = PPTState(
        source_file="test.pptx",
        slide_count=1,
        global_props=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
        slides=[
            Slide(
                page_num=1,
                size=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
                elements=[
                    TextBox(
                        content="Original text",
                        position=Position(x_emu=0, y_emu=0, x_px=0.0, y_px=0.0),
                        size=Size(width_emu=1000000, height_emu=500000, width_px=100.0, height_px=50.0),
                        style=TextStyle(),
                    )
                ],
            )
        ],
    )
    state = {
        "ppt_state": ppt_state,
        "edit_requests": [],
        "edit_results": [],
        "export_path": None,
        "error": None,
    }
    request = EditRequest(type="refine", text_id=ppt_state.slides[0].elements[0].text_id, prompt="Make it shorter")

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = RefinerOutput(refined_text="Short", change_summary="Cut words")
    mock_llm.with_structured_output.return_value = mock_structured

    result = text_refiner_node(state, request, mock_llm)

    assert "edit_results" in result
    assert len(result["edit_results"]) == 1
    assert result["edit_results"][0].new_content == "Short"


def test_editor_node_binds_tools_when_requests_present():
    """editor_node should route theme requests and bind tools to the LLM."""
    ppt_state = PPTState(
        source_file="/tmp/test.pptx",
        slide_count=1,
        global_props=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
        slides=[
            Slide(
                page_num=1,
                size=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
                elements=[
                    TextBox(
                        content="Sample text",
                        position=Position(x_emu=0, y_emu=0, x_px=0.0, y_px=0.0),
                        size=Size(width_emu=1000000, height_emu=500000, width_px=100.0, height_px=50.0),
                        style=TextStyle(),
                    )
                ],
            )
        ],
    )
    state = GraphState.create(
        ppt_state=ppt_state,
        edit_requests=[{"type": "theme", "prompt": "blue style"}],
    )

    class MockToolInput(BaseModel):
        query: str

    @llm_tool(name="mock_editor_tool", roles=["editor"], description="Mock editor tool")
    def mock_editor_tool(params: MockToolInput) -> str:
        return f"result for {params.query}"

    with patch("workflow.nodes.get_llm_client") as mock_get_llm:
        mock_llm = MagicMock()
        bound_llm = MagicMock()
        bound_llm.invoke.return_value = MockToolCallResponse(
            [
                {
                    "name": "ppt_apply_style",
                    "args": {
                        "slide_number": None,
                        "target": "all_text",
                        "font_color": "#0000FF",
                        "font_size_multiplier": None,
                        "bold": None,
                    },
                }
            ]
        )
        mock_llm.bind_tools.return_value = bound_llm
        mock_get_llm.return_value = mock_llm

        result = editor_node(state)

    assert result["edit_results"][0].status == "completed"
    assert "ppt_apply_style updated" in result["edit_results"][0].new_content
    mock_llm.bind_tools.assert_called_once()


def test_editor_node_handles_unknown_request_type():
    state = GraphState.create(
        ppt_state={"slides": [], "slide_count": 0, "global_props": {}, "source_file": "/tmp/test.pptx"},
        edit_requests=[{"type": "unknown", "prompt": "do something"}],
    )
    with patch("workflow.nodes.get_llm_client") as mock_get_llm:
        mock_get_llm.return_value = MagicMock()
        result = editor_node(state)
    assert result["edit_results"][0].status == "failed"


def test_apply_style_to_ppt_state_updates_requested_slide_only():
    ppt_state = make_ppt_state_with_three_slides()
    result = apply_style_to_ppt_state(
        ppt_state,
        PPTApplyStyleInput(
            slide_number=3,
            target="all_text",
            font_color="#0000FF",
            font_size_multiplier=None,
            bold=None,
        ),
    )

    assert result["updated_textboxes"] == 1
    assert ppt_state.slides[0].elements[0].style.font_color is None
    assert ppt_state.slides[1].elements[0].style.font_color is None
    assert ppt_state.slides[2].elements[0].style.font_color == "#0000FF"


def test_apply_style_to_ppt_state_rejects_slide_out_of_range():
    ppt_state = make_ppt_state_with_three_slides()

    with pytest.raises(ValueError, match="slide_number 4 is outside valid range"):
        apply_style_to_ppt_state(
            ppt_state,
            PPTApplyStyleInput(
                slide_number=4,
                target="all_text",
                font_color="#0000FF",
                font_size_multiplier=None,
                bold=None,
            ),
        )
