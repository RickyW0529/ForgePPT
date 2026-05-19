### Task 5: Prefect Executors & Orchestrator

**Files:**
- Create: `python_worker/workflow/executors.py`
- Create: `python_worker/workflow/orchestrator.py`
- Create: `python_worker/tests/test_orchestrator.py`
- Modify: `python_worker/models/__init__.py`

---

- [ ] **Step 1: Write the failing test**

Create `python_worker/tests/test_orchestrator.py`:

```python
import pytest
from unittest.mock import patch, MagicMock

from models.ppt_state import PPTState, Slide, TextBox
from models.workflow_def import WorkflowDef, WorkflowNode, WorkflowEdge, Position, AgentNodeConfig
from workflow.orchestrator import execute_workflow


def _make_simple_state(content: str = "hello") -> PPTState:
    return PPTState(
        slides=[
            Slide(
                slide_number=1,
                elements=[
                    TextBox(
                        element_type="textbox",
                        text_id="t1",
                        content=content,
                        left=0, top=0, width=100, height=50,
                        font_size=12, font_color="#000000",
                    )
                ],
            )
        ],
        source_file="/tmp/test.pptx",
    )


@pytest.mark.asyncio
async def test_execute_simple_linear_workflow():
    """upload -> agent (theme) -> export"""
    wf = WorkflowDef(
        workflow_id="wf1",
        nodes=[
            WorkflowNode(id="upload", type="upload", position=Position(x=0, y=0), data={}),
            WorkflowNode(
                id="agent",
                type="agent",
                position=Position(x=0, y=0),
                data=AgentNodeConfig(role="theme_designer", prompt="make it blue").model_dump(),
            ),
            WorkflowNode(id="export", type="export", position=Position(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="upload", target="agent"),
            WorkflowEdge(id="e2", source="agent", target="export"),
        ],
    )

    with patch("workflow.executors.parse_pptx") as mock_parse, \
         patch("workflow.executors.recompose_pptx") as mock_recompose, \
         patch("workflow.agent_registry.execute_agent") as mock_agent:

        mock_parse.return_value = _make_simple_state()
        mock_recompose_pptx.return_value = "/tmp/output.pptx"
        mock_agent.return_value = _make_simple_state()

        result = await execute_workflow(wf, "/tmp/test.pptx")
        assert result == "/tmp/output.pptx"
        mock_parse.assert_called_once_with("/tmp/test.pptx")
        mock_recompose.assert_called_once()


@pytest.mark.asyncio
async def test_execute_parallel_branches():
    """upload -> allocator -> [agent_a, agent_b] -> merge -> export"""
    wf = WorkflowDef(
        workflow_id="wf2",
        nodes=[
            WorkflowNode(id="upload", type="upload", position=Position(x=0, y=0), data={}),
            WorkflowNode(
                id="alloc",
                type="page_allocator",
                position=Position(x=0, y=0),
                data={"branches": {"a": [1], "b": [2]}},
            ),
            WorkflowNode(
                id="agent_a",
                type="agent",
                position=Position(x=0, y=0),
                data=AgentNodeConfig(role="text_refiner", prompt="refine").model_dump(),
            ),
            WorkflowNode(
                id="agent_b",
                type="agent",
                position=Position(x=0, y=0),
                data=AgentNodeConfig(role="color_optimizer", prompt="dark blue").model_dump(),
            ),
            WorkflowNode(id="merge", type="merge", position=Position(x=0, y=0), data={"mergeStrategy": "last_write_wins"}),
            WorkflowNode(id="export", type="export", position=Position(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="upload", target="alloc"),
            WorkflowEdge(id="e2a", source="alloc", target="agent_a"),
            WorkflowEdge(id="e2b", source="alloc", target="agent_b"),
            WorkflowEdge(id="e3a", source="agent_a", target="merge"),
            WorkflowEdge(id="e3b", source="agent_b", target="merge"),
            WorkflowEdge(id="e4", source="merge", target="export"),
        ],
    )

    with patch("workflow.executors.parse_pptx") as mock_parse, \
         patch("workflow.executors.recompose_pptx") as mock_recompose, \
         patch("workflow.agent_registry.execute_agent") as mock_agent:

        state = _make_simple_state()
        mock_parse.return_value = state
        mock_recompose.return_value = "/tmp/output.pptx"
        mock_agent.return_value = state

        result = await execute_workflow(wf, "/tmp/test.pptx")
        assert result == "/tmp/output.pptx"
        assert mock_agent.call_count == 2
```

---

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker
pytest tests/test_orchestrator.py -v
```

Expected: ImportError for `workflow.orchestrator`.

---

- [ ] **Step 3: Write shared SSE broadcaster**

Create `python_worker/workflow/sse_broadcaster.py` to avoid circular imports:

```python
import asyncio
from typing import Any

# Global event queue store: workflow_id -> Queue
_workflow_events: dict[str, asyncio.Queue[dict]] = {}


def register_workflow(workflow_id: str) -> None:
    """Register a new workflow for SSE event collection."""
    _workflow_events[workflow_id] = asyncio.Queue()


def broadcast_sse(node_id: str, status: str, **kwargs: Any) -> None:
    """Broadcast a node status event.

    This iterates all active workflows and places the event in their queues.
    In production, use a proper pub/sub system (Redis, etc.).
    """
    event = {"node_id": node_id, "status": status, **kwargs}
    for queue in _workflow_events.values():
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def get_event_queue(workflow_id: str) -> asyncio.Queue[dict] | None:
    """Get the event queue for a workflow."""
    return _workflow_events.get(workflow_id)
