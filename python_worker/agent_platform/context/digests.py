"""Digest builders for PPT state summarisation and diffing (Module 3.1)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict

from models.ppt_state import Image, PPTState, Slide, TextBox


class SlideDigest(BaseModel):
    """Lightweight summary of a single slide for planner consumption."""

    model_config = ConfigDict(extra="forbid")
    page_num: int
    title: str
    sample_text: str
    text_count: int
    image_count: int
    dominant_colors: list[str]
    text_ids: list[str]


class StateDiffDigest(BaseModel):
    """Structured diff between two PPTState snapshots."""

    model_config = ConfigDict(extra="forbid")
    pages_changed: list[int]
    text_ids_changed: list[str]
    style_summary: int
    elements_added: int
    elements_removed: int


def build_slide_digest(slide: Slide, sample_chars: int = 60) -> SlideDigest:
    """Summarise a slide into a compact digest."""
    textboxes: list[TextBox] = []
    images: list[Image] = []
    for elem in slide.elements:
        if isinstance(elem, TextBox):
            textboxes.append(elem)
        elif isinstance(elem, Image):
            images.append(elem)

    title = textboxes[0].content[:30] if textboxes else ""
    sample_text = " | ".join(tb.content[:sample_chars] for tb in textboxes[:3])
    text_count = len(textboxes)
    image_count = len(images)

    # Top 2 font colours by frequency
    colors = [tb.style.font_color for tb in textboxes if tb.style.font_color is not None]
    color_counts = Counter(colors)
    dominant_colors = [color for color, _ in color_counts.most_common(2)]

    text_ids = [tb.text_id for tb in textboxes]

    return SlideDigest(
        page_num=slide.page_num,
        title=title,
        sample_text=sample_text,
        text_count=text_count,
        image_count=image_count,
        dominant_colors=dominant_colors,
        text_ids=text_ids,
    )


def compute_state_diff(before: PPTState, after: PPTState) -> StateDiffDigest:
    """Compute a structured diff between two PPTState snapshots."""
    pages_changed: list[int] = []
    text_ids_changed: list[str] = []
    style_summary = 0
    elements_added = 0
    elements_removed = 0

    before_slides = {s.page_num: s for s in before.slides}
    after_slides = {s.page_num: s for s in after.slides}
    all_page_nums = sorted(set(before_slides.keys()) | set(after_slides.keys()))

    for page_num in all_page_nums:
        before_slide = before_slides.get(page_num)
        after_slide = after_slides.get(page_num)

        if before_slide is None or after_slide is None:
            pages_changed.append(page_num)
            if before_slide is None and after_slide is not None:
                elements_added += len(after_slide.elements)
            elif before_slide is not None and after_slide is None:
                elements_removed += len(before_slide.elements)
            continue

        # Index elements by their unique id
        before_elems: dict[str, TextBox | Image] = {}
        after_elems: dict[str, TextBox | Image] = {}

        for elem in before_slide.elements:
            if isinstance(elem, TextBox):
                before_elems[elem.text_id] = elem
            elif isinstance(elem, Image):
                before_elems[elem.image_id] = elem

        for elem in after_slide.elements:
            if isinstance(elem, TextBox):
                after_elems[elem.text_id] = elem
            elif isinstance(elem, Image):
                after_elems[elem.image_id] = elem

        slide_changed = False
        slide_style_changed = False

        before_ids = set(before_elems.keys())
        after_ids = set(after_elems.keys())

        added_ids = after_ids - before_ids
        removed_ids = before_ids - after_ids

        if added_ids:
            elements_added += len(added_ids)
            slide_changed = True
        if removed_ids:
            elements_removed += len(removed_ids)
            slide_changed = True

        for elem_id in before_ids & after_ids:
            b_elem = before_elems[elem_id]
            a_elem = after_elems[elem_id]

            if isinstance(b_elem, TextBox) and isinstance(a_elem, TextBox):
                if b_elem.content != a_elem.content:
                    text_ids_changed.append(elem_id)
                    slide_changed = True
                if b_elem.style != a_elem.style:
                    slide_style_changed = True
                    slide_changed = True
            elif isinstance(b_elem, Image) and isinstance(a_elem, Image):
                if (
                    b_elem.binary_ref != a_elem.binary_ref
                    or b_elem.placeholder_type != a_elem.placeholder_type
                ):
                    slide_changed = True
            else:
                # Element type changed
                slide_changed = True

        if slide_changed:
            pages_changed.append(page_num)
        if slide_style_changed:
            style_summary += 1

    return StateDiffDigest(
        pages_changed=pages_changed,
        text_ids_changed=text_ids_changed,
        style_summary=style_summary,
        elements_added=elements_added,
        elements_removed=elements_removed,
    )


def allocate_tier1_budget(
    deck_size: int, scope_size: int, total_budget: int = 2000
) -> dict[str, Any]:
    """Allocate the Tier-1 context budget across fixed, tools, memory and per-slide."""
    fixed = 400
    tools = 300
    memory = 200
    remaining = total_budget - fixed - tools - memory
    per_slide = max(15, remaining // max(scope_size, 1))
    sample_chars = min(60, per_slide * 3)
    return {
        "fixed": fixed,
        "tools": tools,
        "memory": memory,
        "remaining": remaining,
        "per_slide": per_slide,
        "sample_chars": sample_chars,
    }
