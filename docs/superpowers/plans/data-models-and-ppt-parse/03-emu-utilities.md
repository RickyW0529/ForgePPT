# 03 - EMU Conversion Utilities

**Files:**
- Create: `python_worker/utils/emu.py`
- Create: `python_worker/tests/test_emu.py`

---

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_emu.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_emu.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'utils.emu'"

- [ ] **Step 3: Write minimal implementation**

```python
# python_worker/utils/emu.py
EMU_PER_INCH = 914_400
DEFAULT_DPI = 96


def emu_to_px(emu: int, dpi: int = DEFAULT_DPI) -> float:
    """Convert EMU (English Metric Units) to pixels."""
    return emu / EMU_PER_INCH * dpi


def px_to_emu(px: float, dpi: int = DEFAULT_DPI) -> int:
    """Convert pixels to EMU (English Metric Units)."""
    return int(px / dpi * EMU_PER_INCH)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_emu.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add python_worker/utils/emu.py python_worker/tests/test_emu.py
git commit -m "feat: add EMU/pixel conversion utilities"
```
