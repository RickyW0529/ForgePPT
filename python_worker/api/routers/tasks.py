from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.ppt_state import PPTState
from models.workflow import EditRequest
from workflow.graph import build_graph

router = APIRouter()


class TaskCreateRequest(BaseModel):
    ppt_state: dict
    edit_requests: list[dict]


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str


@router.post("/tasks", status_code=202)
async def create_task(payload: TaskCreateRequest):
    """Create and execute a workflow task.

    For MVP the graph is invoked synchronously and the final result
    (including export_path) is returned in the response.
    """
    task_id = str(uuid4())

    # Parse PPTState from payload
    try:
        ppt_state = PPTState.model_validate(payload.ppt_state)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid ppt_state: {e}")

    # Build edit requests
    try:
        edit_requests = [EditRequest.model_validate(r) for r in payload.edit_requests]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid edit request: {e}")

    # Initialize graph state
    initial_state = {
        "ppt_state": ppt_state,
        "edit_requests": [r.model_dump() for r in edit_requests],
        "edit_results": [],
        "export_path": None,
        "error": None,
    }

    # Execute graph synchronously (MVP)
    graph = build_graph()
    result = graph.invoke(initial_state)

    return {
        "success": True,
        "data": {
            "task_id": task_id,
            "status": "completed",
            "export_path": result.get("export_path"),
            "edit_results": [r.model_dump() for r in result.get("edit_results", [])],
        },
        "request_id": task_id,
    }
