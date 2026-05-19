### Task 3: PPTState Merge Logic

**Files:**
- Create: `python_worker/workflow/merge.py`
- Create: `python_worker/tests/test_merge.py`

---

- [ ] **Step 1: Write the failing test**

Create `python_worker/tests/test_merge.py`:

```python
import copy
import pytest
from models.ppt_state import PPTState, Slide, TextBox
from workflow.merge import merge_states, detect_modified_pages


def _make_state(pages_data: dict) -> PPTState:
    """Helper: build PPTState from {page_num: [text_contents]}."""
    slides = []
    for page_num, contents in pages_data.items():
        elements = [
            TextBox(
                element_type="textbox",
                text_id=f"p{page_num}-t{i}",
                content=content,
                left=0, top=0, width=100, height=50,
                font_size=12, font_color="#000000",
            )
            for i, content in enumerate(contents)
        ]
        slides.append(Slide(slide_number=page_num, elements=elements))
    return PPTState(slides=slides, source_file="/tmp/test.pptx")


def test_detect_modified_pages():
    base = _make_state({1: ["hello"], 2: ["world"]})
    modified = copy.deepcopy(base)
    modified.slides[0].elements[0].content = "hello modified"
    assert detect_modified_pages(base, modified) == [1]


def test_merge_last_write_wins():
    base = _make_state({1: ["page1-base"], 2: ["page2-base"]})
    branch_a = copy.deepcopy(base)
    branch_a.slides[0].elements[0].content = "page1-a"
    branch_b = copy.deepcopy(base)
    branch_b.slides[1].elements[0].content = "page2-b"

    result = merge_states([branch_a, branch_b], strategy="last_write_wins")
    assert result.slides[0].elements[0].content == "page1-a"
    assert result.slides[1].elements[0].content == "page2-b"


def test_merge_error_on_conflict():
    base = _make_state({1: ["page1"]})
    branch_a = copy.deepcopy(base)
    branch_a.slides[0].elements[0].content = "page1-a"
    branch_b = copy.deepcopy(base)
    branch_b.slides[0].elements[0].content = "page1-b"

    with pytest.raises(ValueError, match="conflict"):
        merge_states([branch_a, branch_b], strategy="error_on_conflict")


def test_merge_no_conflict_error_strategy():
    base = _make_state({1: ["page1"], 2: ["page2"]})
    branch_a = copy.deepcopy(base)
    branch_a.slides[0].elements[0].content = "page1-a"
    branch_b = copy.deepcopy(base)
    branch_b.slides[1].elements[0].content = "page2-b"

    result = merge_states([branch_a, branch_b], strategy="error_on_conflict")
    assert result.slides[0].elements[0].content == "page1-a"
    assert result.slides[1].elements[0].content == "page2-b"
```

---

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker
pytest tests/test_merge.py -v
```

Expected: ImportError for `workflow.merge`.

---

- [ ] **Step 3: Write minimal implementation**

Create `python_worker/workflow/merge.py`:

```python
import copy
from typing import Literal

from models.ppt_state import PPTState


def detect_modified_pages(base: PPTState, modified: PPTState) -> list[int]:
    """Return list of 1-based page numbers that differ between base and modified."""
    changed = []
    for i, (base_slide, mod_slide) in enumerate(zip(base.slides, modified.slides)):
        if base_slide.model_dump_json() != mod_slide.model_dump_json():
            changed.append(i + 1)
    return changed


def merge_states(
    inputs: list[PPTState],
    strategy: Literal["last_write_wins", "error_on_conflict"] = "last_write_wins",
) -> PPTState:
    """Merge multiple branch outputs into a single PPTState.

    Args:
        inputs: List of PPTStates from upstream branches. The first is the base.
        strategy: How to handle overlapping page modifications.

    Returns:
        Merged PPTState.
    """
    if not inputs:
        raise ValueError("No inputs to merge")

    base = copy.deepcopy(inputs[0])
    base_modified = {p: False for p in range(1, len(base.slides) + 1)}

    for branch_state in inputs[1:]:
        modified_pages = detect_modified_pages(inputs[0], branch_state)
        for page_num in modified_pages:
            if strategy == "error_on_conflict" and base_modified[page_num]:
                raise ValueError(
                    f"Merge conflict: page {page_num} modified by multiple branches"
                )
            base.slides[page_num - 1] = copy.deepcopy(branch_state.slides[page_num - 1])
            base_modified[page_num] = True

    return base
```

---

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker
pytest tests/test_merge.py -v
```

Expected: 4 tests pass.

---

- [ ] **Step 5: Commit**

```bash
git add python_worker/workflow/merge.py python_worker/tests/test_merge.py
git commit -m "feat: add PPTState merge logic with conflict strategies

Co-Authored-By: Claude <noreply@anthropic.com>"
```
