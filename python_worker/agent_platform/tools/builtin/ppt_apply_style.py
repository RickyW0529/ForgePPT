"""Built-in tool: apply style changes to text boxes in a PPT state."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_platform.tools.descriptor import Capability, SideEffect, ToolDescriptor
from agent_platform.tools.sandbox import ToolContext, ToolMetrics, ToolOutput


class PPTApplyStyleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    font_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Font color as #RRGGBB.",
    )
    font_size_multiplier: float | None = Field(
        default=None,
        gt=0,
        description="Multiplier for existing font sizes.",
    )
    bold: bool | None = Field(default=None)


class PPTApplyStyleOutput(ToolOutput):
    pass


class PPTApplyStyleTool:
    descriptor = ToolDescriptor(
        name="ppt_apply_style",
        description="Apply style changes (font color, size, bold) to text boxes in a PPT state.",
        input_schema=PPTApplyStyleInput,
        output_schema=PPTApplyStyleOutput,
        capabilities=[Capability.READ_STYLE, Capability.WRITE_STYLE],
        side_effects=[
            SideEffect(type="mutate_state", scope="slide", reversible=True)
        ],
        required_role_grants=["theme_designer", "color_optimizer"],
        timeout_sec=10.0,
    )

    async def execute(
        self,
        ppt_state: dict[str, Any],
        params: PPTApplyStyleInput,
        target: Any,
        ctx: ToolContext,
    ) -> PPTApplyStyleOutput:
        from models.ppt_state import PPTState

        state = PPTState.model_validate(ppt_state)
        new_state = state.model_copy(deep=True)

        updated = 0
        for slide in new_state.slides:
            if target is not None and slide.page_num != target:
                continue
            for elem in slide.elements:
                if elem.element_type != "textbox":
                    continue
                if params.font_color is not None:
                    elem.style.font_color = params.font_color.upper()
                if params.font_size_multiplier is not None and elem.style.font_size_pt:
                    elem.style.font_size_pt = round(
                        elem.style.font_size_pt * params.font_size_multiplier, 1
                    )
                if params.bold is not None:
                    elem.style.bold = params.bold
                updated += 1

        return PPTApplyStyleOutput(
            new_state=new_state.model_dump(),
            summary={
                "updated_textboxes": updated,
                "target": target,
            },
            metrics=ToolMetrics(),
        )
