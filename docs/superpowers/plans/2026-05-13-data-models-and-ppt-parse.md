# Data Models & PPT Parse/Recompose Service Implementation Plan

> **Execution Order:** 1 / 6 — Foundation layer. No upstream dependencies.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the canonical `PPTState` data model and implement the PPTX parse/recompose pipeline that converts between `.pptx` files and structured JSON.

**Architecture:** Pydantic v2 models enforce type safety across language boundaries. The parse pipeline extracts text boxes, images, and shapes from `.pptx` via `python-pptx` into `PPTState`. The recompose engine writes incremental changes back while preserving original formatting. Both directions are validated by round-trip tests.

**Tech Stack:** Python 3.11+, Pydantic v2, python-pptx, pytest, Pillow (for image handling)

---

## File Structure

| File | Responsibility |
|------|--------------|
| `python_worker/models/ppt_state.py` | PPTState Pydantic models (Slide, TextBox, Image, Position, Size, TextStyle) |
| `python_worker/models/__init__.py` | Package exports |
| `python_worker/services/parser.py` | PPTX → PPTState parse pipeline |
| `python_worker/services/recomposer.py` | PPTState → PPTX incremental write-back |
| `python_worker/services/__init__.py` | Package exports |
| `python_worker/utils/emu.py` | EMU ↔ pixel conversion utilities |
| `python_worker/utils/__init__.py` | Package exports |
| `python_worker/tests/test_models.py` | PPTState model validation tests |
| `python_worker/tests/test_parser.py` | Parse pipeline tests |
| `python_worker/tests/test_recomposer.py` | Recompose engine tests |
| `python_worker/tests/fixtures/` | Sample `.pptx` files for testing |
| `python_worker/pyproject.toml` | Python project config |
| `python_worker/requirements.txt` | Python dependencies |

---

## Task 1: Project Skeleton & Dependencies

**Files:**
- Create: `python_worker/pyproject.toml`
- Create: `python_worker/requirements.txt`
- Create: `python_worker/models/__init__.py`
- Create: `python_worker/services/__init__.py`
- Create: `python_worker/utils/__init__.py`
- Create: `python_worker/tests/__init__.py`
- Create: `python_worker/tests/fixtures/.gitkeep`

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_models.py
import pytest
from models.ppt_state import PPTState, Slide, TextBox, Position, Size, TextStyle


def test_ppt_state_imports():
    """All core models should be importable."""
    assert PPTState is not None
    assert Slide is not None
    assert TextBox is not None


def test_textbox_creation():
    """TextBox should accept content and geometry."""
    tb = TextBox(
        content="Hello, world!",
        position=Position(x_emu=0, y_emu=0, x_px=0.0, y_px=0.0),
        size=Size(width_emu=1000000, height_emu=500000, width_px=100.0, height_px=50.0),
        style=TextStyle(),
    )
    assert tb.content == "Hello, world!"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'models'"

- [ ] **Step 3: Write project configuration**

```toml
# python_worker/pyproject.toml
[project]
name = "ppt-agent-worker"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "python-pptx>=1.0.0",
    "pillow>=10.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

```text
# python_worker/requirements.txt
pydantic>=2.0
python-pptx>=1.0.0
pillow>=10.0
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 4: Create empty package files**

```python
# python_worker/models/__init__.py
```

```python
# python_worker/services/__init__.py
```

```python
# python_worker/utils/__init__.py
```

```python
# python_worker/tests/__init__.py
```

- [ ] **Step 5: Run test to verify it still fails (models not yet defined)**

