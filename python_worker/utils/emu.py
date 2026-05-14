EMU_PER_INCH = 914_400
DEFAULT_DPI = 96


def emu_to_px(emu: int, dpi: int = DEFAULT_DPI) -> float:
    """Convert EMU (English Metric Units) to pixels."""
    return emu / EMU_PER_INCH * dpi


def px_to_emu(px: float, dpi: int = DEFAULT_DPI) -> int:
    """Convert pixels to EMU (English Metric Units)."""
    return int(px / dpi * EMU_PER_INCH)
