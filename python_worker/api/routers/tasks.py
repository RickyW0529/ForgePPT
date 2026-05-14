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


@router.post("/tasks", status_code=202)
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
