from llm.prompts import build_refiner_messages, build_merge_messages, build_svg_messages


def test_build_ppt_editing_messages_includes_instruction_and_slide_count():
    from llm.prompts import build_ppt_editing_messages

    messages = build_ppt_editing_messages(
        instruction="把第三页整体颜色改成蓝色",
        slide_count=3,
    )

    assert len(messages) == 2
    assert "PPT editing agent" in messages[0].content
    assert "ppt_apply_style" in messages[0].content
    assert "Slide count: 3" in messages[1].content
    assert "把第三页整体颜色改成蓝色" in messages[1].content


def test_refiner_messages_structure():
    """Refiner messages should be a list of System + Human messages."""
    messages = build_refiner_messages("Original text", "Make it shorter")
    assert len(messages) == 2
    assert messages[0].type == "system"
    assert "PPT文案编辑" in messages[0].content or "editor" in messages[0].content.lower()
    assert messages[1].type == "human"
    assert "Original text" in messages[1].content
    assert "Make it shorter" in messages[1].content


def test_svg_messages_structure():
    """SVG messages should be a list of System + Human messages."""
    messages = build_svg_messages("Blue tech icon", "minimalist")
    assert len(messages) == 2
    assert messages[0].type == "system"
    assert "SVG" in messages[0].content or "svg" in messages[0].content
    assert messages[1].type == "human"
    assert "Blue tech icon" in messages[1].content


def test_refiner_with_preferences():
    """Refiner should inject memory preferences into system prompt."""
    prefs = "Prefer concise, bullet-style text."
    messages = build_refiner_messages("Text", "Shorten", memory_preferences=prefs)
    assert prefs in messages[0].content


def test_build_merge_messages_structure():
    """Merge messages should be a list of System + Human messages with non-empty content."""
    messages = build_merge_messages(
        user_prompt="Merge supplementary PPT after slide 3",
        primary_slide_count=5,
        supplementary_counts=[2, 3],
    )
    assert len(messages) == 2
    assert messages[0].type == "system"
    assert messages[1].type == "human"
    assert messages[0].content.strip()
    assert messages[1].content.strip()


def test_build_merge_messages_includes_prompt():
    """User prompt should appear in the human message."""
    prompt = "把辅PPT的第2页插入到主PPT第3页之后"
    messages = build_merge_messages(
        user_prompt=prompt,
        primary_slide_count=5,
        supplementary_counts=[2],
    )
    assert prompt in messages[1].content


def test_build_merge_messages_includes_counts():
    """Slide counts should appear in the human message."""
    messages = build_merge_messages(
        user_prompt="Merge all",
        primary_slide_count=5,
        supplementary_counts=[2, 3],
    )
    assert "5" in messages[1].content
    assert "2" in messages[1].content
    assert "3" in messages[1].content
