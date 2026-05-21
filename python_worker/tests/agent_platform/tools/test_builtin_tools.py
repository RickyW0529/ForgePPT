"""Tests for built-in PPT tools (Module 2.2)."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from agent_platform.tools.descriptor import Capability
from agent_platform.tools.sandbox import (
    PermissionDeniedError,
    ToolContext,
    ToolExecutionError,
    sandboxed_execute,
)

# Import tool classes and schemas from the builtin module
from agent_platform.tools.builtin import (
    BUILTIN_TOOLS,
    PPTApplyStyleInput,
    PPTApplyStyleOutput,
    PPTApplyStyleTool,
    PPTApplyTextInput,
    PPTApplyTextOutput,
    PPTApplyTextTool,
    PPTInspectSlideInput,
    PPTInspectSlideOutput,
    PPTInspectSlideTool,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_ppt_state() -> dict[str, Any]:
    """Return a minimal valid PPTState dict with two text boxes."""
    return {
        "version": "1.0.0",
        "source_file": "test.pptx",
        "slide_count": 1,
        "slides": [
            {
                "slide_id": "slide-1",
                "page_num": 1,
                "size": {
                    "width_emu": 9_144_000,
                    "height_emu": 6_858_000,
                    "width_px": 960.0,
                    "height_px": 720.0,
                },
                "elements": [
                    {
                        "element_type": "textbox",
                        "text_id": "text-1",
                        "content": "Hello World",
                        "position": {
                            "x_emu": 0,
                            "y_emu": 0,
                            "x_px": 0.0,
                            "y_px": 0.0,
                        },
                        "size": {
                            "width_emu": 1_000_000,
                            "height_emu": 1_000_000,
                            "width_px": 100.0,
                            "height_px": 100.0,
                        },
                        "style": {
                            "font_size_pt": 12.0,
                            "font_color": "#000000",
                            "bold": False,
                        },
                    },
                    {
                        "element_type": "textbox",
                        "text_id": "text-2",
                        "content": "Second box",
                        "position": {
                            "x_emu": 0,
                            "y_emu": 0,
                            "x_px": 0.0,
                            "y_px": 0.0,
                        },
                        "size": {
                            "width_emu": 1_000_000,
                            "height_emu": 1_000_000,
                            "width_px": 100.0,
                            "height_px": 100.0,
                        },
                        "style": {
                            "font_size_pt": 18.0,
                            "font_color": "#FF0000",
                            "bold": True,
                        },
                    },
                ],
            }
        ],
        "global_props": {
            "width_emu": 9_144_000,
            "height_emu": 6_858_000,
            "width_px": 960.0,
            "height_px": 720.0,
        },
    }


def _two_slide_ppt_state() -> dict[str, Any]:
    """Return a PPTState dict with two slides (1 text box each)."""
    state = _minimal_ppt_state()
    state["slide_count"] = 2
    state["slides"].append(
        {
            "slide_id": "slide-2",
            "page_num": 2,
            "size": {
                "width_emu": 9_144_000,
                "height_emu": 6_858_000,
                "width_px": 960.0,
                "height_px": 720.0,
            },
            "elements": [
                {
                    "element_type": "textbox",
                    "text_id": "text-3",
                    "content": "Slide 2 box",
                    "position": {
                        "x_emu": 0,
                        "y_emu": 0,
                        "x_px": 0.0,
                        "y_px": 0.0,
                    },
                    "size": {
                        "width_emu": 1_000_000,
                        "height_emu": 1_000_000,
                        "width_px": 100.0,
                        "height_px": 100.0,
                    },
                    "style": {
                        "font_size_pt": 14.0,
                        "font_color": "#0000FF",
                        "bold": False,
                    },
                },
            ],
        }
    )
    return state


def _ctx(grants: set[Capability] | None = None, role: str = "editor") -> ToolContext:
    return ToolContext(
        role=role,
        step_id="s1",
        trace_id="t1",
        granted_capabilities=grants or {Capability.READ_TEXT, Capability.WRITE_TEXT},
        timeout_sec=5.0,
    )


# ---------------------------------------------------------------------------
# 1. Schema validation tests
# ---------------------------------------------------------------------------

class TestPPTApplyStyleInputSchema:
    def test_valid_all_fields(self):
        inp = PPTApplyStyleInput(
            font_color="#FFFFFF",
            font_size_multiplier=1.5,
            bold=True,
        )
        assert inp.font_color == "#FFFFFF"
        assert inp.font_size_multiplier == 1.5
        assert inp.bold is True

    def test_valid_defaults(self):
        inp = PPTApplyStyleInput()
        assert inp.font_color is None
        assert inp.font_size_multiplier is None
        assert inp.bold is None

    def test_invalid_font_color(self):
        with pytest.raises(ValidationError):
            PPTApplyStyleInput(font_color="red")


class TestPPTApplyTextInputSchema:
    def test_valid_minimal(self):
        inp = PPTApplyTextInput(instruction="Make it shorter")
        assert inp.instruction == "Make it shorter"
        assert inp.style_hint is None
        assert inp.keep_length_ratio == (0.7, 1.3)

    def test_valid_full(self):
        inp = PPTApplyTextInput(
            instruction="Refine",
            style_hint="professional",
            keep_length_ratio=(0.5, 2.0),
        )
        assert inp.style_hint == "professional"
        assert inp.keep_length_ratio == (0.5, 2.0)

    def test_invalid_keep_length_ratio_type(self):
        with pytest.raises(ValidationError):
            PPTApplyTextInput(instruction="x", keep_length_ratio="0.7,1.3")


class TestPPTInspectSlideInputSchema:
    def test_valid_defaults(self):
        inp = PPTInspectSlideInput()
        assert inp.detail_level == "summary"

    def test_valid_full(self):
        inp = PPTInspectSlideInput(detail_level="full")
        assert inp.detail_level == "full"

    def test_invalid_detail_level(self):
        with pytest.raises(ValidationError):
            PPTInspectSlideInput(detail_level="medium")


# ---------------------------------------------------------------------------
# 2. Behavior tests
# ---------------------------------------------------------------------------

class TestPPTApplyStyleTool:
    @pytest.mark.asyncio
    async def test_applies_style_to_all_textboxes(self):
        tool = PPTApplyStyleTool()
        ppt_state = _minimal_ppt_state()
        params = PPTApplyStyleInput(
            font_color="#00FF00",
            font_size_multiplier=2.0,
            bold=True,
        )

        result = await tool.execute(ppt_state, params, target=None, ctx=_ctx())

        assert isinstance(result, PPTApplyStyleOutput)
        new_state = result.new_state
        summary = result.summary

        # Two text elements should be updated
        elems = new_state["slides"][0]["elements"]
        assert elems[0]["style"]["font_color"] == "#00FF00"
        assert elems[0]["style"]["font_size_pt"] == 24.0  # 12 * 2
        assert elems[0]["style"]["bold"] is True

        assert elems[1]["style"]["font_color"] == "#00FF00"
        assert elems[1]["style"]["font_size_pt"] == 36.0  # 18 * 2
        assert elems[1]["style"]["bold"] is True

        assert summary.get("updated_textboxes") == 2

    @pytest.mark.asyncio
    async def test_does_not_mutate_input_state(self):
        tool = PPTApplyStyleTool()
        ppt_state = _minimal_ppt_state()
        original_color = ppt_state["slides"][0]["elements"][0]["style"]["font_color"]

        params = PPTApplyStyleInput(font_color="#00FF00")
        await tool.execute(ppt_state, params, target=None, ctx=_ctx())

        # Original dict must be untouched
        assert ppt_state["slides"][0]["elements"][0]["style"]["font_color"] == original_color

    @pytest.mark.asyncio
    async def test_partial_style_fields(self):
        tool = PPTApplyStyleTool()
        ppt_state = _minimal_ppt_state()
        params = PPTApplyStyleInput(bold=False)

        result = await tool.execute(ppt_state, params, target=None, ctx=_ctx())
        elems = result.new_state["slides"][0]["elements"]

        # Only bold changed; color and size preserved
        assert elems[0]["style"]["bold"] is False
        assert elems[0]["style"]["font_color"] == "#000000"
        assert elems[0]["style"]["font_size_pt"] == 12.0

    @pytest.mark.asyncio
    async def test_applies_style_to_target_slide_only(self):
        tool = PPTApplyStyleTool()
        ppt_state = _two_slide_ppt_state()
        params = PPTApplyStyleInput(font_color="#00FF00")

        result = await tool.execute(ppt_state, params, target=1, ctx=_ctx())

        new_state = result.new_state
        # Slide 1 mutated (2 text boxes)
        assert new_state["slides"][0]["elements"][0]["style"]["font_color"] == "#00FF00"
        assert new_state["slides"][0]["elements"][1]["style"]["font_color"] == "#00FF00"
        # Slide 2 untouched
        assert new_state["slides"][1]["elements"][0]["style"]["font_color"] == "#0000FF"
        assert result.summary["updated_textboxes"] == 2


class TestPPTApplyTextTool:
    @pytest.mark.asyncio
    async def test_returns_deep_copied_state(self):
        """MVP: LLM refinement is no-op; wiring matters."""
        tool = PPTApplyTextTool()
        ppt_state = _minimal_ppt_state()
        params = PPTApplyTextInput(instruction="Make it shorter")

        result = await tool.execute(ppt_state, params, target=None, ctx=_ctx())

        assert isinstance(result, PPTApplyTextOutput)
        new_state = result.new_state

        # Content unchanged because MVP placeholder
        assert new_state["slides"][0]["elements"][0]["content"] == "Hello World"
        assert new_state["slides"][0]["elements"][1]["content"] == "Second box"

        # But it must be a distinct object (deep copy)
        assert new_state is not ppt_state
        assert new_state["slides"] is not ppt_state["slides"]

    @pytest.mark.asyncio
    async def test_does_not_mutate_input_state(self):
        tool = PPTApplyTextTool()
        ppt_state = _minimal_ppt_state()
        original = copy.deepcopy(ppt_state)

        params = PPTApplyTextInput(instruction="x")
        await tool.execute(ppt_state, params, target=None, ctx=_ctx())

        assert ppt_state == original


class TestPPTInspectSlideTool:
    @pytest.mark.asyncio
    async def test_inspects_slide_summary(self):
        tool = PPTInspectSlideTool()
        ppt_state = _minimal_ppt_state()
        params = PPTInspectSlideInput(detail_level="summary")

        result = await tool.execute(ppt_state, params, target=1, ctx=_ctx())

        assert isinstance(result, PPTInspectSlideOutput)
        assert result.slide_id == "slide-1"
        assert result.full_text == {"text-1": "Hello World", "text-2": "Second box"}
        assert result.style == {"text_boxes": 2, "images": 0}
        assert "style" in result.summary
        assert result.new_state == ppt_state

    @pytest.mark.asyncio
    async def test_inspects_slide_full(self):
        tool = PPTInspectSlideTool()
        ppt_state = _minimal_ppt_state()
        params = PPTInspectSlideInput(detail_level="full")

        result = await tool.execute(ppt_state, params, target=1, ctx=_ctx())

        assert result.slide_id == "slide-1"
        assert result.full_text == {"text-1": "Hello World", "text-2": "Second box"}
        assert "style" in result.summary
        assert result.style["text-1"]["font_color"] == "#000000"

    @pytest.mark.asyncio
    async def test_read_only_returns_same_state(self):
        tool = PPTInspectSlideTool()
        ppt_state = _minimal_ppt_state()
        params = PPTInspectSlideInput()

        result = await tool.execute(ppt_state, params, target=1, ctx=_ctx())

        # Inspect is read-only: new_state should be identical to input
        assert result.new_state == ppt_state

    @pytest.mark.asyncio
    async def test_missing_slide_raises_invalid_target(self):
        tool = PPTInspectSlideTool()
        ppt_state = _minimal_ppt_state()
        params = PPTInspectSlideInput()

        with pytest.raises(ToolExecutionError) as exc:
            await tool.execute(ppt_state, params, target=99, ctx=_ctx())
        assert exc.value.code == "invalid_target"


# ---------------------------------------------------------------------------
# 3. Sandbox / permission tests
# ---------------------------------------------------------------------------

class TestSandboxPermissions:
    @pytest.mark.asyncio
    async def test_style_tool_denied_without_write_style(self):
        tool = PPTApplyStyleTool()
        ctx = _ctx(grants={Capability.READ_TEXT}, role="viewer")

        with pytest.raises(PermissionDeniedError) as exc:
            await sandboxed_execute(
                tool,
                ppt_state=_minimal_ppt_state(),
                params={"font_color": "#FFFFFF"},
                target=None,
                ctx=ctx,
            )
        assert Capability.WRITE_STYLE.value in str(exc.value)

    @pytest.mark.asyncio
    async def test_text_tool_denied_without_write_text(self):
        tool = PPTApplyTextTool()
        ctx = _ctx(grants={Capability.READ_TEXT, Capability.LLM_CALL}, role="assistant")

        with pytest.raises(PermissionDeniedError) as exc:
            await sandboxed_execute(
                tool,
                ppt_state=_minimal_ppt_state(),
                params={"instruction": "refine"},
                target=None,
                ctx=ctx,
            )
        assert Capability.WRITE_TEXT.value in str(exc.value)

    @pytest.mark.asyncio
    async def test_inspect_tool_allowed_with_read_caps(self):
        tool = PPTInspectSlideTool()
        ctx = _ctx(
            grants={Capability.READ_TEXT, Capability.READ_STYLE, Capability.READ_IMAGE},
            role="planner",
        )

        result = await sandboxed_execute(
            tool,
            ppt_state=_minimal_ppt_state(),
            params={},
            target=1,
            ctx=ctx,
        )
        assert result.summary["slide_id"] == "slide-1"


# ---------------------------------------------------------------------------
# 4. Registry wiring test
# ---------------------------------------------------------------------------

class TestBuiltinToolsList:
    def test_all_tools_registered(self):
        names = {t.descriptor.name for t in BUILTIN_TOOLS}
        assert "ppt_apply_style" in names
        assert "ppt_apply_text" in names
        assert "ppt_inspect_slide" in names
        assert len(BUILTIN_TOOLS) == 3


# ---------------------------------------------------------------------------
# 5. Snapshot-style output tests
# ---------------------------------------------------------------------------

class TestSnapshots:
    @pytest.mark.asyncio
    async def test_apply_style_snapshot(self):
        tool = PPTApplyStyleTool()
        ppt_state = _minimal_ppt_state()
        params = PPTApplyStyleInput(font_color="#00FF00", bold=True)

        result = await tool.execute(ppt_state, params, target=None, ctx=_ctx())

        assert result.summary == {"updated_textboxes": 2, "target": None}
        elems = result.new_state["slides"][0]["elements"]
        assert elems[0]["style"]["font_color"] == "#00FF00"
        assert elems[0]["style"]["bold"] is True
        assert elems[1]["style"]["font_color"] == "#00FF00"
        assert elems[1]["style"]["bold"] is True

    @pytest.mark.asyncio
    async def test_apply_text_snapshot(self):
        tool = PPTApplyTextTool()
        ppt_state = _minimal_ppt_state()
        params = PPTApplyTextInput(instruction="Make it shorter")

        result = await tool.execute(ppt_state, params, target=None, ctx=_ctx())

        assert result.summary == {"instruction": "Make it shorter", "refined_boxes": 2}
        assert result.new_state["slides"][0]["elements"][0]["content"] == "Hello World"

    @pytest.mark.asyncio
    async def test_inspect_slide_snapshot(self):
        tool = PPTInspectSlideTool()
        ppt_state = _minimal_ppt_state()
        params = PPTInspectSlideInput(detail_level="summary")

        result = await tool.execute(ppt_state, params, target=1, ctx=_ctx())

        assert result.summary == {
            "slide_id": "slide-1",
            "slide_number": 1,
            "detail_level": "summary",
            "style": {"text_boxes": 2, "images": 0},
        }
        assert result.slide_id == "slide-1"
        assert result.full_text == {"text-1": "Hello World", "text-2": "Second box"}
        assert result.style == {"text_boxes": 2, "images": 0}
