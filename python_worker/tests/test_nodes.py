from unittest.mock import MagicMock, patch

import pytest
from models.ppt_state import PPTState, Slide, SlideSize, TextBox, Position, Size, TextStyle
from models.workflow import EditRequest, EditResult, GraphState, RefinerOutput, ThemeOutput
from workflow.nodes import text_refiner_node, editor_node


def test_text_refiner_node_returns_edit_result():
    """text_refiner_node should return an EditResult with new content."""
    # Build a minimal state
    from models.ppt_state import PPTState, Slide, SlideSize, TextBox, Position, Size, TextStyle

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

    # Mock the LLM structured output
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = RefinerOutput(refined_text="Short", change_summary="Cut words")
    mock_llm.with_structured_output.return_value = mock_structured

    with patch("workflow.nodes.get_llm_client", return_value=mock_llm):
        result = text_refiner_node(state, request)

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

    with patch("workflow.nodes.get_llm_client") as mock_get_llm:
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = ThemeOutput(
            color_palette=["#0000FF"],
            font_size_multiplier=1.0,
            make_bold=False,
            change_summary="ok",
        )
        mock_llm.with_structured_output.return_value = mock_structured
        mock_llm.bind_tools.return_value = mock_llm
        mock_get_llm.return_value = mock_llm

        result = editor_node(state)

    assert result["edit_results"][0].status == "completed"
    assert result["edit_results"][0].new_content == "ok"
    # Verify bind_tools was called because tools are built from the registry
    mock_llm.bind_tools.assert_called_once()
