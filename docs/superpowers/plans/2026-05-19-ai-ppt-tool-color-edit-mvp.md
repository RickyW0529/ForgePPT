# AI PPT Tool Color Edit MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP where a theme request lets the AI call a PPT editing tool to change slide text color, then exports a PPTX with the modified style written back.

**Architecture:** Keep the existing LangGraph flow and `EditRequest.type == "theme"` entry point. Add a small AI-visible `ppt_apply_style` tool schema plus backend executor that mutates a copied `PPTState`, then update the recomposer so modified `TextBox.style` fields are written into the exported PPTX. This proves the end-to-end protocol without adding a full multi-step agent loop.

**Tech Stack:** Python 3, Pydantic v2, LangChain tool binding, LangGraph, python-pptx, pytest.

---

## File Structure

- Modify `python_worker/llm/prompts.py`
  - Add a PPT editing agent system prompt and `build_ppt_editing_messages()` helper.
- Create `python_worker/llm/tools/ppt_apply_style.py`
  - Define `PPTApplyStyleInput`, a LangChain-compatible no-op schema function for AI binding, and `apply_style_to_ppt_state()` backend executor.
- Modify `python_worker/workflow/nodes.py`
  - Import the new prompt/tool helpers.
  - Change `theme_refiner_node()` from structured `ThemeOutput` to tool-call execution.
  - Keep existing `refine` and `placeholder` paths unchanged.
- Modify `python_worker/services/recomposer.py`
  - Apply `TextBox.style.font_color`, `font_size_pt`, `bold`, and `italic` to PowerPoint runs during export.
- Modify `python_worker/tests/test_nodes.py`
  - Add tests for mocked AI tool calls and no-tool failure.
- Modify `python_worker/tests/test_recomposer.py`
  - Add a round-trip color write-back test.

---

### Task 1: Add PPT Editing Prompt

**Files:**
- Modify: `python_worker/llm/prompts.py`
- Test: `python_worker/tests/test_prompts.py`

- [ ] **Step 1: Write the failing prompt test**

Add this test to `python_worker/tests/test_prompts.py`:

```python
def test_build_ppt_editing_messages_includes_instruction_and_slide_count():
    from llm.prompts import build_ppt_editing_messages

    messages = build_ppt_editing_messages(
        instruction="把第三页整体颜色改成蓝色",
        slide_count=3,
    )

    assert len(messages) == 2
    assert "PPT editing agent" in messages[0].content
    assert "ppt_apply_style" in messages[0].content
    assert "Slide count: 3" in messages[1].content
    assert "把第三页整体颜色改成蓝色" in messages[1].content
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd python_worker && python -m pytest tests/test_prompts.py::test_build_ppt_editing_messages_includes_instruction_and_slide_count -v
```

Expected: FAIL with import error or missing `build_ppt_editing_messages`.

- [ ] **Step 3: Implement prompt helper**

Append this code to `python_worker/llm/prompts.py` after `build_theme_messages()`:

```python

PPT_EDITING_SYSTEM_TEMPLATE = """You are a PPT editing agent. You must use the available PPT editing tools to modify the presentation state.

Available MVP tool:
- ppt_apply_style: apply text style changes to a selected slide scope.

Rules:
- When the user asks to change colors or overall visual style, call ppt_apply_style.
- Use one-based slide numbers from the user's request.
- If the user names a common color, convert it to a #RRGGBB hex color.
- For this MVP, use target=\"all_text\" for slide-level or presentation-level color changes.
- Do not claim the edit is complete unless you call a PPT editing tool."""


def build_ppt_editing_messages(
    instruction: str,
    slide_count: int,
) -> list[SystemMessage | HumanMessage]:
    """Build message list for PPT editing tool-call agent."""
    human_content = f"""Slide count: {slide_count}

User instruction:
{instruction}

Call the appropriate PPT editing tool to apply the requested change."""
    return [
        SystemMessage(content=PPT_EDITING_SYSTEM_TEMPLATE),
        HumanMessage(content=human_content),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd python_worker && python -m pytest tests/test_prompts.py::test_build_ppt_editing_messages_includes_instruction_and_slide_count -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add python_worker/llm/prompts.py python_worker/tests/test_prompts.py
git commit -m "feat: add ppt editing tool prompt"
```

---

