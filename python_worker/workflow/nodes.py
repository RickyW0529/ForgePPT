import copy
from pathlib import Path

try:
    from defusedxml import ElementTree as DefusedET
except ImportError:
    import xml.etree.ElementTree as DefusedET

from models.ppt_state import PPTState
from models.workflow import EditRequest, EditResult, GraphState, RefinerOutput, SVGOutput
from llm.client import get_llm_client
from llm.prompts import build_ppt_editing_messages, build_refiner_messages, build_svg_messages
from llm.tools.registry import ToolRegistry
from llm.tools.svg_generator import svg_generator_tool
from llm.tools.ppt_screenshot import ppt_screenshot_tool
from llm.tools.ppt_apply_style import PPTApplyStyleInput, apply_style_to_ppt_state, ppt_apply_style
from services.recomposer import recompose_pptx

from langchain_core.tools import BaseTool, StructuredTool


def upload_parser_node(state: GraphState) -> dict:
    """Upload/parser node: loads PPTState into graph state.

    In the real pipeline this would receive a file path and call parse_pptx.
    For the workflow engine, we assume ppt_state is already present.
    """
    return {}


def text_refiner_node(state: GraphState, request: EditRequest, llm, tools: list[BaseTool] | None = None) -> dict:
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

    messages = build_refiner_messages(text_box.content, request.prompt)
    if tools:
        llm = llm.bind_tools(tools)
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


def svg_placeholder_node(state: GraphState, request: EditRequest, llm, tools: list[BaseTool] | None = None) -> dict:
    """SVG placeholder sub-node: generates SVG for an image placeholder."""
    messages = build_svg_messages(request.prompt, request.style_hint)
    if tools:
        llm = llm.bind_tools(tools)
    structured_llm = llm.with_structured_output(SVGOutput, method="json_schema")
    response: SVGOutput = structured_llm.invoke(messages)

    svg_clean = response.svg_xml.replace("```xml", "").replace("```", "").strip()
    # Basic SVG validation
    try:
        root = DefusedET.fromstring(svg_clean)
        if root.tag.lower() != "svg":
            raise ValueError("Root element is not <svg>")
    except Exception as e:
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


def _tool_call_name(tool_call) -> str | None:
    if isinstance(tool_call, dict):
        return tool_call.get("name")
    return getattr(tool_call, "name", None)


def _tool_call_args(tool_call) -> dict:
    if isinstance(tool_call, dict):
        return tool_call.get("args") or {}
    return getattr(tool_call, "args", {}) or {}


def theme_refiner_node(state: GraphState, request: EditRequest, llm, tools: list[BaseTool] | None = None) -> dict:
    """Theme refinement sub-node: lets AI call PPT editing tools and applies them."""
    ppt_state: PPTState = copy.deepcopy(state["ppt_state"])
    messages = build_ppt_editing_messages(request.prompt, ppt_state.slide_count)

    ppt_tools = [
        StructuredTool.from_function(
            name="ppt_apply_style",
            description=(
                "Apply text style changes to a PPT slide scope. Use this for requests "
                "to change text color or overall color style."
            ),
            func=ppt_apply_style,
            args_schema=PPTApplyStyleInput,
        )
    ]
    llm_with_tools = llm.bind_tools(ppt_tools)
    response = llm_with_tools.invoke(messages)
    tool_calls = getattr(response, "tool_calls", None) or []

    if not tool_calls:
        return {
            "edit_results": [
                EditResult(
                    request_id=request.id,
                    status="failed",
                    error="AI did not call a PPT editing tool",
                )
            ]
        }

    summaries = []
    try:
        for tool_call in tool_calls:
            name = _tool_call_name(tool_call)
            if name != "ppt_apply_style":
                raise ValueError(f"Unsupported PPT editing tool: {name}")
            params = PPTApplyStyleInput.model_validate(_tool_call_args(tool_call))
            result = apply_style_to_ppt_state(ppt_state, params)
            scope = f"slide {result['slide_number']}" if result["slide_number"] else "all slides"
            summaries.append(f"ppt_apply_style updated {result['updated_textboxes']} text boxes in {scope}")
    except Exception as e:
        return {
            "edit_results": [
                EditResult(
                    request_id=request.id,
                    status="failed",
                    error=str(e),
                )
            ]
        }

    return {
        "ppt_state": ppt_state,
        "edit_results": [
            EditResult(
                request_id=request.id,
                status="completed",
                new_content="; ".join(summaries),
            )
        ],
    }


def editor_node(state: GraphState) -> dict:
    """Editor node: routes edit requests to appropriate sub-nodes."""
    if state.get("error"):
        return {}

    llm = get_llm_client()
    registry = ToolRegistry()
    available_tools = registry.get_tools_for_role("editor")
    lc_tools = []
    for t in available_tools:
        lc_tools.append(
            StructuredTool.from_function(
                name=t.name,
                description=t.description,
                func=t.invoke,
                args_schema=t.input_model,
            )
        )

    all_results = []
    updated_ppt_state = None
    for req_data in state.get("edit_requests", []):
        try:
            request = EditRequest.model_validate(req_data) if isinstance(req_data, dict) else req_data
            if request.type == "refine":
                result = text_refiner_node(state, request, llm, tools=lc_tools)
            elif request.type == "placeholder":
                result = svg_placeholder_node(state, request, llm, tools=lc_tools)
            elif request.type == "theme":
                result = theme_refiner_node(state, request, llm, tools=lc_tools)
                updated_ppt_state = result.get("ppt_state", updated_ppt_state)
            else:
                raise ValueError(f"Unknown edit type: {request.type}")
            all_results.extend(result.get("edit_results", []))
        except Exception as e:
            request_id = req_data.get("id") if isinstance(req_data, dict) else getattr(req_data, "id", None)
            all_results.append(
                EditResult(
                    request_id=request_id or "unknown",
                    status="failed",
                    error=str(e),
                )
            )

    result_dict = {"edit_results": all_results}
    if updated_ppt_state is not None:
        result_dict["ppt_state"] = updated_ppt_state
    return result_dict


def exporter_node(state: GraphState) -> dict:
    """Exporter node: recompose PPTX from modified PPTState."""
    ppt_state: PPTState = state.get("ppt_state")
    if not ppt_state:
        return {"error": "No PPTState available for export"}

    source_file = ppt_state.source_file
    if not source_file or not Path(source_file).exists():
        return {"error": f"Source file not found: {source_file}"}

    output_path = f"/tmp/forgeppt_output_{ppt_state.source_file.replace('/', '_')}"
    try:
        recompose_pptx(source_file, ppt_state, output_path)
        return {"export_path": output_path}
    except Exception as e:
        return {"error": f"Export failed: {e}"}
