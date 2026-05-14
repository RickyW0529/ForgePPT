# 06 - Workflow Nodes Implementation

**Files:**
- Create: `python_worker/workflow/nodes.py`
- Modify: `python_worker/tests/test_graph.py` (add node execution tests)
- Create: `python_worker/tests/test_nodes.py`

---

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_nodes.py
from unittest.mock import MagicMock, patch

import pytest
from models.workflow import EditRequest, EditResult, RefinerOutput
from workflow.nodes import text_refiner_node


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_nodes.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'workflow.nodes'"

- [ ] **Step 3: Write minimal implementation**

```python
# python_worker/workflow/nodes.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_nodes.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add python_worker/workflow/nodes.py python_worker/tests/test_nodes.py
git commit -m "feat: implement workflow nodes (upload_parser, editor, exporter)"
```
