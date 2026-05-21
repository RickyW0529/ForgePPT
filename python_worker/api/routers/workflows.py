import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models.workflow_def import WorkflowDef
from workflow.dag import validate_dag
from workflow.orchestrator import execute_workflow
from workflow.sse_broadcaster import register_workflow, get_event_queue, unregister_workflow

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

    # Validate DAG structure synchronously so client gets immediate feedback
    try:
        validate_dag(workflow_def)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    workflow_id = workflow_def.workflow_id

    # Path traversal guard
    upload_dir = Path("/tmp").resolve()
    real_path = Path(payload.file_path).resolve()
    if not real_path.is_relative_to(upload_dir):
        raise HTTPException(status_code=400, detail="Invalid file path")

    register_workflow(workflow_id)
    _workflow_results[workflow_id] = {"status": "running"}

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
    finally:
        unregister_workflow(workflow_id)


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
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("status") in ("completed", "error") and event.get("node_id") == "export":
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
