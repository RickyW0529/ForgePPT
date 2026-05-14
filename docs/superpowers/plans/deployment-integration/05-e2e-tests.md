# 05 - End-to-End Integration Test

**Files:**
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_full_pipeline.py`
- Modify: `.gitignore`

---

- [ ] **Step 1: Write the failing test**

```python
# tests/e2e/conftest.py
import os
import pytest
import requests

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:3000")
PYTHON_URL = os.getenv("PYTHON_URL", "http://localhost:8000")


@pytest.fixture
def gateway():
    return requests.Session()


@pytest.fixture
def python_worker():
    return requests.Session()


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end")
```

```python
# tests/e2e/test_full_pipeline.py
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent.parent / "python_worker" / "tests" / "fixtures"


@pytest.mark.e2e
class TestFullPipeline:
    def test_health_checks(self, gateway, python_worker):
        """Both services should respond to health checks."""
        gw_resp = gateway.get("http://localhost:3000/health")
        assert gw_resp.status_code == 200
        assert gw_resp.json()["status"] == "ok"

        py_resp = python_worker.get("http://localhost:8000/health")
        assert py_resp.status_code == 200

    def test_file_upload_and_parse(self, gateway):
        """Upload a PPTX and verify parsing returns PPTState."""
        fixture = FIXTURES_DIR / "sample.pptx"
        if not fixture.exists():
            pytest.skip("sample.pptx not found")

        with open(fixture, "rb") as f:
            files = {"file": ("sample.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
            resp = gateway.post("http://localhost:3000/api/v1/upload", files=files)

        assert resp.status_code in (200, 202)
        data = resp.json()
        assert "data" in data or "task_id" in data

    def test_create_task(self, gateway):
        """Create an edit task and verify it is accepted."""
        payload = {
            "source_file": "test.pptx",
            "edit_requests": [
                {"type": "refine", "text_id": "t1", "prompt": "Make it shorter"}
            ],
        }
        resp = gateway.post("http://localhost:3000/api/v1/tasks", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert data["success"] is True
        assert "task_id" in data["data"]

    def test_preferences_round_trip(self, gateway):
        """Write a preference and retrieve context."""
        write_resp = gateway.post(
            "http://localhost:3000/api/v1/preferences",
            json={
                "raw_text": "Blue tech style with minimalist icons",
                "preference_type": "layout_style",
            },
            headers={"x-user-id": "e2e-test-user"},
        )
        assert write_resp.status_code == 201

        ctx_resp = gateway.get(
            "http://localhost:3000/api/v1/preferences/context",
            params={"query": "blue minimalist"},
            headers={"x-user-id": "e2e-test-user"},
        )
        assert ctx_resp.status_code == 200
        data = ctx_resp.json()
        assert "preferences" in data
```

- [ ] **Step 2: Add e2e dependencies**

Append to `python_worker/requirements.txt`:

```text
requests>=2.32.0
```

- [ ] **Step 3: Run tests (requires services up)**

Run:
```bash
docker compose up -d
sleep 10  # wait for services to be ready
cd python_worker && pytest ../tests/e2e/ -v -m e2e
```

Expected: Results depend on whether services are fully running. For now, document that E2E tests require `docker compose up`.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/ python_worker/requirements.txt
git commit -m "feat: add end-to-end integration tests"
```
