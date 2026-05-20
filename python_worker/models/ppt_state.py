from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class SlideSize(BaseModel):
    width_emu: int = Field(..., ge=1, description="Slide width in EMU")
    height_emu: int = Field(..., ge=1, description="Slide height in EMU")
    width_px: float = Field(..., gt=0, description="Pixel width at 96 DPI")
    height_px: float = Field(..., gt=0, description="Pixel height at 96 DPI")


class Position(BaseModel):
    x_emu: int = Field(..., ge=0, description="Top-left X in EMU")
    y_emu: int = Field(..., ge=0, description="Top-left Y in EMU")
    x_px: float = Field(..., ge=0, description="Top-left X in pixels at 96 DPI")
    y_px: float = Field(..., ge=0, description="Top-left Y in pixels at 96 DPI")


class Size(BaseModel):
    width_emu: int = Field(..., ge=1, description="Width in EMU")
    height_emu: int = Field(..., ge=1, description="Height in EMU")
    width_px: float = Field(..., gt=0, description="Pixel width at 96 DPI")
    height_px: float = Field(..., gt=0, description="Pixel height at 96 DPI")


class TextStyle(BaseModel):
    font_size_pt: Optional[float] = Field(default=None, gt=0, description="Font size in points")
    font_color: Optional[str] = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Font color as #RRGGBB",
    )
    bold: Optional[bool] = Field(default=None)
    italic: Optional[bool] = Field(default=None)
    alignment: Optional[str] = Field(
        default=None,
        pattern=r"^(left|center|right|justify)$",
    )


class TextBox(BaseModel):
    element_type: Literal["textbox"] = "textbox"
    text_id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(default="", max_length=10000)
    position: Position = Field(...)
    size: Size = Field(...)
    style: TextStyle = Field(default_factory=TextStyle)


class Image(BaseModel):
    element_type: Literal["image"] = "image"
    image_id: str = Field(default_factory=lambda: str(uuid4()))
    position: Position = Field(...)
    size: Size = Field(...)
    binary_ref: Optional[str] = Field(
        default=None,
        pattern=r"^file://.+|^https?://.+$",
    )
    placeholder_type: str = Field(default="picture")


class Slide(BaseModel):
    slide_id: str = Field(default_factory=lambda: str(uuid4()))
    page_num: int = Field(..., ge=1, le=50, description="Original PPTX page number (1-based)")
    size: SlideSize = Field(...)
    elements: List[Union[TextBox, Image]] = Field(
        default_factory=list,
        max_length=50,
    )

    @field_validator("elements")
    @classmethod
    def _validate_element_discriminator(cls, v: List[Union[TextBox, Image]]) -> List:
        for elem in v:
            if elem.element_type not in ("textbox", "image"):
                raise ValueError(f"Unknown element_type: {elem.element_type}")
        return v


class PPTState(BaseModel):
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    source_file: str = Field(..., max_length=255)
    slide_count: int = Field(..., ge=1, le=50)
    slides: List[Slide] = Field(default_factory=list, max_length=50)
    global_props: SlideSize = Field(...)

    @model_validator(mode="after")
    def _check_slide_consistency(self):
        if len(self.slides) != self.slide_count:
            raise ValueError(
                f"slide_count={self.slide_count} but {len(self.slides)} slides"
            )
        return self

    @field_validator("source_file")
    @classmethod
    def _validate_extension(cls, v: str) -> str:
        if not v.lower().endswith(".pptx"):
            raise ValueError("source_file must have .pptx extension")
        return v
