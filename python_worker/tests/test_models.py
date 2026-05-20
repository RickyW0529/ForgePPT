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


def test_large_slide_count_allowed():
    """PPTState should allow up to 50 slides."""
    size = SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0)
    slides = [
        Slide(page_num=i, size=size)
        for i in range(1, 51)
    ]
    state = PPTState(
        source_file="test.pptx",
        slide_count=50,
        global_props=size,
        slides=slides,
    )
    assert state.slide_count == 50
    assert len(state.slides) == 50
    assert state.slides[49].page_num == 50


def test_slide_count_exceeds_max():
    """PPTState should reject more than 50 slides."""
    size = SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0)
    with pytest.raises(ValidationError) as exc_info:
        PPTState(
            source_file="test.pptx",
            slide_count=51,
            global_props=size,
            slides=[
                Slide(page_num=i, size=size)
                for i in range(1, 52)
            ],
        )
    assert "slide_count" in str(exc_info.value) or "slides" in str(exc_info.value) or "page_num" in str(exc_info.value)
