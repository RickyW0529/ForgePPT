# 01 - Project Skeleton & Dependencies

**Files:**
- Create: `python_worker/pyproject.toml`
- Create: `python_worker/requirements.txt`
- Create: `python_worker/models/__init__.py`
- Create: `python_worker/services/__init__.py`
- Create: `python_worker/utils/__init__.py`
- Create: `python_worker/tests/__init__.py`
- Create: `python_worker/tests/fixtures/.gitkeep`

---

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_models.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'models'"

- [ ] **Step 3: Write project configuration**

```toml
# python_worker/pyproject.toml
[project]
name = "ppt-agent-worker"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "python-pptx>=1.0.0",
    "pillow>=10.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

```text
# python_worker/requirements.txt
pydantic>=2.0
python-pptx>=1.0.0
pillow>=10.0
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 4: Create empty package files**

```python
# python_worker/models/__init__.py
```

```python
# python_worker/services/__init__.py
```

```python
# python_worker/utils/__init__.py
```

```python
# python_worker/tests/__init__.py
```

- [ ] **Step 5: Run test to verify it still fails (models not yet defined)**

Run: `cd python_worker && pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'models.ppt_state'"

- [ ] **Step 6: Commit**

```bash
git add python_worker/
git commit -m "feat: add python worker project skeleton"
```
