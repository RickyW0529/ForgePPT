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
