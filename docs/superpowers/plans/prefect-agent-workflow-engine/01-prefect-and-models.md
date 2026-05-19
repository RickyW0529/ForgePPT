### Task 1: Add Prefect Dependency & Define Workflow Models

**Files:**
- Modify: `python_worker/requirements.txt`
- Create: `python_worker/models/workflow_def.py`
- Create: `python_worker/tests/test_workflow_def.py`

---

- [ ] **Step 1: Add Prefect to requirements**

Add `prefect>=3.0` to `python_worker/requirements.txt`. Add it after `langgraph`.

```text
langgraph>=0.2.0
prefect>=3.0
```

Run:
```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker
pip install prefect>=3.0
```

Expected: Prefect installs successfully.

---

- [ ] **Step 2: Write the workflow definition models**

Create `python_worker/models/workflow_def.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Position(BaseModel):
    x: float
    y: float


class WorkflowNode(BaseModel):
    id: str
    type: Literal["upload", "page_allocator", "agent", "merge", "export"]
    position: Position
    data: dict[str, Any]


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str


class AgentNodeConfig(BaseModel):
    role: str
    prompt: str = ""
    temperature: float = Field(0.3, ge=0.0, le=1.0)
    model: str | None = None
    pageScope: list[int] = Field(default_factory=list)


class WorkflowDef(BaseModel):
    workflow_id: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]

    def get_node(self, node_id: str) -> WorkflowNode | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_predecessors(self, node_id: str) -> list[str]:
        return [e.source for e in self.edges if e.target == node_id]

    def get_successors(self, node_id: str) -> list[str]:
        return [e.target for e in self.edges if e.source == node_id]
```

---

- [ ] **Step 3: Write tests for the models**

Create `python_worker/tests/test_workflow_def.py`:

```python
import pytest
from models.workflow_def import WorkflowDef, WorkflowNode, WorkflowEdge, AgentNodeConfig, Position


def test_workflow_def_predecessors():
    wf = WorkflowDef(
        workflow_id="test",
        nodes=[
            WorkflowNode(id="a", type="upload", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="b", type="agent", position=Position(x=0, y=0), data={}),
            WorkflowNode(id="c", type="merge", position=Position(x=0, y=0), data={}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ],
    )
    assert wf.get_predecessors("b") == ["a"]
    assert wf.get_predecessors("c") == ["b"]
    assert wf.get_predecessors("a") == []


def test_agent_node_config_validation():
    config = AgentNodeConfig(role="text_refiner", prompt="Make it better", temperature=0.5)
    assert config.role == "text_refiner"
    assert config.temperature == 0.5


def test_agent_node_config_temperature_out_of_range():
    with pytest.raises(Exception):
        AgentNodeConfig(role="x", temperature=1.5)
```

Run:
```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker
pytest tests/test_workflow_def.py -v
```

Expected: 3 tests pass.

---

- [ ] **Step 4: Commit**

```bash
git add python_worker/requirements.txt python_worker/models/workflow_def.py python_worker/tests/test_workflow_def.py
git commit -m "feat: add Prefect dependency and workflow definition models

Co-Authored-By: Claude <noreply@anthropic.com>"
```
