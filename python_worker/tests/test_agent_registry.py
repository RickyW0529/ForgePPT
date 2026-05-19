from unittest.mock import MagicMock, patch

import pytest
from models.ppt_state import PPTState, Slide, SlideSize, TextBox, Position, Size, TextStyle
from models.workflow_def import AgentNodeConfig
from workflow.agent_registry import AGENT_ROLES, _build_tools, execute_agent, AgentRole


class MockToolCallResponse:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


def test_agent_roles_defined():
    assert "text_refiner" in AGENT_ROLES
    assert "color_optimizer" in AGENT_ROLES
    assert "layout_designer" in AGENT_ROLES
    assert "svg_generator" in AGENT_ROLES
    assert "theme_designer" in AGENT_ROLES


def test_agent_role_has_prompt():
    role = AGENT_ROLES["text_refiner"]
    assert "text" in role.system_prompt.lower()
    assert len(role.available_tools) >= 1


def test_execute_agent_unknown_role():
    state = PPTState(
        source_file="/tmp/test.pptx",
        slide_count=1,
        global_props=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
        slides=[
            Slide(
                page_num=1,
                size=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
                elements=[],
            )
        ],
    )
    config = AgentNodeConfig(role="nonexistent")
    with pytest.raises(ValueError, match="Unknown agent role"):
        execute_agent(state, config)


def test_build_tools_returns_correct_tools_for_theme_designer():
    role = AGENT_ROLES["theme_designer"]
    tools = _build_tools(role)
    assert len(tools) == 1
    assert tools[0].name == "ppt_apply_style"


def test_build_tools_raises_for_unknown_tool():
    role = AgentRole(
        key="unknown",
        system_prompt="test",
        available_tools=["nonexistent_tool"],
    )
    with pytest.raises(ValueError, match="Unknown tool: nonexistent_tool"):
        _build_tools(role)


def test_execute_agent_with_theme_designer_and_mocked_llm():
    state = PPTState(
        source_file="/tmp/test.pptx",
        slide_count=1,
        global_props=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
        slides=[
            Slide(
                page_num=1,
                size=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
                elements=[
                    TextBox(
                        content="Hello",
                        position=Position(x_emu=0, y_emu=0, x_px=0.0, y_px=0.0),
                        size=Size(width_emu=1000000, height_emu=500000, width_px=100.0, height_px=50.0),
                        style=TextStyle(),
                    )
                ],
            )
        ],
    )
    config = AgentNodeConfig(role="theme_designer", prompt="Make text blue")

    with patch("workflow.agent_registry.get_llm_client") as mock_get_llm:
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

        result = execute_agent(state, config)

    assert result.slides[0].elements[0].style.font_color == "#0000FF"
    mock_llm.bind_tools.assert_called_once()
