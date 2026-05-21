"""Tests for digest builders (Module 3.1)."""

from __future__ import annotations

import pytest

from models.ppt_state import (
    Image,
    Position,
    PPTState,
    Size,
    Slide,
    SlideSize,
    TextBox,
    TextStyle,
)
from agent_platform.context.digests import (
    SlideDigest,
    StateDiffDigest,
    allocate_tier1_budget,
    build_slide_digest,
    compute_state_diff,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slide(page_num: int = 1, elements: list | None = None) -> Slide:
    size = SlideSize(
        width_emu=9_144_000,
        height_emu=6_858_000,
        width_px=960.0,
        height_px=720.0,
    )
    return Slide(
        page_num=page_num,
        size=size,
        elements=elements or [],
    )


def _textbox(
    content: str, text_id: str, font_color: str | None = None
) -> TextBox:
    return TextBox(
        text_id=text_id,
        content=content,
        position=Position(x_emu=0, y_emu=0, x_px=0.0, y_px=0.0),
        size=Size(
            width_emu=1_000_000,
            height_emu=1_000_000,
            width_px=100.0,
            height_px=100.0,
        ),
        style=TextStyle(font_color=font_color),
    )


def _image(image_id: str = "img-1") -> Image:
    return Image(
        image_id=image_id,
        position=Position(x_emu=0, y_emu=0, x_px=0.0, y_px=0.0),
        size=Size(
            width_emu=1_000_000,
            height_emu=1_000_000,
            width_px=100.0,
            height_px=100.0,
        ),
    )


# ---------------------------------------------------------------------------
# SlideDigest
# ---------------------------------------------------------------------------


class TestBuildSlideDigest:
    def test_empty_slide(self):
        slide = _slide(page_num=1)
        digest = build_slide_digest(slide)
        assert isinstance(digest, SlideDigest)
        assert digest.page_num == 1
        assert digest.title == ""
        assert digest.sample_text == ""
        assert digest.text_count == 0
        assert digest.image_count == 0
        assert digest.dominant_colors == []
        assert digest.text_ids == []

    def test_title_from_first_textbox(self):
        slide = _slide(
            page_num=1,
            elements=[_textbox("This is the title of the slide", "t1")],
        )
        digest = build_slide_digest(slide)
        assert digest.title == "This is the title of the slide"
        assert digest.text_count == 1
        assert digest.image_count == 0
        assert digest.text_ids == ["t1"]

    def test_sample_text_truncation(self):
        slide = _slide(
            page_num=1,
            elements=[
                _textbox("First textbox content here", "t1"),
                _textbox("Second textbox content here", "t2"),
                _textbox("Third textbox content here", "t3"),
                _textbox("Fourth textbox content here", "t4"),
            ],
        )
        digest = build_slide_digest(slide, sample_chars=10)
        assert digest.sample_text == "First text | Second tex | Third text"
        assert digest.text_count == 4

    def test_dominant_colors(self):
        slide = _slide(
            page_num=1,
            elements=[
                _textbox("A", "t1", font_color="#000000"),
                _textbox("B", "t2", font_color="#000000"),
                _textbox("C", "t3", font_color="#FF0000"),
                _textbox("D", "t4", font_color="#FF0000"),
                _textbox("E", "t5", font_color="#0000FF"),
            ],
        )
        digest = build_slide_digest(slide)
        assert digest.dominant_colors == ["#000000", "#FF0000"]

    def test_image_count(self):
        slide = _slide(
            page_num=1,
            elements=[
                _textbox("Text", "t1"),
                _image("img-1"),
                _image("img-2"),
            ],
        )
        digest = build_slide_digest(slide)
        assert digest.image_count == 2
        assert digest.text_count == 1


# ---------------------------------------------------------------------------
# StateDiffDigest
# ---------------------------------------------------------------------------


class TestComputeStateDiff:
    def test_identical_states(self):
        before = PPTState(
            source_file="test.pptx",
            slide_count=1,
            slides=[_slide(page_num=1, elements=[_textbox("Hello", "t1")])],
            global_props=SlideSize(
                width_emu=9_144_000,
                height_emu=6_858_000,
                width_px=960.0,
                height_px=720.0,
            ),
        )
        after = before.model_copy(deep=True)
        diff = compute_state_diff(before, after)
        assert isinstance(diff, StateDiffDigest)
        assert diff.pages_changed == []
        assert diff.text_ids_changed == []
        assert diff.style_summary == 0
        assert diff.elements_added == 0
        assert diff.elements_removed == 0

    def test_text_content_changed(self):
        before = PPTState(
            source_file="test.pptx",
            slide_count=1,
            slides=[_slide(page_num=1, elements=[_textbox("Hello", "t1")])],
            global_props=SlideSize(
                width_emu=9_144_000,
                height_emu=6_858_000,
                width_px=960.0,
                height_px=720.0,
            ),
        )
        after = before.model_copy(deep=True)
        after.slides[0].elements[0].content = "World"
        diff = compute_state_diff(before, after)
        assert diff.pages_changed == [1]
        assert diff.text_ids_changed == ["t1"]
        assert diff.style_summary == 0
        assert diff.elements_added == 0
        assert diff.elements_removed == 0

    def test_style_changed(self):
        before = PPTState(
            source_file="test.pptx",
            slide_count=1,
            slides=[
                _slide(
                    page_num=1,
                    elements=[_textbox("Hello", "t1", font_color="#000000")],
                )
            ],
            global_props=SlideSize(
                width_emu=9_144_000,
                height_emu=6_858_000,
                width_px=960.0,
                height_px=720.0,
            ),
        )
        after = before.model_copy(deep=True)
        after.slides[0].elements[0].style.font_color = "#FF0000"
        diff = compute_state_diff(before, after)
        assert diff.pages_changed == [1]
        assert diff.text_ids_changed == []
        assert diff.style_summary == 1
        assert diff.elements_added == 0
        assert diff.elements_removed == 0

    def test_element_added(self):
        before = PPTState(
            source_file="test.pptx",
            slide_count=1,
            slides=[_slide(page_num=1, elements=[_textbox("Hello", "t1")])],
            global_props=SlideSize(
                width_emu=9_144_000,
                height_emu=6_858_000,
                width_px=960.0,
                height_px=720.0,
            ),
        )
        after = before.model_copy(deep=True)
        after.slides[0].elements.append(_textbox("New", "t2"))
        diff = compute_state_diff(before, after)
        assert diff.pages_changed == [1]
        assert diff.text_ids_changed == []
        assert diff.style_summary == 0
        assert diff.elements_added == 1
        assert diff.elements_removed == 0

    def test_element_removed(self):
        before = PPTState(
            source_file="test.pptx",
            slide_count=1,
            slides=[
                _slide(
                    page_num=1,
                    elements=[_textbox("Hello", "t1"), _textbox("World", "t2")],
                )
            ],
            global_props=SlideSize(
                width_emu=9_144_000,
                height_emu=6_858_000,
                width_px=960.0,
                height_px=720.0,
            ),
        )
        after = before.model_copy(deep=True)
        after.slides[0].elements.pop()
        diff = compute_state_diff(before, after)
        assert diff.pages_changed == [1]
        assert diff.text_ids_changed == []
        assert diff.style_summary == 0
        assert diff.elements_added == 0
        assert diff.elements_removed == 1

    def test_multiple_slides(self):
        before = PPTState(
            source_file="test.pptx",
            slide_count=2,
            slides=[
                _slide(page_num=1, elements=[_textbox("Hello", "t1")]),
                _slide(page_num=2, elements=[_textbox("World", "t2")]),
            ],
            global_props=SlideSize(
                width_emu=9_144_000,
                height_emu=6_858_000,
                width_px=960.0,
                height_px=720.0,
            ),
        )
        after = before.model_copy(deep=True)
        after.slides[1].elements[0].content = "Changed"
        diff = compute_state_diff(before, after)
        assert diff.pages_changed == [2]
        assert diff.text_ids_changed == ["t2"]


# ---------------------------------------------------------------------------
# Budget allocation
# ---------------------------------------------------------------------------


class TestAllocateTier1Budget:
    def test_default_budget(self):
        result = allocate_tier1_budget(deck_size=10, scope_size=5)
        assert result["fixed"] == 400
        assert result["tools"] == 300
        assert result["memory"] == 200
        remaining = 2000 - 400 - 300 - 200  # 1100
        assert result["remaining"] == remaining
        assert result["per_slide"] == max(15, remaining // 5)  # 220
        assert result["sample_chars"] == min(60, 220 * 3)  # 60

    def test_small_scope(self):
        result = allocate_tier1_budget(deck_size=10, scope_size=100)
        remaining = 1100
        assert result["per_slide"] == max(15, remaining // 100)  # max(15, 11) = 15
        assert result["sample_chars"] == min(60, 15 * 3)  # 45

    def test_custom_total_budget(self):
        result = allocate_tier1_budget(deck_size=10, scope_size=5, total_budget=3000)
        assert result["fixed"] == 400
        assert result["tools"] == 300
        assert result["memory"] == 200
        remaining = 3000 - 400 - 300 - 200  # 2100
        assert result["remaining"] == remaining
        assert result["per_slide"] == max(15, remaining // 5)  # 420
        assert result["sample_chars"] == min(60, 420 * 3)  # 60

    def test_zero_scope_size(self):
        result = allocate_tier1_budget(deck_size=10, scope_size=0)
        remaining = 1100
        assert result["per_slide"] == max(15, remaining // 1)  # 1100
        assert result["sample_chars"] == min(60, 1100 * 3)  # 60
