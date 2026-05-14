import pytest
from models.workflow import (
    EditRequest,
    EditResult,
    GraphState,
    RefinerOutput,
    SVGOutput,
)


def test_edit_request_creation():
    """EditRequest should accept type, text_id, and prompt."""
    req = EditRequest(type="refine", text_id="t1", prompt="Make it shorter")
    assert req.type == "refine"
    assert req.text_id == "t1"
    assert req.prompt == "Make it shorter"


def test_refiner_output():
    """RefinerOutput should validate refined_text and change_summary."""
    out = RefinerOutput(refined_text="Short text", change_summary="Removed filler")
    assert out.refined_text == "Short text"


def test_svg_output():
    """SVGOutput should validate svg_xml."""
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    out = SVGOutput(svg_xml=svg, description="A rectangle")
    assert out.svg_xml == svg


def test_graph_state_serialization():
    """GraphState should serialize to dict."""
    state = GraphState(
        edit_requests=[EditRequest(type="refine", text_id="t1", prompt="test")],
    )
    assert len(state["edit_requests"]) == 1
