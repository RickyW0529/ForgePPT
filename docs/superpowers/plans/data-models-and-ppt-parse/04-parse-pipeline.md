# 04 - PPTX Parse Pipeline

**Files:**
- Create: `python_worker/services/parser.py`
- Create: `python_worker/tests/test_parser.py`
- Modify: `python_worker/tests/fixtures/` (add sample pptx)

---

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
