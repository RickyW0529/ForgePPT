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