### Task 2: Add PPT Apply Style Tool Executor

**Files:**
- Create: `python_worker/llm/tools/ppt_apply_style.py`
- Test: `python_worker/tests/test_nodes.py`

- [ ] **Step 1: Write failing executor tests**

Add these imports to `python_worker/tests/test_nodes.py`:

```python
from llm.tools.ppt_apply_style import PPTApplyStyleInput, apply_style_to_ppt_state
```

Add this helper near the top of `python_worker/tests/test_nodes.py`, after `reset_registry()`:

```python
def make_ppt_state_with_three_slides() -> PPTState:
    slide_size = SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0)
    slides = []
    for page_num in range(1, 4):
        slides.append(
            Slide(
                page_num=page_num,
                size=slide_size,
                elements=[
                    TextBox(
                        content=f"Slide {page_num} title",
                        position=Position(x_emu=0, y_emu=0, x_px=0.0, y_px=0.0),
                        size=Size(width_emu=1000000, height_emu=500000, width_px=100.0, height_px=50.0),
                        style=TextStyle(font_size_pt=20.0),
                    )
                ],
            )
        )
    return PPTState(
        source_file="test.pptx",
        slide_count=3,
        global_props=slide_size,
        slides=slides,
    )
```

Add these tests:

```python
def test_apply_style_to_ppt_state_updates_requested_slide_only():
    ppt_state = make_ppt_state_with_three_slides()
    result = apply_style_to_ppt_state(
        ppt_state,
        PPTApplyStyleInput(
            slide_number=3,
            target="all_text",
            font_color="#0000FF",
            font_size_multiplier=None,
            bold=None,
        ),
    )

    assert result["updated_textboxes"] == 1
    assert ppt_state.slides[0].elements[0].style.font_color is None
    assert ppt_state.slides[1].elements[0].style.font_color is None
    assert ppt_state.slides[2].elements[0].style.font_color == "#0000FF"


def test_apply_style_to_ppt_state_rejects_slide_out_of_range():
    ppt_state = make_ppt_state_with_three_slides()

    with pytest.raises(ValueError, match="slide_number 4 is outside valid range"):
        apply_style_to_ppt_state(
            ppt_state,
            PPTApplyStyleInput(
                slide_number=4,
                target="all_text",
                font_color="#0000FF",
                font_size_multiplier=None,
                bold=None,
            ),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd python_worker && python -m pytest tests/test_nodes.py::test_apply_style_to_ppt_state_updates_requested_slide_only tests/test_nodes.py::test_apply_style_to_ppt_state_rejects_slide_out_of_range -v
```

Expected: FAIL with missing module `llm.tools.ppt_apply_style`.

- [ ] **Step 3: Implement tool input and backend executor**

Create `python_worker/llm/tools/ppt_apply_style.py` with:

```python
from typing import Literal

from pydantic import BaseModel, Field

from models.ppt_state import PPTState


class PPTApplyStyleInput(BaseModel):
    slide_number: int | None = Field(
        None,
        ge=1,
        description="One-based slide number to modify. Use null to modify all slides.",
    )
    target: Literal["all_text"] = Field(
        "all_text",
        description="MVP target. all_text applies changes to every text box in the selected slide scope.",
    )
    font_color: str | None = Field(
        None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Optional text color as #RRGGBB.",
    )
    font_size_multiplier: float | None = Field(
        None,
        gt=0,
        description="Optional multiplier for existing font sizes.",
    )
    bold: bool | None = Field(
        None,
        description="Optional bold setting for selected text.",
    )


def ppt_apply_style(params: PPTApplyStyleInput) -> dict:
    """AI-visible schema function. Backend execution is handled by apply_style_to_ppt_state."""
    return {"accepted": True, "target": params.target}


def apply_style_to_ppt_state(ppt_state: PPTState, params: PPTApplyStyleInput) -> dict:
    """Apply validated style arguments to the mutable PPTState."""
    if params.font_color is None and params.font_size_multiplier is None and params.bold is None:
        raise ValueError("ppt_apply_style requires at least one style field")

    if params.slide_number is not None and params.slide_number > ppt_state.slide_count:
        raise ValueError(
            f"slide_number {params.slide_number} is outside valid range 1-{ppt_state.slide_count}"
        )

    updated = 0
    for slide in ppt_state.slides:
        if params.slide_number is not None and slide.page_num != params.slide_number:
            continue
        for elem in slide.elements:
            if elem.element_type != "textbox":
                continue
            if params.font_color is not None:
                elem.style.font_color = params.font_color.upper()
            if params.font_size_multiplier is not None and elem.style.font_size_pt:
                elem.style.font_size_pt = round(elem.style.font_size_pt * params.font_size_multiplier, 1)
            if params.bold is not None:
                elem.style.bold = params.bold
            updated += 1

    if updated == 0:
        scope = f"slide {params.slide_number}" if params.slide_number is not None else "all slides"
        raise ValueError(f"ppt_apply_style matched no text boxes in {scope}")

    return {
        "updated_textboxes": updated,
        "slide_number": params.slide_number,
        "target": params.target,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd python_worker && python -m pytest tests/test_nodes.py::test_apply_style_to_ppt_state_updates_requested_slide_only tests/test_nodes.py::test_apply_style_to_ppt_state_rejects_slide_out_of_range -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add python_worker/llm/tools/ppt_apply_style.py python_worker/tests/test_nodes.py
git commit -m "feat: add ppt apply style executor"
```

