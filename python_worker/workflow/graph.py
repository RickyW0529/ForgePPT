from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from models.workflow import GraphState
from workflow.nodes import editor_node, exporter_node, upload_parser_node


class _GraphStateSchema(TypedDict):
    """Internal schema for LangGraph StateGraph."""
    ppt_state: dict | None
    edit_requests: list[dict]
    edit_results: list[dict]
    export_path: str | None
    error: str | None


def build_graph():
    """Build and compile the LangGraph DAG.

    Structure: START -> upload_parser -> editor -> exporter -> END
    """
    builder = StateGraph(_GraphStateSchema)

    builder.add_node("upload_parser", upload_parser_node)
    builder.add_node("editor", editor_node)
    builder.add_node("exporter", exporter_node)

    builder.add_edge(START, "upload_parser")
    builder.add_edge("upload_parser", "editor")
    builder.add_edge("editor", "exporter")
    builder.add_edge("exporter", END)

    return builder.compile()
