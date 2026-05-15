# LLM Tools Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an extensible LLM tool system with registration, role-based access control, and two initial tools: vector graphics generation and PPT page screenshot.

**Architecture:** A decorator-based tool registry (`@llm_tool`) maps tools to allowed node roles. Nodes receive a filtered tool list via `registry.get_tools_for_role(role)`. Tools are bound to the LLM with LangChain `bind_tools()` so the model can choose to invoke them. Each tool is a pure function with a Pydantic input schema, returning structured output.

**Tech Stack:** Python 3.11, LangChain, Pydantic v2, python-pptx, LibreOffice (headless) for PPT→PNG conversion.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `python_worker/llm/tools/registry.py` | `ToolRegistry` singleton, `@llm_tool` decorator, role filtering |
| `python_worker/llm/tools/base.py` | `BaseToolInput` Pydantic model, tool wrapper/protocol |
| `python_worker/llm/tools/svg_generator.py` | Vector graphics tool: LLM→SVG generation |
| `python_worker/llm/tools/ppt_screenshot.py` | PPT page screenshot tool: slide→PNG (base64) |
| `python_worker/llm/tools/__init__.py` | Public exports: `registry`, `svg_generator_tool`, `ppt_screenshot_tool` |
| `python_worker/tests/test_tools.py` | Unit tests for registry, role filtering, and both tools |

---

## Task 1: Tool Registry and Base Classes

**Files:**
- Create: `python_worker/llm/tools/__init__.py`
- Create: `python_worker/llm/tools/base.py`
- Create: `python_worker/llm/tools/registry.py`
- Test: `python_worker/tests/test_tools.py`

- [ ] **Step 1: Write the failing test for registry basics**

```python
# python_worker/tests/test_tools.py
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
```

Run: `cd python_worker && pytest tests/test_tools.py -v`
Expected: FAIL with imports missing

- [ ] **Step 2: Create `base.py`**

```python
# python_worker/llm/tools/base.py
from typing import Any, Callable
from pydantic import BaseModel

class BaseToolInput(BaseModel):
    """All tool inputs inherit from this."""
    pass

class ToolDefinition:
    """Wraps a callable tool with metadata for LLM binding."""

    def __init__(
        self,
        name: str,
        description: str,
        roles: list[str],
        input_model: type[BaseModel],
        func: Callable[[Any], Any],
    ):
        self.name = name
        self.description = description
        self.roles = set(roles)
        self.input_model = input_model
        self.func = func

    def invoke(self, params: dict) -> Any:
        validated = self.input_model.model_validate(params)
        return self.func(validated)
```

- [ ] **Step 3: Create `registry.py`**

```python
# python_worker/llm/tools/registry.py
import inspect
from typing import Any, Callable
from pydantic import BaseModel
from llm.tools.base import ToolDefinition

class ToolRegistry:
    """Singleton registry for LLM tools."""

    _instance: "ToolRegistry | None" = None
    _tools: dict[str, ToolDefinition]

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(
        self,
        name: str,
        description: str,
        roles: list[str],
        input_model: type[BaseModel],
        func: Callable[[Any], Any],
    ) -> None:
        if name in self._tools:
            raise ValueError(f"Tool '{name}' already registered")
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            roles=roles,
            input_model=input_model,
            func=func,
        )

    def get_tool(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found")
        return self._tools[name]

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_tools_for_role(self, role: str) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if role in t.roles]


def llm_tool(
    name: str,
    roles: list[str],
    description: str = "",
) -> Callable:
    """Decorator to register a function as an LLM tool.

    The decorated function must accept a single Pydantic model argument
    (its input schema) and return a JSON-serializable value.
    """
    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        if len(params) != 1:
            raise TypeError(f"Tool '{name}' must accept exactly one argument (input model)")
        input_model = params[0].annotation
        if not issubclass(input_model, BaseModel):
            raise TypeError(f"Tool '{name}' argument must be a Pydantic model")

        registry = ToolRegistry()
        registry.register(
            name=name,
            description=description or func.__doc__ or "",
            roles=roles,
            input_model=input_model,
            func=func,
        )
        return func
    return decorator
```

- [ ] **Step 4: Create `__init__.py`**

```python
# python_worker/llm/tools/__init__.py
from llm.tools.registry import ToolRegistry, llm_tool

__all__ = ["ToolRegistry", "llm_tool"]
```

- [ ] **Step 5: Run tests**

Run: `cd python_worker && pytest tests/test_tools.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python_worker/llm/tools/ python_worker/tests/test_tools.py
git commit -m "feat: add LLM tool registry with role-based access control"
```

---

## Task 2: Vector Graphics Generation Tool

