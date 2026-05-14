import pytest
from utils.emu import emu_to_px, px_to_emu


def test_emu_to_px():
    """EMU to pixel conversion at default 96 DPI."""
    assert emu_to_px(914400) == 96.0
    assert emu_to_px(457200) == 48.0
    assert emu_to_px(0) == 0.0


def test_px_to_emu():
    """Pixel to EMU conversion at default 96 DPI."""
    assert px_to_emu(96.0) == 914400
    assert px_to_emu(48.0) == 457200
    assert px_to_emu(0.0) == 0


def test_round_trip():
    """Converting px -> emu -> px should return the original value."""
    original_px = 123.45
    emu = px_to_emu(original_px)
    recovered_px = emu_to_px(emu)
    assert abs(recovered_px - original_px) < 0.01