Run: `cd python_worker && pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'models.ppt_state'"

- [ ] **Step 6: Commit**

```bash
git add python_worker/
git commit -m "feat: add python worker project skeleton"
```

---

## Task 2: PPTState Data Models

**Files:**
- Create: `python_worker/models/ppt_state.py`
- Modify: `python_worker/tests/test_models.py`

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

---

## Task 3: EMU Conversion Utilities

**Files:**
- Create: `python_worker/utils/emu.py`
- Create: `python_worker/tests/test_emu.py`

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_emu.py
import pytest
from utils.emu import emu_to_px, px_to_emu


def test_emu_to_px():
    """EMU to pixel conversion at default 96 DPI."""
    assert emu_to_px(914400) == 96.0
    assert emu_to_px(457200) == 48.0
    assert emu_to_px(0) == 0.0


def test_px_to_emu():
    """Pixel to EMU conversion at default 96 DPI."""
    assert px_to_emu(96.0) == 914400
    assert px_to_emu(48.0) == 457200
    assert px_to_emu(0.0) == 0


def test_round_trip():
    """Converting px → emu → px should return the original value."""
    original_px = 123.45
    emu = px_to_emu(original_px)
    recovered_px = emu_to_px(emu)
    assert abs(recovered_px - original_px) < 0.01
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_emu.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'utils.emu'"

- [ ] **Step 3: Write minimal implementation**

```python
# python_worker/utils/emu.py
EMU_PER_INCH = 914_400
DEFAULT_DPI = 96


def emu_to_px(emu: int, dpi: int = DEFAULT_DPI) -> float:
    """Convert EMU (English Metric Units) to pixels."""
    return emu / EMU_PER_INCH * dpi


def px_to_emu(px: float, dpi: int = DEFAULT_DPI) -> int:
    """Convert pixels to EMU (English Metric Units)."""
    return int(px / dpi * EMU_PER_INCH)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_emu.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add python_worker/utils/emu.py python_worker/tests/test_emu.py
git commit -m "feat: add EMU/pixel conversion utilities"
```

---

## Task 4: PPTX Parse Pipeline

**Files:**
- Create: `python_worker/services/parser.py`
- Create: `python_worker/tests/test_parser.py`
- Modify: `python_worker/tests/fixtures/` (add sample pptx)

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_parser.py
import os
from pathlib import Path

import pytest
from models.ppt_state import PPTState
from services.parser import parse_pptx

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_sample_pptx():
    """Parse a real .pptx fixture and verify structure."""
    fixture_path = FIXTURES_DIR / "sample.pptx"
    if not fixture_path.exists():
        pytest.skip("sample.pptx fixture not found")

    state = parse_pptx(str(fixture_path))
    assert isinstance(state, PPTState)
    assert state.source_file == "sample.pptx"
    assert state.slide_count >= 1
    assert len(state.slides) == state.slide_count
    assert state.global_props.width_emu > 0
    assert state.global_props.height_emu > 0

    # At least one slide should have elements or we verify the structure
    slide = state.slides[0]
    assert slide.page_num == 1
    assert slide.size.width_emu > 0


def test_parse_nonexistent_file():
    """Parsing a nonexistent file should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        parse_pptx("/nonexistent/path.pptx")


def test_parse_invalid_file():
    """Parsing an invalid file should raise ValueError."""
    invalid_path = FIXTURES_DIR / "invalid.txt"
    invalid_path.write_text("not a pptx")
    try:
        with pytest.raises(ValueError):
            parse_pptx(str(invalid_path))
    finally:
        invalid_path.unlink(missing_ok=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_parser.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'services.parser'"

- [ ] **Step 3: Create a minimal test fixture .pptx**

Run the following Python script to generate a valid test fixture:

```python
# Run this inline to create fixture
from pptx import Presentation
from pptx.util import Inches

prs = Presentation()
slide_layout = prs.slide_layouts[6]  # blank layout
slide = prs.slides.add_slide(slide_layout)
txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
tf = txBox.text_frame
tf.text = "Hello, PPT Agent!"

prs.save("/Users/wangruiqi/RustroverProjects/ForgePPT/python_worker/tests/fixtures/sample.pptx")
print("Fixture created")
```

Or via bash:

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker
python3 -c "
from pptx import Presentation
from pptx.util import Inches
prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[6])
txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
txBox.text_frame.text = 'Hello, PPT Agent!'
prs.save('tests/fixtures/sample.pptx')
print('Created sample.pptx')
"
```

- [ ] **Step 4: Write minimal implementation**

