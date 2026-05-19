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
