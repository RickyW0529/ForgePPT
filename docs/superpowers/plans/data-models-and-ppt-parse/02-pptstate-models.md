# 02 - PPTState Data Models

**Files:**
- Create: `python_worker/models/ppt_state.py`
- Modify: `python_worker/tests/test_models.py`

---

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_models.py
import pytest
from pydantic import ValidationError
from models.ppt_state import (
    PPTState, Slide, SlideSize, TextBox, Image,
    Position, Size, TextStyle
)


def test_ppt_state_round_trip():
    """PPTState should serialize to JSON and back without data loss."""
    state = PPTState(
        source_file="test.pptx",
        slide_count=1,
        global_props=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
        slides=[
            Slide(
                page_num=1,
                size=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
                elements=[
                    TextBox(
                        content="Title slide",
                        position=Position(x_emu=1000000, y_emu=500000, x_px=105.0, y_px=52.5),
                        size=Size(width_emu=7000000, height_emu=1000000, width_px=735.0, height_px=105.0),
                        style=TextStyle(font_size_pt=24.0, font_color="#1A365D", bold=True),
                    )
                ],
            )
        ],
    )
    json_str = state.model_dump_json()
    restored = PPTState.model_validate_json(json_str)
    assert restored.source_file == "test.pptx"
    assert restored.slide_count == 1
    assert len(restored.slides) == 1
    assert restored.slides[0].elements[0].content == "Title slide"
    assert restored.slides[0].elements[0].style.bold is True


def test_invalid_source_file_extension():
    """PPTState should reject non-.pptx source_file."""
    with pytest.raises(ValidationError) as exc_info:
        PPTState(
            source_file="test.pdf",
            slide_count=1,
            global_props=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
        )
    assert "must have .pptx extension" in str(exc_info.value)


def test_slide_count_mismatch():
    """PPTState should reject slide_count that doesn't match slides length."""
    with pytest.raises(ValidationError) as exc_info:
        PPTState(
            source_file="test.pptx",
            slide_count=2,
            global_props=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
            slides=[
                Slide(
                    page_num=1,
                    size=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
                )
            ],
        )
    assert "slide_count=2 but 1 slides" in str(exc_info.value)


def test_element_discriminator():
    """Slide elements should be discriminated by element_type."""
    slide = Slide(
        page_num=1,
        size=SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0),
        elements=[
            {"element_type": "textbox", "content": "Hello", "position": {"x_emu": 0, "y_emu": 0, "x_px": 0.0, "y_px": 0.0}, "size": {"width_emu": 1000000, "height_emu": 500000, "width_px": 100.0, "height_px": 50.0}, "style": {}},
            {"element_type": "image", "position": {"x_emu": 0, "y_emu": 0, "x_px": 0.0, "y_px": 0.0}, "size": {"width_emu": 1000000, "height_emu": 500000, "width_px": 100.0, "height_px": 50.0}},
        ],
    )
    assert slide.elements[0].element_type == "textbox"
    assert slide.elements[1].element_type == "image"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'models.ppt_state'"

- [ ] **Step 3: Write minimal implementation**

```python
# python_worker/models/ppt_state.py
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
    page_num: int = Field(..., ge=1, le=3, description="Original PPTX page number (1-based)")
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
    slide_count: int = Field(..., ge=1, le=3)
    slides: List[Slide] = Field(default_factory=list, max_length=3)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add python_worker/models/ppt_state.py python_worker/tests/test_models.py
git commit -m "feat: add PPTState data models with validation"
```