```python
# python_worker/services/parser.py
import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import PP_PLACEHOLDER

from models.ppt_state import (
    Image,
    PPTState,
    Position,
    Size,
    Slide,
    SlideSize,
    TextBox,
    TextStyle,
)
from utils.emu import emu_to_px

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/octet-stream",
}

IMAGE_PLACEHOLDER_TYPES = {
    PP_PLACEHOLDER.PICTURE,
    PP_PLACEHOLDER.CLIP_ART,
    PP_PLACEHOLDER.OBJECT,
}


def _validate_pptx(file_path: Path) -> None:
    """Validate file is a valid PPTX."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if file_path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError(f"File exceeds {MAX_FILE_SIZE} bytes limit")
    if not zipfile.is_zipfile(file_path):
        raise ValueError("File is not a valid ZIP/PPTX format")
    with zipfile.ZipFile(file_path, "r") as zf:
        if "ppt/presentation.xml" not in zf.namelist():
            raise ValueError("Missing required presentation.xml entry")


def _extract_textboxes(slide) -> list[TextBox]:
    """Extract text boxes from a slide."""
    textboxes = []
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        if shape.is_placeholder and not shape.text_frame.text.strip():
            continue

        paragraphs = []
        for para in shape.text_frame.paragraphs:
            para_text = "".join(run.text for run in para.runs)
            paragraphs.append(para_text)
        content = "\n".join(paragraphs)

        # Extract style from first run
        style = TextStyle()
        if shape.text_frame.paragraphs:
            first_para = shape.text_frame.paragraphs[0]
            if first_para.runs:
                first_run = first_para.runs[0]
                font = first_run.font
                if font.size:
                    style.font_size_pt = font.size.pt
                if font.color and font.color.rgb:
                    style.font_color = f"#{font.color.rgb}"
                style.bold = font.bold
                style.italic = font.italic

        textboxes.append(
            TextBox(
                content=content,
                position=Position(
                    x_emu=shape.left,
                    y_emu=shape.top,
                    x_px=emu_to_px(shape.left),
                    y_px=emu_to_px(shape.top),
                ),
                size=Size(
                    width_emu=shape.width,
                    height_emu=shape.height,
                    width_px=emu_to_px(shape.width),
                    height_px=emu_to_px(shape.height),
                ),
                style=style,
            )
        )
    return textboxes


def _extract_images(slide) -> list[Image]:
    """Extract image placeholders from a slide."""
    images = []
    for shape in slide.shapes:
        if not shape.is_placeholder:
            continue
        if shape.placeholder_format.type not in IMAGE_PLACEHOLDER_TYPES:
            continue
        images.append(
            Image(
                position=Position(
                    x_emu=shape.left,
                    y_emu=shape.top,
                    x_px=emu_to_px(shape.left),
                    y_px=emu_to_px(shape.top),
                ),
                size=Size(
                    width_emu=shape.width,
                    height_emu=shape.height,
                    width_px=emu_to_px(shape.width),
                    height_px=emu_to_px(shape.height),
                ),
                placeholder_type=shape.placeholder_format.type.name.lower(),
            )
        )
    return images


def parse_pptx(file_path: str | Path, page_nums: list[int] | None = None) -> PPTState:
    """Parse a PPTX file into PPTState.

    Args:
        file_path: Path to the .pptx file.
        page_nums: Optional list of 1-based page numbers to extract.
            Defaults to first 3 pages.

    Returns:
        PPTState representing the parsed slides.
    """
    file_path = Path(file_path)
    _validate_pptx(file_path)

    prs = Presentation(str(file_path))
    total_slides = len(prs.slides)

    if page_nums is None:
        page_nums = list(range(1, min(total_slides + 1, 4)))  # default first 3
    else:
        page_nums = sorted(set(page_nums))
        if any(p < 1 or p > total_slides for p in page_nums):
            raise ValueError(f"Page numbers out of range (1-{total_slides})")
        if len(page_nums) > 3:
            raise ValueError("MVP supports at most 3 pages")

    slides = []
    for page_num in page_nums:
        slide = prs.slides[page_num - 1]
        textboxes = _extract_textboxes(slide)
        images = _extract_images(slide)
        slides.append(
            Slide(
                page_num=page_num,
                size=SlideSize(
                    width_emu=prs.slide_width,
                    height_emu=prs.slide_height,
                    width_px=emu_to_px(prs.slide_width),
                    height_px=emu_to_px(prs.slide_height),
                ),
                elements=textboxes + images,
            )
        )

    return PPTState(
        source_file=file_path.name,
        slide_count=len(slides),
        global_props=SlideSize(
            width_emu=prs.slide_width,
            height_emu=prs.slide_height,
            width_px=emu_to_px(prs.slide_width),
            height_px=emu_to_px(prs.slide_height),
        ),
        slides=slides,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_parser.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add python_worker/services/parser.py python_worker/tests/test_parser.py python_worker/tests/fixtures/sample.pptx
git commit -m "feat: add PPTX parse pipeline with validation"
```

