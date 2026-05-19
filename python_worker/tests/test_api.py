from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from models.ppt_state import PPTState, Position, Size, Slide, SlideSize, TextBox

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
