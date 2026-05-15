from __future__ import annotations

from typing import List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EditRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal["refine", "placeholder", "theme"]
    text_id: Optional[str] = None
    prompt: str = Field(..., min_length=1)
    style_hint: Optional[str] = None


class EditResult(BaseModel):
    request_id: str
    status: Literal["completed", "failed", "filtered"] = "completed"
    new_content: Optional[str] = None
    svg_xml: Optional[str] = None
    error: Optional[str] = None


class RefinerOutput(BaseModel):
    refined_text: str = Field(..., description="Final refined text content")
    change_summary: str = Field(..., description="Brief summary of changes made")


class SVGOutput(BaseModel):
    svg_xml: str = Field(
        ...,
        description="Complete SVG XML string, without markdown code block markers",
    )
    description: str = Field(..., description="Brief description of generated image")


class ThemeOutput(BaseModel):
    color_palette: list[str] = Field(
        ...,
        description="List of text colors in #RRGGBB format to apply cyclically",
    )
    font_size_multiplier: float = Field(
        1.0,
        description="Multiplier for all font sizes, e.g. 1.1 for 10% larger",
    )
    make_bold: bool = Field(False, description="Whether to make all text bold")
    change_summary: str = Field(..., description="Summary of the style changes")


class GraphState(dict):
    """TypedDict-like state container for LangGraph.

    Inherits from dict for LangGraph compatibility while providing
    typed access helpers.
    """

    @classmethod
    def create(
        cls,
        ppt_state: Optional[dict] = None,
        edit_requests: Optional[List[dict]] = None,
        edit_results: Optional[List[dict]] = None,
        export_path: Optional[str] = None,
        error: Optional[str] = None,
    ) -> "GraphState":
        return cls(
            ppt_state=ppt_state,
            edit_requests=edit_requests or [],
            edit_results=edit_results or [],
            export_path=export_path,
            error=error,
        )
