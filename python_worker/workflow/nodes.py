import xml.etree.ElementTree as ET
from hashlib import sha256

from models.ppt_state import PPTState
from models.workflow import EditRequest, EditResult, GraphState, RefinerOutput, SVGOutput
from llm.client import get_llm_client
from llm.prompts import build_refiner_messages, build_svg_messages


def upload_parser_node(state: GraphState) -> dict:
    """Upload/parser node: loads PPTState into graph state.

    In the real pipeline this would receive a file path and call parse_pptx.
    For the workflow engine, we assume ppt_state is already present.
    """
    return {}


def text_refiner_node(state: GraphState, request: EditRequest) -> dict:
    """Text refinement sub-node: rewrites a single text box."""
    ppt_state: PPTState = state["ppt_state"]
    text_box = None
    for slide in ppt_state.slides:
        for elem in slide.elements:
            if elem.element_type == "textbox" and elem.text_id == request.text_id:
                text_box = elem
                break
        if text_box:
            break

    if text_box is None:
        return {
            "edit_results": [
                EditResult(
                    request_id=request.id,
                    status="failed",
                    error=f"Text box {request.text_id} not found",
                )
            ]
        }

    llm = get_llm_client()
    messages = build_refiner_messages(text_box.content, request.prompt)
    structured_llm = llm.with_structured_output(RefinerOutput, method="function_calling")
    response: RefinerOutput = structured_llm.invoke(messages)

    return {
        "edit_results": [
            EditResult(
                request_id=request.id,
                status="completed",
                new_content=response.refined_text,
            )
        ]
    }


def svg_placeholder_node(state: GraphState, request: EditRequest) -> dict:
    """SVG placeholder sub-node: generates SVG for an image placeholder."""
    llm = get_llm_client()
    messages = build_svg_messages(request.prompt, request.style_hint)
    structured_llm = llm.with_structured_output(SVGOutput, method="json_schema")
    response: SVGOutput = structured_llm.invoke(messages)

    svg_clean = response.svg_xml.replace("```xml", "").replace("```", "").strip()
    # Basic SVG validation
    try:
        root = ET.fromstring(svg_clean)
        if root.tag.lower() != "svg":
            raise ValueError("Root element is not <svg>")
    except ET.ParseError as e:
        return {
            "edit_results": [
                EditResult(
                    request_id=request.id,
                    status="failed",
                    error=f"SVG validation failed: {e}",
                )
            ]
        }

    return {
        "edit_results": [
            EditResult(
                request_id=request.id,
                status="completed",
                svg_xml=svg_clean,
            )
        ]
    }


def editor_node(state: GraphState) -> dict:
    """Editor node: routes edit requests to appropriate sub-nodes."""
    if state.get("error"):
        return {}

    edit_requests: list[EditRequest] = [
        EditRequest.model_validate(r) if isinstance(r, dict) else r
        for r in state.get("edit_requests", [])
    ]

    all_results = []
    for request in edit_requests:
        if request.type == "refine":
            result = text_refiner_node(state, request)
        elif request.type == "placeholder":
            result = svg_placeholder_node(state, request)
        else:
            result = {
                "edit_results": [
                    EditResult(
                        request_id=request.id,
                        status="failed",
                        error=f"Unknown request type: {request.type}",
                    )
                ]
            }
        all_results.extend(result.get("edit_results", []))

    return {"edit_results": all_results}


def exporter_node(state: GraphState) -> dict:
    """Exporter node: finalizes output path."""
    return {"export_path": "/tmp/output.pptx"}
