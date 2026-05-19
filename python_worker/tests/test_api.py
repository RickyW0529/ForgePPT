import asyncio
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from models.ppt_state import PPTState, Position, Size, Slide, SlideSize, TextBox
from workflow.sse_broadcaster import _workflow_events

client = TestClient(app)


def _task_payload() -> dict:
    slide_size = SlideSize(width_emu=9144000, height_emu=5143500, width_px=960.0, height_px=540.0)
    text_box = TextBox(
        text_id="t1",
        content="Original text",
        position=Position(x_emu=0, y_emu=0, x_px=0.0, y_px=0.0),
        size=Size(width_emu=1000000, height_emu=500000, width_px=100.0, height_px=50.0),
    )
    ppt_state = PPTState(
        source_file="test.pptx",
        slide_count=1,
        slides=[Slide(page_num=1, size=slide_size, elements=[text_box])],
        global_props=slide_size,
    )
    return {
        "ppt_state": ppt_state.model_dump(),
        "edit_requests": [
            {"type": "refine", "text_id": "t1", "prompt": "Make it shorter"}
        ],
    }


def test_health_check():
    """Health endpoint should return 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_task():
    """POST /tasks should accept a task payload and return task_id."""
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "export_path": "/tmp/output.pptx",
        "edit_results": [],
    }
    with patch("api.routers.tasks.build_graph", return_value=mock_graph):
        response = client.post("/api/v1/tasks", json=_task_payload())

    assert response.status_code == 202
    data = response.json()
    assert data["success"] is True
    assert "task_id" in data["data"]


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


async def _slow_run(*args, **kwargs):
    await asyncio.sleep(999)


def test_create_workflow_accepted():
    """Valid workflow should return 202 Accepted."""
    with patch("api.routers.workflows._run_workflow", side_effect=_slow_run):
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
    with patch("api.routers.workflows._run_workflow", side_effect=_slow_run):
        resp = client.post("/api/v1/workflows", json={
            "workflow_definition": {
                "workflow_id": "events-test",
                "nodes": [
                    {"id": "upload", "type": "upload", "position": {"x": 0, "y": 0}, "data": {}},
                    {"id": "export", "type": "export", "position": {"x": 0, "y": 0}, "data": {}},
                ],
                "edges": [{"id": "e1", "source": "upload", "target": "export"}]
            },
            "file_path": "/tmp/test.pptx"
        })
        assert resp.status_code == 202

        # Seed the queue with an export-completed event so the SSE generator
        # yields once and then breaks, allowing TestClient to finish reading.
        queue = _workflow_events["events-test"]
        queue.put_nowait({"node_id": "export", "status": "completed"})

        resp = client.get("/api/v1/workflows/events-test/events", headers={"Accept": "text/event-stream"})
        # For MVP the endpoint may immediately close if no active workflow;
        # just verify it doesn't 404 and returns the right content type.
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