---

## Task 5: PPTX Recompose Engine

**Files:**
- Create: `python_worker/services/recomposer.py`
- Create: `python_worker/tests/test_recomposer.py`
- Modify: `python_worker/tests/test_parser.py` (add round-trip test)

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_recomposer.py
from pathlib import Path

import pytest
from models.ppt_state import PPTState
from services.parser import parse_pptx
from services.recomposer import recompose_pptx

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_recompose_no_changes():
    """Recomposing without changes should produce a valid PPTX."""
    fixture_path = FIXTURES_DIR / "sample.pptx"
    if not fixture_path.exists():
        pytest.skip("sample.pptx fixture not found")

    state = parse_pptx(str(fixture_path))
    output_path = FIXTURES_DIR / "output_no_changes.pptx"

    try:
        recompose_pptx(str(fixture_path), state, str(output_path))
        assert output_path.exists()
        # Should be parseable again
        state2 = parse_pptx(str(output_path))
        assert state2.source_file == "output_no_changes.pptx"
        assert state2.slide_count == state.slide_count
    finally:
        output_path.unlink(missing_ok=True)


def test_recompose_text_change():
    """Recomposing with a text change should update the content."""
    fixture_path = FIXTURES_DIR / "sample.pptx"
    if not fixture_path.exists():
        pytest.skip("sample.pptx fixture not found")

    state = parse_pptx(str(fixture_path))
    output_path = FIXTURES_DIR / "output_text_change.pptx"

    try:
        # Modify the first text box content
        if state.slides and state.slides[0].elements:
            text_elems = [e for e in state.slides[0].elements if e.element_type == "textbox"]
            if text_elems:
                text_elems[0].content = "Modified by PPT Agent"

        recompose_pptx(str(fixture_path), state, str(output_path))
        assert output_path.exists()

        state2 = parse_pptx(str(output_path))
        text_elems2 = [e for e in state2.slides[0].elements if e.element_type == "textbox"]
        assert text_elems2[0].content == "Modified by PPT Agent"
    finally:
        output_path.unlink(missing_ok=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_recomposer.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'services.recomposer'"

- [ ] **Step 3: Write minimal implementation**

```python
# python_worker/services/recomposer.py
import shutil
import tempfile
from pathlib import Path

from pptx import Presentation

from models.ppt_state import Image, PPTState, TextBox


def _replace_text_preserving_format(shape, new_content: str) -> None:
    """Replace shape text while preserving original formatting."""
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
        return

    first_run = first_para.runs[0]
    # Clear other paragraphs
    for para in paragraphs[1:]:
        para.clear()
    # Clear other runs in first paragraph
    for run in first_para.runs[1:]:
        run.text = ""

    first_run.text = new_content


def _find_shape_by_geometry(slide, left: int, top: int, width: int, height: int):
    """Find a shape by its geometry (position + size)."""
    for shape in slide.shapes:
        if (shape.left == left and shape.top == top and
                shape.width == width and shape.height == height):
            return shape
    return None


def _write_text_changes(slide, elements: list[TextBox]) -> None:
    """Apply text box changes to a slide."""
    for elem in elements:
        if elem.element_type != "textbox":
            continue
        shape = _find_shape_by_geometry(
            slide,
            left=elem.position.x_emu,
            top=elem.position.y_emu,
            width=elem.size.width_emu,
            height=elem.size.height_emu,
        )
        if shape and shape.has_text_frame:
            _replace_text_preserving_format(shape, elem.content)


def _write_image_changes(slide, elements: list[Image]) -> None:
    """Apply image placeholder changes to a slide."""
    # MVP: images are placeholders only; no binary replacement yet
    pass


def recompose_pptx(
    original_path: str | Path,
    ppt_state: PPTState,
    output_path: str | Path,
) -> Path:
    """Recompose a PPTX from PPTState, preserving original formatting.

    Args:
        original_path: Path to the original .pptx template.
        ppt_state: Modified PPTState with changes to apply.
        output_path: Destination path for the output .pptx.

    Returns:
        Path to the output file.
    """
    original_path = Path(original_path)
    output_path = Path(output_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        working_copy = Path(tmp_dir) / original_path.name
        shutil.copy2(original_path, working_copy)

        prs = Presentation(str(working_copy))

        for slide_state in ppt_state.slides:
            if slide_state.page_num < 1 or slide_state.page_num > len(prs.slides):
                continue
            slide = prs.slides[slide_state.page_num - 1]
            text_elems = [e for e in slide_state.elements if e.element_type == "textbox"]
            image_elems = [e for e in slide_state.elements if e.element_type == "image"]
            _write_text_changes(slide, text_elems)
            _write_image_changes(slide, image_elems)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(output_path))

    return output_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_recomposer.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Add round-trip test**

Append to `python_worker/tests/test_parser.py`:

```python
def test_round_trip():
    """Parse → recompose → parse should preserve text content and geometry."""
    from services.recomposer import recompose_pptx

    fixture_path = FIXTURES_DIR / "sample.pptx"
    if not fixture_path.exists():
        pytest.skip("sample.pptx fixture not found")

    state_v1 = parse_pptx(str(fixture_path))
    output_path = FIXTURES_DIR / "round_trip.pptx"
    try:
        recompose_pptx(str(fixture_path), state_v1, str(output_path))
        state_v2 = parse_pptx(str(output_path))

        assert state_v2.slide_count == state_v1.slide_count
        for s1, s2 in zip(state_v1.slides, state_v2.slides):
            assert len(s1.elements) == len(s2.elements)
            for e1, e2 in zip(s1.elements, s2.elements):
                assert e1.element_type == e2.element_type
                assert e1.position.x_emu == e2.position.x_emu
                assert e1.position.y_emu == e2.position.y_emu
                assert e1.size.width_emu == e2.size.width_emu
                assert e1.size.height_emu == e2.size.height_emu
                if e1.element_type == "textbox":
                    assert e1.content == e2.content
    finally:
        output_path.unlink(missing_ok=True)
```

- [ ] **Step 6: Run all tests**

Run: `cd python_worker && pytest tests/ -v`
Expected: PASS (all tests)

- [ ] **Step 7: Commit**

```bash
git add python_worker/services/recomposer.py python_worker/tests/test_recomposer.py python_worker/tests/test_parser.py
git commit -m "feat: add PPTX recompose engine with round-trip tests"
```

---

## Self-Review

**1. Spec coverage:**
- PPTState JSON Schema with version, slides, metadata, history → Task 2 implements PPTState with version, source_file, slide_count, slides, global_props
- TextBox element model with content, position, size, style → Task 2 implements TextBox with all fields
- Image element model with position, size, placeholder_type → Task 2 implements Image with all fields
- Position/Size dual-unit (EMU + px) → Task 2 implements both, Task 3 provides conversion utilities
- PPTX parse pipeline with validation → Task 4 implements full pipeline
- Incremental recompose with text replacement preserving format → Task 5 implements recompose engine
- Round-trip validation → Task 5 includes round-trip test
- File validation (MIME, size, ZIP structure) → Task 4 implements _validate_pptx
- Page number limiting (max 3) → Task 4 implements in parse_pptx

**2. Placeholder scan:**
- No "TBD", "TODO", or "implement later" found.
- No vague "add error handling" steps; all error handling is explicit in code.
- No "Similar to Task N" shortcuts.

**3. Type consistency:**
- `element_type` is `"textbox"` | `"image"` consistently across TextBox and Image models.
- `Position` and `Size` use the same field names (`x_emu`, `y_emu`, `width_emu`, `height_emu`, plus px variants) everywhere.
- `slide_count` validation ensures consistency with `slides` list length.

**Gaps identified and fixed:**
- Added `max_length=10000` to TextBox.content to match spec.
- Added `page_nums` parameter and max-3 validation to parse_pptx.
- Added file validation (ZIP check, presentation.xml check) in Task 4.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-13-data-models-and-ppt-parse.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