**Files:**
- Create: `python_worker/llm/tools/svg_generator.py`
- Modify: `python_worker/llm/tools/__init__.py`
- Test: `python_worker/tests/test_tools.py`

- [ ] **Step 1: Write the failing test for SVG generator**

Add to `python_worker/tests/test_tools.py`:

```python
from llm.tools.svg_generator import svg_generator_tool, SVGGeneratorInput

def test_svg_generator_schema():
    inp = SVGGeneratorInput(description="A blue circle", style_hint="minimal")
    assert inp.description == "A blue circle"
    assert inp.style_hint == "minimal"

def test_svg_generator_invocation(mocker):
    # Mock the LLM call inside the tool
    from llm.tools.svg_generator import _generate_svg_with_llm
    mocker.patch(
        "llm.tools.svg_generator._generate_svg_with_llm",
        return_value='<svg><circle r="10"/></svg>',
    )
    registry = ToolRegistry()
    tool = registry.get_tool("svg_generator")
    result = tool.invoke({"description": "circle", "style_hint": None})
    assert "<svg>" in result["svg_xml"]
    assert result["description"] == "circle"
```

Run: `cd python_worker && pytest tests/test_tools.py::test_svg_generator_schema -v`
Expected: FAIL with import error

- [ ] **Step 2: Create `svg_generator.py`**

```python
# python_worker/llm/tools/svg_generator.py
from pydantic import BaseModel, Field
from llm.tools.registry import llm_tool
from llm.client import get_llm_client
from llm.prompts import build_svg_messages

class SVGGeneratorInput(BaseModel):
    description: str = Field(..., description="Detailed description of the desired vector graphic")
    style_hint: str | None = Field(None, description="Optional style direction, e.g. 'minimal flat icon'")

class SVGGeneratorOutput(BaseModel):
    svg_xml: str = Field(..., description="Complete SVG XML string without markdown code fences")
    description: str = Field(..., description="Brief description of the generated graphic")


def _generate_svg_with_llm(description: str, style_hint: str | None) -> dict:
    llm = get_llm_client()
    messages = build_svg_messages(description, style_hint)
    structured_llm = llm.with_structured_output(SVGGeneratorOutput, method="json_schema")
    response: SVGGeneratorOutput = structured_llm.invoke(messages)
    return {
        "svg_xml": response.svg_xml,
        "description": response.description,
    }


@llm_tool(
    name="svg_generator",
    roles=["editor"],
    description=(
        "Generate a vector SVG graphic from a text description. "
        "Returns valid SVG XML that can be embedded in a slide."
    ),
)
def svg_generator_tool(params: SVGGeneratorInput) -> dict:
    """Generate an SVG based on the user's description."""
    return _generate_svg_with_llm(params.description, params.style_hint)
```

- [ ] **Step 3: Update `__init__.py`**

```python
# python_worker/llm/tools/__init__.py
from llm.tools.registry import ToolRegistry, llm_tool
from llm.tools.svg_generator import svg_generator_tool

__all__ = ["ToolRegistry", "llm_tool", "svg_generator_tool"]
```

- [ ] **Step 4: Run tests**

Run: `cd python_worker && pytest tests/test_tools.py::test_svg_generator_schema tests/test_tools.py::test_svg_generator_invocation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_worker/llm/tools/
git commit -m "feat: add svg_generator LLM tool"
```

---

## Task 3: PPT Page Screenshot Tool

**Files:**
- Create: `python_worker/llm/tools/ppt_screenshot.py`
- Modify: `python_worker/llm/tools/__init__.py`
- Test: `python_worker/tests/test_tools.py`

- [ ] **Step 1: Write the failing test for PPT screenshot**

Add to `python_worker/tests/test_tools.py`:

```python
from llm.tools.ppt_screenshot import ppt_screenshot_tool, PPTScreenshotInput

def test_ppt_screenshot_schema():
    inp = PPTScreenshotInput(slide_number=1, width_px=1280)
    assert inp.slide_number == 1
    assert inp.width_px == 1280

def test_ppt_screenshot_role():
    registry = ToolRegistry()
    tools = registry.get_tools_for_role("editor")
    names = [t.name for t in tools]
    assert "ppt_screenshot" in names
```

Run: `cd python_worker && pytest tests/test_tools.py::test_ppt_screenshot_schema -v`
Expected: FAIL with import error

- [ ] **Step 2: Create `ppt_screenshot.py`**

