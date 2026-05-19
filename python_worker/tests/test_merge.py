from models.ppt_state import PPTState, Slide, SlideSize, TextBox, Position, Size, TextStyle
from workflow.merge import detect_modified_pages, merge_states


def _make_state(pages_data: list[str]) -> PPTState:
    """Build a PPTState with one textbox per slide, content from pages_data."""
    slides = []
    for i, content in enumerate(pages_data, start=1):
        textbox = TextBox(
            text_id=f"text-{i}",
            content=content,
            position=Position(x_emu=0, y_emu=0, x_px=0, y_px=0),
            size=Size(width_emu=100, height_emu=50, width_px=100, height_px=50),
            style=TextStyle(font_size_pt=12, font_color="#000000"),
        )
        slide = Slide(
            slide_id=f"slide-{i}",
            page_num=i,
            size=SlideSize(width_emu=9144000, height_emu=5143500, width_px=1280.0, height_px=720.0),
            elements=[textbox],
        )
        slides.append(slide)

    return PPTState(
        source_file="test.pptx",
        slide_count=len(slides),
        slides=slides,
        global_props=SlideSize(width_emu=9144000, height_emu=5143500, width_px=1280.0, height_px=720.0),
    )


def test_detect_modified_pages():
    base = _make_state(["page1", "page2", "page3"])
    modified = _make_state(["page1 changed", "page2", "page3 changed"])
    assert detect_modified_pages(base, modified) == [1, 3]


def test_merge_last_write_wins():
    base = _make_state(["page1", "page2", "page3"])
    branch_a = _make_state(["page1 A", "page2", "page3"])
    branch_b = _make_state(["page1", "page2 B", "page3"])

    merged = merge_states([base, branch_a, branch_b], strategy="last_write_wins")
    assert merged.slides[0].elements[0].content == "page1 A"
    assert merged.slides[1].elements[0].content == "page2 B"
    assert merged.slides[2].elements[0].content == "page3"


def test_merge_error_on_conflict():
    base = _make_state(["page1", "page2", "page3"])
    branch_a = _make_state(["page1 A", "page2", "page3"])
    branch_b = _make_state(["page1 B", "page2", "page3"])

    try:
        merge_states([base, branch_a, branch_b], strategy="error_on_conflict")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Merge conflict: page 1 modified by multiple branches" in str(e)


def test_merge_no_conflict_error_strategy():
    base = _make_state(["page1", "page2", "page3"])
    branch_a = _make_state(["page1 A", "page2", "page3"])
    branch_b = _make_state(["page1", "page2 B", "page3"])

    merged = merge_states([base, branch_a, branch_b], strategy="error_on_conflict")
    assert merged.slides[0].elements[0].content == "page1 A"
    assert merged.slides[1].elements[0].content == "page2 B"
    assert merged.slides[2].elements[0].content == "page3"