---

### Task 3: Route Theme Requests Through AI Tool Calls

**Files:**
- Modify: `python_worker/workflow/nodes.py`
- Test: `python_worker/tests/test_nodes.py`

- [ ] **Step 1: Write failing theme tool-call tests**

Add this class to `python_worker/tests/test_nodes.py`:

```python
class MockToolCallResponse:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls
```

Add these tests:

```python
def test_theme_refiner_node_executes_ai_tool_call_for_slide_color():
    from workflow.nodes import theme_refiner_node

    ppt_state = make_ppt_state_with_three_slides()
    state = GraphState.create(ppt_state=ppt_state)
    request = EditRequest(type="theme", prompt="把第三页整体颜色改成蓝色")

    mock_llm = MagicMock()
    bound_llm = MagicMock()
    bound_llm.invoke.return_value = MockToolCallResponse(
        [
            {
                "name": "ppt_apply_style",
                "args": {
                    "slide_number": 3,
                    "target": "all_text",
                    "font_color": "#0000FF",
                    "font_size_multiplier": None,
                    "bold": None,
                },
            }
        ]
    )
    mock_llm.bind_tools.return_value = bound_llm

    result = theme_refiner_node(state, request, mock_llm)

    assert result["edit_results"][0].status == "completed"
    assert result["ppt_state"].slides[0].elements[0].style.font_color is None
    assert result["ppt_state"].slides[1].elements[0].style.font_color is None
    assert result["ppt_state"].slides[2].elements[0].style.font_color == "#0000FF"
    mock_llm.bind_tools.assert_called_once()


def test_theme_refiner_node_fails_when_ai_does_not_call_tool():
    from workflow.nodes import theme_refiner_node

    ppt_state = make_ppt_state_with_three_slides()
    state = GraphState.create(ppt_state=ppt_state)
    request = EditRequest(type="theme", prompt="把第三页整体颜色改成蓝色")

    mock_llm = MagicMock()
    bound_llm = MagicMock()
    bound_llm.invoke.return_value = MockToolCallResponse([])
    mock_llm.bind_tools.return_value = bound_llm

    result = theme_refiner_node(state, request, mock_llm)

    assert result["edit_results"][0].status == "failed"
    assert "did not call" in result["edit_results"][0].error
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd python_worker && python -m pytest tests/test_nodes.py::test_theme_refiner_node_executes_ai_tool_call_for_slide_color tests/test_nodes.py::test_theme_refiner_node_fails_when_ai_does_not_call_tool -v
```

Expected: FAIL because `theme_refiner_node` still uses `with_structured_output(ThemeOutput, ...)` and does not consume `tool_calls`.

- [ ] **Step 3: Update imports in workflow nodes**

In `python_worker/workflow/nodes.py`, replace:

```python
from models.workflow import EditRequest, EditResult, GraphState, RefinerOutput, SVGOutput, ThemeOutput
```

with:

```python
from models.workflow import EditRequest, EditResult, GraphState, RefinerOutput, SVGOutput
```

Replace:

```python
from llm.prompts import build_refiner_messages, build_svg_messages, build_theme_messages
```

with:

