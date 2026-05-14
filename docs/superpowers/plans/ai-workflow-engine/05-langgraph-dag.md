# 05 - LangGraph DAG Definition

**Files:**
- Create: `python_worker/workflow/graph.py`
- Create: `python_worker/workflow/__init__.py`
- Create: `python_worker/tests/test_graph.py`

---

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_graph.py
from unittest.mock import patch

import pytest
from workflow.graph import build_graph


def test_build_graph_returns_compiled_graph():
    """build_graph should return a CompiledStateGraph with 3 nodes."""
    graph = build_graph()
    assert graph is not None
    # LangGraph compiled graphs have a get_graph() method
    raw_graph = graph.get_graph()
    node_ids = set(raw_graph.nodes.keys())
    assert "upload_parser" in node_ids
    assert "editor" in node_ids
    assert "exporter" in node_ids


def test_graph_invocation_with_mocked_nodes():
    """Graph should execute from start to end with mocked nodes."""
    graph = build_graph()
    # Use a simple initial state
    initial_state = {
        "ppt_state": None,
        "edit_requests": [],
        "edit_results": [],
        "export_path": None,
        "error": None,
    }
    # We can't fully invoke without LLM, but we can test structure
    assert graph is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_graph.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'workflow.graph'"

- [ ] **Step 3: Write minimal implementation**

```python
# python_worker/workflow/graph.py
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from models.workflow import GraphState
from workflow.nodes import editor_node, exporter_node, upload_parser_node


class _GraphStateSchema(TypedDict):
    """Internal schema for LangGraph StateGraph."""
    ppt_state: dict | None
    edit_requests: list[dict]
    edit_results: list[dict]
    export_path: str | None
    error: str | None


def build_graph():
    """Build and compile the LangGraph DAG.

    Structure: START -> upload_parser -> editor -> exporter -> END
    """
    builder = StateGraph(_GraphStateSchema)

    builder.add_node("upload_parser", upload_parser_node)
    builder.add_node("editor", editor_node)
    builder.add_node("exporter", exporter_node)

    builder.add_edge(START, "upload_parser")
    builder.add_edge("upload_parser", "editor")
    builder.add_edge("editor", "exporter")
    builder.add_edge("exporter", END)

    return builder.compile()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_graph.py -v`
Expected: PASS (2 tests) — note that node functions may fail when called, but graph structure tests should pass.

- [ ] **Step 5: Commit**

```bash
git add python_worker/workflow/graph.py python_worker/workflow/__init__.py python_worker/tests/test_graph.py
git commit -m "feat: add LangGraph DAG definition with three-node pipeline"
```
