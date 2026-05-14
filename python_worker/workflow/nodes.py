from models.workflow import GraphState


def upload_parser_node(state: GraphState) -> dict:
    return {}


def editor_node(state: GraphState) -> dict:
    return {}


def exporter_node(state: GraphState) -> dict:
    return {"export_path": "/tmp/output.pptx"}
