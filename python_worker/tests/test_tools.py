import pytest
from llm.tools.registry import ToolRegistry, llm_tool
from llm.tools.base import BaseToolInput
from pydantic import BaseModel


class MockInput(BaseModel):
    query: str


@llm_tool(name="mock_search", roles=["editor"], description="Mock search")
def mock_search(params: MockInput) -> str:
    return f"result for {params.query}"


def test_registry_lists_tools():
    registry = ToolRegistry()
    names = [t.name for t in registry.list_tools()]
    assert "mock_search" in names


def test_registry_filters_by_role():
    registry = ToolRegistry()
    editor_tools = registry.get_tools_for_role("editor")
    assert len(editor_tools) == 1
    assert editor_tools[0].name == "mock_search"

    exporter_tools = registry.get_tools_for_role("exporter")
    assert len(exporter_tools) == 0


def test_tool_invocation():
    registry = ToolRegistry()
    tool = registry.get_tool("mock_search")
    result = tool.invoke({"query": "hello"})
    assert result == "result for hello"
