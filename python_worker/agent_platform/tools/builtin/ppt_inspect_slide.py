"""Built-in tool: inspect a single slide and return its content and style summary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agent_platform.tools.descriptor import Capability, ToolDescriptor
from agent_platform.tools.sandbox import ToolContext, ToolExecutionError, ToolMetrics, ToolOutput


class PPTInspectSlideInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detail_level: Literal["summary", "full"] = "summary"


class PPTInspectSlideOutput(ToolOutput):
    slide_id: str = ""
    full_text: dict[str, str] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)


class PPTInspectSlideTool:
    descriptor = ToolDescriptor(
        name="ppt_inspect_slide",
        description="Inspect a single slide and return its text content and style summary.",
        input_schema=PPTInspectSlideInput,
        output_schema=PPTInspectSlideOutput,
        capabilities=[Capability.READ_TEXT, Capability.READ_STYLE, Capability.READ_IMAGE],
        side_effects=[],
        timeout_sec=5.0,
    )

    async def execute(
        self,
        ppt_state: dict[str, Any],
        params: PPTInspectSlideInput,
        target: Any,
        ctx: ToolContext,
    ) -> PPTInspectSlideOutput:
        from models.ppt_state import PPTState

        state = PPTState.model_validate(ppt_state)

        if target is None:
            raise ToolExecutionError(
                code="invalid_target",
                message="target slide number is required",
                retryable=False,
                suggested_fix="verify the slide number exists",
            )

        slide = None
        for s in state.slides:
            if s.page_num == target:
                slide = s
                break

        if slide is None:
            raise ToolExecutionError(
                code="invalid_target",
                message=f"Slide number {target} not found",
                retryable=False,
                suggested_fix="verify the slide number exists",
            )

        full_text: dict[str, str] = {}
        style: dict[str, Any] = {}

        for elem in slide.elements:
            if elem.element_type == "textbox":
                full_text[elem.text_id] = elem.content
                if params.detail_level == "full":
                    style[elem.text_id] = elem.style.model_dump(exclude_none=True)

        if params.detail_level == "summary":
            style = {
                "text_boxes": len(full_text),
                "images": sum(1 for e in slide.elements if e.element_type == "image"),
            }

        # Read-only tool: return the original dict unchanged to avoid
        # serialization round-trip differences (e.g. None fields).
        return PPTInspectSlideOutput(
            new_state=ppt_state,
            slide_id=slide.slide_id,
            full_text=full_text,
            style=style,
            summary={
                "slide_id": slide.slide_id,
                "slide_number": target,
                "detail_level": params.detail_level,
                "style": style,
            },
            metrics=ToolMetrics(),
        )
