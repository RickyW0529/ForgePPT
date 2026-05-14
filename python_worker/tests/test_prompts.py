from llm.prompts import build_refiner_messages, build_svg_messages


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
