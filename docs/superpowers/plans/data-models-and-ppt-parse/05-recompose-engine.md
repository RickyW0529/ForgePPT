# 05 - PPTX Recompose Engine

**Files:**
- Create: `python_worker/services/recomposer.py`
- Create: `python_worker/tests/test_recomposer.py`
- Modify: `python_worker/tests/test_parser.py` (add round-trip test)

---

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
    """Parse -> recompose -> parse should preserve text content and geometry."""
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