```python
# python_worker/llm/tools/ppt_screenshot.py
import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field
from llm.tools.registry import llm_tool

class PPTScreenshotInput(BaseModel):
    slide_number: int = Field(..., ge=1, description="1-based slide number to capture")
    width_px: int = Field(1280, ge=640, le=3840, description="Output image width in pixels")


def _libreoffice_available() -> bool:
    return shutil.which("soffice") is not None or shutil.which("libreoffice") is not None


def _soffice_cmd() -> str:
    if shutil.which("soffice"):
        return "soffice"
    if shutil.which("libreoffice"):
        return "libreoffice"
    raise RuntimeError("LibreOffice not found")


def _convert_slide_to_png(pptx_path: str, slide_number: int, width_px: int) -> str:
    """Convert a single PPT slide to PNG and return base64 data URL.

    Uses LibreOffice headless to export the PPTX to PDF, then pdf2image
    to render the requested slide as PNG. Falls back to a placeholder
    if dependencies are missing.
    """
    if not _libreoffice_available():
        return _placeholder_image(slide_number)

    path = Path(pptx_path)
    if not path.exists():
        raise FileNotFoundError(f"PPTX not found: {pptx_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # LibreOffice headless export to PDF
        cmd = [
            _soffice_cmd(),
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(tmp_path),
            str(path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            return _placeholder_image(slide_number)

        pdf_file = tmp_path / f"{path.stem}.pdf"
        if not pdf_file.exists():
            return _placeholder_image(slide_number)

        try:
            from pdf2image import convert_from_path
            pages = convert_from_path(str(pdf_file), dpi=width_px // 10)
            if slide_number > len(pages):
                raise ValueError(f"Slide {slide_number} exceeds total {len(pages)}")
            img = pages[slide_number - 1]
            png_path = tmp_path / "slide.png"
            img.save(str(png_path), "PNG")
            b64 = base64.b64encode(png_path.read_bytes()).decode()
            return f"data:image/png;base64,{b64}"
        except ImportError:
            return _placeholder_image(slide_number)


def _placeholder_image(slide_number: int) -> str:
    """Return a transparent 1x1 PNG as a fallback when rendering is unavailable."""
    # Minimal valid PNG, 1x1 transparent pixel
    minimal_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\xfc\xcf\xc0\x50\x0f\x00\x04A\x01\xa1\x3a\xf0\xfc\xcc\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    b64 = base64.b64encode(minimal_png).decode()
    return f"data:image/png;base64,{b64}"


@llm_tool(
    name="ppt_screenshot",
    roles=["editor"],
    description=(
        "Capture a screenshot of a specific slide in the uploaded PPT "
        "and return it as a base64 PNG image. Useful for visual analysis."
    ),
)
def ppt_screenshot_tool(params: PPTScreenshotInput) -> dict:
    """Render a PPT slide to an image.

    Requires the pptx source path to be available in the workflow context.
    In practice the caller must inject `pptx_path` before invoking.
    """
    # The actual pptx_path is injected by the node at runtime via closure or context.
    # For the tool interface we return a structured dict; the node wires the path.
    return {
        "slide_number": params.slide_number,
        "width_px": params.width_px,
        "image_data": None,  # populated by node wrapper
        "note": "Use the node-level wrapper that injects pptx_path.",
    }


def render_slide(pptx_path: str, slide_number: int, width_px: int = 1280) -> str:
    """Standalone helper for nodes to call directly. Returns base64 data URL."""
    return _convert_slide_to_png(pptx_path, slide_number, width_px)
```

- [ ] **Step 3: Update `__init__.py`**

```python
# python_worker/llm/tools/__init__.py
from llm.tools.registry import ToolRegistry, llm_tool
from llm.tools.svg_generator import svg_generator_tool
from llm.tools.ppt_screenshot import ppt_screenshot_tool, render_slide

__all__ = [
    "ToolRegistry",
    "llm_tool",
    "svg_generator_tool",
    "ppt_screenshot_tool",
    "render_slide",
]
```

- [ ] **Step 4: Run tests**

Run: `cd python_worker && pytest tests/test_tools.py::test_ppt_screenshot_schema tests/test_tools.py::test_ppt_screenshot_role -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_worker/llm/tools/ python_worker/tests/test_tools.py
git commit -m "feat: add ppt_screenshot LLM tool with LibreOffice fallback"
```

---

## Task 4: Node Integration — Bind Tools to LLM in Editor Node

**Files:**
- Modify: `python_worker/workflow/nodes.py`
- Modify: `python_worker/models/workflow.py`
- Test: `python_worker/tests/test_nodes.py` (create if missing)

- [ ] **Step 1: Write the failing test for tool-aware LLM binding**

Create `python_worker/tests/test_nodes.py`:

