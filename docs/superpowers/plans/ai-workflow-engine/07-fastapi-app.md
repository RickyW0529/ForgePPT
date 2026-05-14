# 07 - FastAPI Application Skeleton

**Files:**
- Create: `python_worker/api/main.py`
- Create: `python_worker/api/routers/tasks.py`
- Create: `python_worker/api/routers/__init__.py`
- Create: `python_worker/tests/test_api.py`

---

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_api.py
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_check():
    """Health endpoint should return 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_task():
    """POST /tasks should accept a task payload and return task_id."""
    payload = {
        "source_file": "test.pptx",
        "edit_requests": [
            {"type": "refine", "text_id": "t1", "prompt": "Make it shorter"}
        ],
    }
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["success"] is True
    assert "task_id" in data["data"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_api.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'api.main'"

- [ ] **Step 3: Write minimal implementation**

```python
# python_worker/api/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routers import tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="PPT Agent Worker",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(tasks.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ppt-agent-worker"}
```

```python
# python_worker/api/routers/tasks.py
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.workflow import EditRequest
from workflow.graph import build_graph

router = APIRouter()


class TaskCreateRequest(BaseModel):
    source_file: str
    edit_requests: list[dict]


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str


@router.post("/tasks")
async def create_task(payload: TaskCreateRequest):
    """Create a new workflow task.

    Returns immediately with a task_id. The actual execution
    is handled asynchronously via the graph engine.
    """
    task_id = str(uuid4())

    # Build edit requests
    try:
        edit_requests = [EditRequest.model_validate(r) for r in payload.edit_requests]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid edit request: {e}")

    # Initialize graph state
    initial_state = {
        "ppt_state": None,
        "edit_requests": [r.model_dump() for r in edit_requests],
        "edit_results": [],
        "export_path": None,
        "error": None,
    }

    # TODO: offload to background task in production
    graph = build_graph()
    # For MVP we invoke synchronously; SSE streaming is handled by Rust gateway
    # result = graph.invoke(initial_state)

    return {
        "success": True,
        "data": {"task_id": task_id, "status": "queued"},
        "request_id": task_id,
    }
```

```python
# python_worker/api/routers/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_api.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add python_worker/api/ python_worker/tests/test_api.py
git commit -m "feat: add FastAPI skeleton with task creation endpoint"
```