```python
from llm.prompts import build_ppt_editing_messages, build_refiner_messages, build_svg_messages
```

Add this import after the existing tool imports:

```python
from llm.tools.ppt_apply_style import PPTApplyStyleInput, apply_style_to_ppt_state, ppt_apply_style
```

- [ ] **Step 4: Replace theme_refiner_node implementation**

Replace the entire `theme_refiner_node()` function in `python_worker/workflow/nodes.py` with:

```python
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
```

- [ ] **Step 5: Run focused theme tests**

Run:

```bash
cd python_worker && python -m pytest tests/test_nodes.py::test_theme_refiner_node_executes_ai_tool_call_for_slide_color tests/test_nodes.py::test_theme_refiner_node_fails_when_ai_does_not_call_tool -v
```

Expected: PASS.

- [ ] **Step 6: Update editor-node tool-binding test expectation**

The existing `test_editor_node_binds_tools_when_requests_present` mocks structured output. Replace its LLM mock setup block with tool-call response setup:

```python
    with patch("workflow.nodes.get_llm_client") as mock_get_llm:
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

        result = editor_node(state)
```

Keep the assertions:

```python
    assert result["edit_results"][0].status == "completed"
    assert "ppt_apply_style updated" in result["edit_results"][0].new_content
    mock_llm.bind_tools.assert_called_once()
```

- [ ] **Step 7: Run node tests**

Run:

```bash
cd python_worker && python -m pytest tests/test_nodes.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add python_worker/workflow/nodes.py python_worker/tests/test_nodes.py
git commit -m "feat: route theme edits through ppt tool calls"
```

---

### Task 4: Write Text Styles Back Into PPTX

**Files:**
- Modify: `python_worker/services/recomposer.py`
- Test: `python_worker/tests/test_recomposer.py`

- [ ] **Step 1: Write failing recomposer test**

Add these imports to `python_worker/tests/test_recomposer.py`:

```python
from pptx import Presentation
```

Add this test:

```python
def test_recompose_text_color_change_is_written_to_pptx():
    """Recomposing with a text color change should update the PPTX run color."""
    fixture_path = FIXTURES_DIR / "sample.pptx"
    if not fixture_path.exists():
        pytest.skip("sample.pptx fixture not found")

    state = parse_pptx(str(fixture_path))
    output_path = FIXTURES_DIR / "output_text_color_change.pptx"

    try:
        text_elems = [
            e
            for e in state.slides[0].elements
            if e.element_type == "textbox"
        ]
        if not text_elems:
            pytest.skip("sample.pptx fixture has no text boxes")
        text_elems[0].style.font_color = "#0000FF"

        recompose_pptx(str(fixture_path), state, str(output_path))
        assert output_path.exists()

        prs = Presentation(str(output_path))
        shape = next(shape for shape in prs.slides[0].shapes if shape.has_text_frame)
        run = shape.text_frame.paragraphs[0].runs[0]
        assert str(run.font.color.rgb) == "0000FF"
    finally:
        output_path.unlink(missing_ok=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd python_worker && python -m pytest tests/test_recomposer.py::test_recompose_text_color_change_is_written_to_pptx -v
```

Expected: FAIL because recomposer does not currently write `TextBox.style.font_color` into runs.

- [ ] **Step 3: Add style imports**

In `python_worker/services/recomposer.py`, add these imports after `from pptx import Presentation`:

```python
from pptx.dml.color import RGBColor
from pptx.util import Pt
```

Replace:

```python
from models.ppt_state import Image, PPTState, TextBox
```

with:

```python
from models.ppt_state import Image, PPTState, TextBox, TextStyle
```

- [ ] **Step 4: Add style helper functions**

Add these helpers above `_replace_text_preserving_format()`:

```python
def _hex_to_rgb_color(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.lstrip("#"))


def _apply_text_style_to_run(run, style: TextStyle) -> None:
    if style.font_color:
        run.font.color.rgb = _hex_to_rgb_color(style.font_color)
    if style.font_size_pt:
        run.font.size = Pt(style.font_size_pt)
    if style.bold is not None:
        run.font.bold = style.bold
    if style.italic is not None:
        run.font.italic = style.italic
```

- [ ] **Step 5: Update text replacement to apply style**

Replace `_replace_text_preserving_format()` in `python_worker/services/recomposer.py` with:

