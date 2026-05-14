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
