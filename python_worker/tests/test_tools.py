import pytest
from pydantic import BaseModel, ValidationError
from llm.tools.registry import ToolRegistry, llm_tool


class MockInput(BaseModel):
    query: str


@pytest.fixture(autouse=True)
def reset_registry():
    ToolRegistry().clear()
    yield


def _register_mock_search():
    @llm_tool(name="mock_search", roles=["editor"], description="Mock search")
    def mock_search(params: MockInput) -> str:
        return f"result for {params.query}"


def test_registry_lists_tools():
    _register_mock_search()
    registry = ToolRegistry()
    names = [t.name for t in registry.list_tools()]
    assert "mock_search" in names


def test_registry_filters_by_role():
    _register_mock_search()
    registry = ToolRegistry()
    editor_tools = registry.get_tools_for_role("editor")
    assert len(editor_tools) == 1
    assert editor_tools[0].name == "mock_search"

    exporter_tools = registry.get_tools_for_role("exporter")
    assert len(exporter_tools) == 0


def test_tool_invocation():
    _register_mock_search()
    registry = ToolRegistry()
    tool = registry.get_tool("mock_search")
    result = tool.invoke({"query": "hello"})
    assert result == "result for hello"


def test_duplicate_registration_raises():
    _register_mock_search()
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            name="mock_search",
            description="dup",
            roles=["editor"],
            input_model=MockInput,
            func=lambda x: x,
        )


def test_missing_tool_raises():
    registry = ToolRegistry()
    with pytest.raises(KeyError, match="not found"):
        registry.get_tool("nonexistent")


def test_decorator_zero_args_raises():
    with pytest.raises(TypeError, match="exactly one argument"):
        @llm_tool(name="bad", roles=["editor"])
        def bad_tool():
            pass


def test_decorator_two_args_raises():
    with pytest.raises(TypeError, match="exactly one argument"):
        @llm_tool(name="bad_two", roles=["editor"])
        def bad_tool_two(params: MockInput, extra: str):
            pass


def test_decorator_non_pydantic_arg_raises():
    with pytest.raises(TypeError, match="Pydantic model"):
        @llm_tool(name="bad2", roles=["editor"])
        def bad_tool2(params: str):
            pass


def test_invocation_validation_error():
    _register_mock_search()
    registry = ToolRegistry()
    tool = registry.get_tool("mock_search")
    with pytest.raises(ValidationError):
        tool.invoke({"bad_key": 123})


def test_svg_generator_schema():
    from llm.tools.svg_generator import SVGGeneratorInput
    inp = SVGGeneratorInput(description="A blue circle", style_hint="minimal")
    assert inp.description == "A blue circle"
    assert inp.style_hint == "minimal"


def test_svg_generator_invocation():
    # Importing registers the tool via @llm_tool decorator
    from unittest.mock import patch
    import importlib
    from llm.tools import svg_generator
    from llm.tools.registry import ToolRegistry

    importlib.reload(svg_generator)  # Re-register after fixture clear

    with patch("llm.tools.svg_generator._generate_svg_with_llm") as mock_gen:
        mock_gen.return_value = {"svg_xml": '<svg><circle r="10"/></svg>', "description": "circle"}
        registry = ToolRegistry()
        tool = registry.get_tool("svg_generator")
        result = tool.invoke({"description": "circle", "style_hint": None})
        assert "<svg>" in result["svg_xml"]
        assert result["description"] == "circle"