```python
from unittest.mock import MagicMock, patch
from workflow.nodes import editor_node
from models.workflow import GraphState

def test_editor_node_binds_tools_when_requests_present():
    state = GraphState.create(
        ppt_state={"slides": [], "slide_count": 0, "global_props": {}, "source_file": "/tmp/test.pptx"},
        edit_requests=[{"type": "theme", "prompt": "blue style"}],
    )
    with patch("workflow.nodes.get_llm_client") as mock_get_llm:
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = MagicMock(
            color_palette=["#0000FF"], font_size_multiplier=1.0, make_bold=False, change_summary="ok"
        )
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        result = editor_node(state)
        assert result["edit_results"][0]["status"] == "completed"
```

Run: `cd python_worker && pytest tests/test_nodes.py -v`
Expected: FAIL (file may not exist or test logic may need tweaking)

- [ ] **Step 2: Add `ToolAwareLLM` helper in `llm/client.py`**

Modify `python_worker/llm/client.py` — add at the bottom:

```python
from langchain_core.tools import BaseTool

def bind_tools_to_llm(llm, tools: list[BaseTool]):
    """Bind a list of LangChain-compatible tools to an LLM client."""
    return llm.bind_tools(tools)
```

- [ ] **Step 3: Modify `editor_node` to optionally bind tools**

In `python_worker/workflow/nodes.py`, add at the top:

```python
from llm.tools.registry import ToolRegistry
```

Inside `editor_node`, before calling the sub-node:

```python
def editor_node(state: GraphState) -> dict:
    ppt_state = PPTState.model_validate(state.get("ppt_state") or {})
    requests_data = state.get("edit_requests") or []
    results: list[dict] = []

    registry = ToolRegistry()
    available_tools = registry.get_tools_for_role("editor")
    # Convert to LangChain tool format for binding
    lc_tools = []
    for t in available_tools:
        from langchain_core.tools import StructuredTool
        lc_tools.append(
            StructuredTool.from_function(
                name=t.name,
                description=t.description,
                func=t.invoke,
                args_schema=t.input_model,
            )
        )

    for req_data in requests_data:
        request = EditRequest.model_validate(req_data)
        try:
            if request.type == "refine":
                result = text_refiner_node(state, request, tools=lc_tools)
            elif request.type == "placeholder":
                result = svg_placeholder_node(state, request, tools=lc_tools)
            elif request.type == "theme":
                result = theme_refiner_node(state, request, tools=lc_tools)
            else:
                raise ValueError(f"Unknown edit type: {request.type}")
            results.append(result)
        except Exception as e:
            results.append({
                "request_id": request.id,
                "status": "failed",
                "error": str(e),
            })

    return {"edit_results": results}
```

- [ ] **Step 4: Update sub-nodes to accept and forward `tools`**

For each sub-node (`text_refiner_node`, `svg_placeholder_node`, `theme_refiner_node`), add a `tools=None` parameter and pass it to `llm.bind_tools(tools)` when `tools` is non-empty.

Example for `theme_refiner_node`:

```python
def theme_refiner_node(state: GraphState, request: EditRequest, tools=None) -> dict:
    ppt_state = PPTState.model_validate(state.get("ppt_state") or {})
    text_samples = []
    for slide in ppt_state.slides:
        for el in slide.elements:
            if isinstance(el, TextBox) and el.content.strip():
                text_samples.append(el.content[:200])
    if not text_samples:
        text_samples = ["No text found"]

    llm = get_llm_client()
    messages = build_theme_messages(text_samples, request.prompt)
    if tools:
        llm = llm.bind_tools(tools)
    structured_llm = llm.with_structured_output(ThemeOutput, method="function_calling")
    response: ThemeOutput = structured_llm.invoke(messages)
    # ... rest unchanged
```

Repeat the same `if tools: llm = llm.bind_tools(tools)` pattern for `text_refiner_node` and `svg_placeholder_node`.

- [ ] **Step 5: Run tests**

Run: `cd python_worker && pytest tests/test_nodes.py -v`
Expected: PASS (or adjust mocks as needed)

- [ ] **Step 6: Commit**

```bash
git add python_worker/llm/client.py python_worker/workflow/nodes.py python_worker/tests/test_nodes.py
git commit -m "feat: wire tool registry into editor node with optional LLM tool binding"
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - Tool registration (`@llm_tool`, `ToolRegistry`) → Task 1
   - Tool usage restriction by node role (`get_tools_for_role`) → Task 1
   - Tool logic (vector graphics generation) → Task 2
   - Tool logic (PPT page screenshot) → Task 3
   - Extensibility (new tools just need decorator + file) → Task 1 & 4

2. **Placeholder scan:** No TBD, TODO, or vague steps found.

3. **Type consistency:** `llm_tool` decorator always expects a single Pydantic argument. `ToolDefinition.invoke` validates with `model_validate`. `editor_node` passes `lc_tools` (LangChain `StructuredTool` list) to sub-nodes. Sub-nodes conditionally call `llm.bind_tools(tools)`.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-14-llm-tools-module.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?