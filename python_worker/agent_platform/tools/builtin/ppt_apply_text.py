"""Built-in tool: refine text content in a PPT state (MVP placeholder)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_platform.tools.descriptor import Capability, SideEffect, ToolDescriptor
from agent_platform.tools.sandbox import ToolContext, ToolMetrics, ToolOutput


class PPTApplyTextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instruction: str = Field(..., description="Refinement instruction, e.g. 'Make it shorter'.")
    style_hint: str | None = Field(default=None)
    keep_length_ratio: tuple[float, float] = Field(default=(0.7, 1.3))


class PPTApplyTextOutput(ToolOutput):
    pass


class PPTApplyTextTool:
    descriptor = ToolDescriptor(
        name="ppt_apply_text",
        description="Refine text content in a PPT state using an LLM.",
        input_schema=PPTApplyTextInput,
        output_schema=PPTApplyTextOutput,
        capabilities=[Capability.READ_TEXT, Capability.WRITE_TEXT, Capability.LLM_CALL],
        side_effects=[
            SideEffect(type="mutate_state", scope="slide", reversible=True)
        ],
        required_role_grants=["text_refiner"],
        timeout_sec=30.0,
    )

    async def execute(
        self,
        ppt_state: dict[str, Any],
        params: PPTApplyTextInput,
        target: Any,
        ctx: ToolContext,
    ) -> PPTApplyTextOutput:
        from models.ppt_state import PPTState

        state = PPTState.model_validate(ppt_state)
        new_state = state.model_copy(deep=True)

        # MVP placeholder: LLM refinement is a no-op.
        # Future implementation will iterate target text_ids and call
        # ctx.llm_provider to refine each text box.
        refined_boxes = sum(
            1
            for slide in new_state.slides
            if target is None or slide.page_num == target
            for elem in slide.elements
            if elem.element_type == "textbox"
        )

        return PPTApplyTextOutput(
            new_state=new_state.model_dump(),
            summary={
                "instruction": params.instruction,
                "refined_boxes": refined_boxes,
            },
            metrics=ToolMetrics(),
        )