```python
def _replace_text_preserving_format(shape, new_content: str, style: TextStyle | None = None) -> None:
    """Replace shape text while preserving original formatting and applying requested style changes."""
    if not shape.has_text_frame:
        return
    text_frame = shape.text_frame
    paragraphs = text_frame.paragraphs
    if not paragraphs:
        return

    first_para = paragraphs[0]
    if not first_para.runs:
        run = first_para.add_run()
        run.text = new_content
        if style:
            _apply_text_style_to_run(run, style)
        return

    first_run = first_para.runs[0]
    # Clear other paragraphs
    for para in paragraphs[1:]:
        para.clear()
    # Clear other runs in first paragraph
    for run in first_para.runs[1:]:
        run.text = ""

    first_run.text = new_content
    if style:
        _apply_text_style_to_run(first_run, style)
```

In `_write_text_changes()`, replace:

```python
            _replace_text_preserving_format(shape, elem.content)
```

with:

```python
            _replace_text_preserving_format(shape, elem.content, elem.style)
```

- [ ] **Step 6: Run recomposer color test**

Run:

```bash
cd python_worker && python -m pytest tests/test_recomposer.py::test_recompose_text_color_change_is_written_to_pptx -v
```

Expected: PASS.

- [ ] **Step 7: Run all recomposer tests**

Run:

```bash
cd python_worker && python -m pytest tests/test_recomposer.py -v
```

Expected: PASS or fixture-dependent SKIP for tests that already skip when `sample.pptx` is missing.

- [ ] **Step 8: Commit**

```bash
git add python_worker/services/recomposer.py python_worker/tests/test_recomposer.py
git commit -m "feat: write text style changes to pptx"
```

---

### Task 5: Verify End-to-End Python Worker Tests

**Files:**
- Modify only if prior tasks reveal a failing test caused by the MVP changes.
- Test: `python_worker/tests/`

- [ ] **Step 1: Run all Python worker tests**

Run:

```bash
cd python_worker && python -m pytest tests/ -v
```

Expected: PASS, except tests that intentionally skip because local PPTX fixtures or external dependencies are unavailable.

- [ ] **Step 2: If `test_editor_node_binds_tools_when_requests_present` fails because of stale assertion text, use this assertion**

In `python_worker/tests/test_nodes.py`, ensure the final assertions are:

```python
    assert result["edit_results"][0].status == "completed"
    assert "ppt_apply_style updated" in result["edit_results"][0].new_content
    mock_llm.bind_tools.assert_called_once()
```

- [ ] **Step 3: If imports fail because `ThemeOutput` is unused in tests, remove it**

In `python_worker/tests/test_nodes.py`, replace:

```python
from models.workflow import EditRequest, EditResult, GraphState, RefinerOutput, ThemeOutput
```

with:

```python
from models.workflow import EditRequest, EditResult, GraphState, RefinerOutput
```

- [ ] **Step 4: Run all Python worker tests again**

Run:

```bash
cd python_worker && python -m pytest tests/ -v
```

Expected: PASS, except fixture/dependency skips.

- [ ] **Step 5: Commit final fixes if any files changed**

If Step 2 or Step 3 changed files, run:

```bash
git add python_worker/tests/test_nodes.py
git commit -m "test: update node tests for ppt tool calls"
```

If no files changed, do not create an empty commit.

---

## Self-Review

Spec coverage:

- AI-visible PPT editing tool contract: Task 2 and Task 3.
- Theme/style requests routed through AI tool calling: Task 3.
- Tool calls executed against `PPTState`: Task 2 and Task 3.
- Text color/style changes written back into PPTX: Task 4.
- Tests for tool-call execution and write-back: Tasks 2, 3, and 4.
- Existing synchronous `/tasks -> graph -> exporter` flow retained: Task 3 changes only editor behavior and Task 4 updates recomposer.

Placeholder scan: No TBD/TODO/fill-in instructions remain. Conditional verification steps in Task 5 include exact replacement code.

Type consistency:

- `PPTApplyStyleInput` fields match all tests and tool-call examples.
- `apply_style_to_ppt_state(ppt_state, params)` signature is used consistently.
- `build_ppt_editing_messages(instruction, slide_count)` signature is used consistently.
- Tool name is consistently `ppt_apply_style`.
