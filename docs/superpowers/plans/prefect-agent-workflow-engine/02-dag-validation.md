### Task 2: DAG Validation & Topological Sort

**Files:**
- Create: `python_worker/workflow/dag.py`
- Create: `python_worker/tests/test_dag.py`

---

- [ ] **Step 1: Write the failing test**

Create `python_worker/tests/test_dag.py`:

```python
import pytest
from models.workflow_def import WorkflowDef, WorkflowNode, WorkflowEdge, Position
from workflow.dag import validate_dag, topological_sort


def test_topological_sort_linear():
    wf = WorkflowDef(
        workflow_id="t1",
        nodes=[
            WorkflowNode(id="a", type="upload", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="b", type="agent", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="c", type="export", position=Position(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ],
    )
    result = topological_sort(wf)
    assert result == ["a", "b", "c"]


def test_topological_sort_parallel():
    wf = WorkflowDef(
        workflow_id="t2",
        nodes=[
            WorkflowNode(id="alloc", type="page_allocator", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="left", type="agent", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="right", type="agent", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="merge", type="merge", position=Position(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="alloc", target="left"),
            WorkflowEdge(id="e2", source="alloc", target="right"),
            WorkflowEdge(id="e3", source="left", target="merge"),
            WorkflowEdge(id="e4", source="right", target="merge"),
        ],
    )
    result = topological_sort(wf)
    assert result.index("alloc") < result.index("left")
    assert result.index("alloc") < result.index("right")
    assert result.index("left") < result.index("merge")
    assert result.index("right") < result.index("merge")


def test_validate_dag_cycle_detected():
    wf = WorkflowDef(
        workflow_id="t3",
        nodes=[
            WorkflowNode(id="a", type="upload", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="b", type="agent", position=Position(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="a"),
        ],
    )
    with pytest.raises(ValueError, match="cycle"):
        validate_dag(wf)


def test_validate_dag_missing_upload():
    wf = WorkflowDef(
        workflow_id="t4",
        nodes=[
            WorkflowNode(id="b", type="agent", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="c", type="export", position=Position(x=0, y=0), data={}),
        ],
        edges=[WorkflowEdge(id="e1", source="b", target="c")],
    )
    with pytest.raises(ValueError, match="upload"):
        validate_dag(wf)


def test_validate_dag_missing_export():
    wf = WorkflowDef(
        workflow_id="t5",
        nodes=[
            WorkflowNode(id="a", type="upload", position=Position(x=0, y=0), data={}),
        ],
        edges=[],
    )
    with pytest.raises(ValueError, match="export"):
        validate_dag(wf)


def test_validate_dag_disconnected_subgraph():
    wf = WorkflowDef(
        workflow_id="t6",
        nodes=[
            WorkflowNode(id="a", type="upload", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="b", type="agent", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="c", type="export", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="d", type="agent", position=Position(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ],
    )
    with pytest.raises(ValueError, match="disconnected"):
        validate_dag(wf)
```

---

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker
pytest tests/test_dag.py -v
```

Expected: ImportError or AttributeError for `workflow.dag`.

---

- [ ] **Step 3: Write minimal implementation**

Create `python_worker/workflow/dag.py`:

```python
from collections import deque

from models.workflow_def import WorkflowDef


def validate_dag(wf: WorkflowDef) -> None:
    """Validate workflow DAG constraints.

    Raises:
        ValueError: If DAG is invalid (cycle, missing nodes, disconnected).
    """
    node_ids = {n.id for n in wf.nodes}
    node_types = {n.id: n.type for n in wf.nodes}

    # Exactly one upload
    upload_nodes = [n for n in wf.nodes if n.type == "upload"]
    if len(upload_nodes) != 1:
        raise ValueError(f"Expected exactly one upload node, found {len(upload_nodes)}")

    # At least one export
    export_nodes = [n for n in wf.nodes if n.type == "export"]
    if len(export_nodes) < 1:
        raise ValueError("Expected at least one export node")

    # All edge endpoints exist
    for edge in wf.edges:
        if edge.source not in node_ids:
            raise ValueError(f"Edge references unknown source: {edge.source}")
        if edge.target not in node_ids:
            raise ValueError(f"Edge references unknown target: {edge.target}")

    # Cycle detection (Kahn's algorithm)
    in_degree = {n.id: 0 for n in wf.nodes}
    adj = {n.id: [] for n in wf.nodes}
    for edge in wf.edges:
        adj[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    queue = deque([n for n, d in in_degree.items() if d == 0])
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(wf.nodes):
        raise ValueError("Workflow graph contains a cycle")

    # Disconnected subgraph check: all nodes must be reachable from upload
    upload_id = upload_nodes[0].id
    reachable = set()
    stack = [upload_id]
    while stack:
        cur = stack.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        for succ in wf.get_successors(cur):
            if succ not in reachable:
                stack.append(succ)

    if reachable != node_ids:
        unreachable = node_ids - reachable
        raise ValueError(f"Disconnected subgraph detected: {unreachable}")


def topological_sort(wf: WorkflowDef) -> list[str]:
    """Return a topological ordering of node IDs."""
    in_degree = {n.id: 0 for n in wf.nodes}
    adj = {n.id: [] for n in wf.nodes}
    for edge in wf.edges:
        adj[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    queue = deque([n for n, d in in_degree.items() if d == 0])
    result = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(wf.nodes):
        raise ValueError("Cycle detected during topological sort")
    return result
```

---

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker
pytest tests/test_dag.py -v
```

Expected: 6 tests pass.

---

- [ ] **Step 5: Commit**

```bash
git add python_worker/workflow/dag.py python_worker/tests/test_dag.py
git commit -m "feat: add DAG validation and topological sort

Co-Authored-By: Claude <noreply@anthropic.com>"
```
