### Task 6: FastAPI Workflow Routes & SSE Streaming

**Files:**
- Create: `python_worker/api/routers/workflows.py`
- Modify: `python_worker/api/main.py`
- Create: `python_worker/tests/test_api.py`

---

- [ ] **Step 1: Write the failing test**

Create `python_worker/tests/test_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_create_workflow_invalid_dag():
    """Missing upload node should return 400."""
    resp = client.post("/api/v1/workflows", json={
        "workflow_definition": {
            "workflow_id": "bad",
            "nodes": [{"id": "x", "type": "agent", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": []
        },
        "file_path": "/tmp/test.pptx"
    })
    assert resp.status_code == 400
    assert "upload" in resp.json()["detail"].lower()


def test_create_workflow_accepted():
    """Valid workflow should return 202 Accepted."""
    resp = client.post("/api/v1/workflows", json={
        "workflow_definition": {
            "workflow_id": "good",
            "nodes": [
                {"id": "upload", "type": "upload", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "export", "type": "export", "position": {"x": 0, "y": 0}, "data": {}},
            ],
            "edges": [{"id": "e1", "source": "upload", "target": "export"}]
        },
        "file_path": "/tmp/test.pptx"
    })
    assert resp.status_code == 202
    data = resp.json()
    assert data["workflow_id"] == "good"
    assert data["status"] == "running"


def test_get_workflow_not_found():
    resp = client.get("/api/v1/workflows/nonexistent")
    assert resp.status_code == 404


def test_workflow_events_stream():
    """SSE endpoint should return text/event-stream."""
    resp = client.get("/api/v1/workflows/good/events", headers={"Accept": "text/event-stream"})
    # For MVP the endpoint may immediately close if no active workflow;
    # just verify it doesn't 404 and returns the right content type.
    assert resp.status_code in (200, 204)
    if resp.status_code == 200:
        assert "text/event-stream" in resp.headers.get("content-type", "")
```

---

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker
pytest tests/test_api.py -v
```

Expected: 404 errors for `/api/v1/workflows` because router is not registered.

---

- [ ] **Step 3: Write workflow API routes**

Create `python_worker/api/routers/workflows.py`:

```python
import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models.workflow_def import WorkflowDef
from workflow.orchestrator import execute_workflow
from workflow.sse_broadcaster import register_workflow, get_event_queue

router = APIRouter()

# In-memory store for MVP
_workflow_results: dict[str, dict] = {}


class WorkflowCreateRequest(BaseModel):
    workflow_definition: dict
    file_path: str


class WorkflowCreateResponse(BaseModel):
    workflow_id: str
    status: str
    message: str


@router.post("/workflows", status_code=202)
async def create_workflow(payload: WorkflowCreateRequest):
    try:
        workflow_def = WorkflowDef.model_validate(payload.workflow_definition)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid workflow definition: {e}")

    workflow_id = workflow_def.workflow_id
    register_workflow(workflow_id)

    # Start workflow execution in background
    asyncio.create_task(_run_workflow(workflow_id, workflow_def, payload.file_path))

    return WorkflowCreateResponse(
        workflow_id=workflow_id,
        status="running",
        message="Workflow execution started",
    )


async def _run_workflow(workflow_id: str, workflow_def: WorkflowDef, file_path: str):
    """Background task that runs the Prefect workflow and stores the result."""
    try:
        export_path = await execute_workflow(workflow_def, file_path)
        _workflow_results[workflow_id] = {
            "status": "completed",
            "export_path": export_path,
        }
    except Exception as e:
        _workflow_results[workflow_id] = {
            "status": "failed",
            "error": str(e),
        }


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    result = _workflow_results.get(workflow_id)
    if not result:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {
        "workflow_id": workflow_id,
        **result,
    }


@router.get("/workflows/{workflow_id}/events")
async def workflow_events(workflow_id: str):
    """SSE stream of workflow node status events."""
    queue = await get_event_queue(workflow_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Workflow not found or not started")

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {event}\n\n"
                if event.get("status") in ("completed", "error") and event.get("node_id") == "export":
                    break
            except asyncio.TimeoutError:
                yield f"data: {{\"type\": \"heartbeat\"}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

---

- [ ] **Step 4: Register router in main.py**

Modify `python_worker/api/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routers import tasks, upload, download, workflows


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    yield


app = FastAPI(
    title="PPT Agent Worker",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(tasks.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(download.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ppt-agent-worker"}
```

---

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/python_worker
pytest tests/test_api.py -v
```

Expected: 4 tests pass.

---

- [ ] **Step 6: Commit**

```bash
git add python_worker/api/routers/workflows.py python_worker/api/main.py python_worker/tests/test_api.py
git commit -m "feat: add workflow API routes and SSE streaming

Co-Authored-By: Claude <noreply@anthropic.com>"
```