```

---

- [ ] **Step 4: Write executor tasks**

Create `python_worker/workflow/executors.py`:

```python
from prefect import task

from models.ppt_state import PPTState
from models.workflow_def import AgentNodeConfig, WorkflowNode
from services.parser import parse_pptx
from services.recomposer import recompose_pptx
from workflow.agent_registry import execute_agent
from workflow.merge import merge_states


from workflow.sse_broadcaster import broadcast_sse


@task(name="{node_id}", retries=1, retry_delay_seconds=5, timeout_seconds=60)
async def run_agent_node(node: WorkflowNode, ppt_state: PPTState, config: AgentNodeConfig) -> PPTState:
    """Execute a single Agent node."""
    broadcast_sse(node.id, "started")
    result = execute_agent(ppt_state, config)
    broadcast_sse(node.id, "completed")
    return result


@task(name="{node_id}")
def run_merge_node(node: WorkflowNode, inputs: list[PPTState], merge_strategy: str) -> PPTState:
    """Merge multiple branch outputs."""
    broadcast_sse(node.id, "started")
    result = merge_states(inputs, strategy=merge_strategy)
    broadcast_sse(node.id, "completed")
    return result


@task(name="{node_id}")
def run_upload_node(node: WorkflowNode, file_path: str) -> PPTState:
    """Parse uploaded PPTX into PPTState."""
    broadcast_sse(node.id, "started")
    result = parse_pptx(file_path)
    broadcast_sse(node.id, "completed")
    return result


@task(name="{node_id}")
def run_export_node(node: WorkflowNode, ppt_state: PPTState) -> str:
    """Recompose PPTX from PPTState."""
    broadcast_sse(node.id, "started")
    output_path = f"/tmp/forgeppt_output_{ppt_state.source_file.replace('/', '_')}"
    recompose_pptx(ppt_state.source_file, ppt_state, output_path)
    broadcast_sse(node.id, "completed", export_path=output_path)
    return output_path


@task(name="{node_id}")
def run_page_allocator_node(node: WorkflowNode, ppt_state: PPTState) -> PPTState:
    """Pure routing node; page scope is carried in downstream edge config."""
    broadcast_sse(node.id, "started")
    broadcast_sse(node.id, "completed")
    return ppt_state
```

---

- [ ] **Step 4: Write orchestrator**

Create `python_worker/workflow/orchestrator.py`:

```python
from prefect import flow
from prefect.futures import PrefectFuture

from models.workflow_def import AgentNodeConfig, WorkflowDef, WorkflowNode
from workflow.dag import topological_sort, validate_dag
from workflow.executors import (
    run_agent_node,
    run_export_node,
    run_merge_node,
    run_page_allocator_node,
    run_upload_node,
)


def _get_export_node_id(nodes: dict[str, WorkflowNode]) -> str:
    exports = [nid for nid, n in nodes.items() if n.type == "export"]
    if not exports:
        raise ValueError("No export node found")
    return exports[0]


@flow(name="forgeppt-workflow")
async def execute_workflow(workflow_def: WorkflowDef, file_path: str) -> str:
    """Dynamically construct and execute a Prefect Flow from user-defined DAG.

    Returns the final export file path.
    """
    validate_dag(workflow_def)

    nodes = {n.id: n for n in workflow_def.nodes}
    topo_order = topological_sort(workflow_def)

    future_cache: dict[str, PrefectFuture] = {}

    for node_id in topo_order:
        node = nodes[node_id]
        preds = workflow_def.get_predecessors(node_id)

        if node.type == "upload":
            future_cache[node_id] = run_upload_node.submit(node, file_path)

        elif node.type == "page_allocator":
            upstream = future_cache[preds[0]]
            future_cache[node_id] = run_page_allocator_node.submit(node, upstream)

        elif node.type == "agent":
            upstream = future_cache[preds[0]]
            config = AgentNodeConfig.model_validate(node.data)
            future_cache[node_id] = run_agent_node.submit(node, upstream, config)

        elif node.type == "merge":
            upstream_futures = [future_cache[p] for p in preds]
            strategy = node.data.get("mergeStrategy", "last_write_wins")
            future_cache[node_id] = run_merge_node.submit(node, upstream_futures, strategy)

        elif node.type == "export":
            upstream = future_cache[preds[0]]
            future_cache[node_id] = run_export_node.submit(node, upstream)

    final_future = future_cache[_get_export_node_id(nodes)]
    return await final_future.result()
```

---

- [ ] **Step 6: Update models __init__.py**

Modify `python_worker/models/__init__.py` to export `WorkflowDef`:

```python
from models.ppt_state import PPTState, Slide, TextBox
from models.workflow_def import (
    AgentNodeConfig,
    Position,
    WorkflowDef,
    WorkflowEdge,
    WorkflowNode,
)

__all__ = [
    "AgentNodeConfig",
    "Position",
    "PPTState",
    "Slide",
    "TextBox",
    "WorkflowDef",
    "WorkflowEdge",
    "WorkflowNode",
]
```

---

- [ ] **Step 7: Run test to verify it passes**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker
pytest tests/test_orchestrator.py -v
```

Expected: 2 tests pass.

---

- [ ] **Step 8: Commit**

```bash
git add python_worker/workflow/sse_broadcaster.py python_worker/workflow/executors.py python_worker/workflow/orchestrator.py python_worker/tests/test_orchestrator.py python_worker/models/__init__.py
git commit -m "feat: add Prefect executors, SSE broadcaster, and dynamic orchestrator

Co-Authored-By: Claude <noreply@anthropic.com>"
```
