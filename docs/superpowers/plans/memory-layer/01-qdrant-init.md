# 01 - Qdrant Initialization Script

**Files:**
- Create: `scripts/init_qdrant.py`
- Create: `docker-compose.yml`
- Create: `scripts/__init__.py`

---

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_memory.py
from unittest.mock import MagicMock, patch

import pytest
from memory.client import MemoryClient
from memory.models import PreferenceItem


def test_upsert_preference():
    """Upsert should return a point_id string."""
    mock_qdrant = MagicMock()
    mock_qdrant.scroll_points.return_value = MagicMock(result=[])
    mock_qdrant.upsert_points.return_value = None

    client = MemoryClient(mock_qdrant)
    pref = PreferenceItem(
        user_id="user-1",
        category="tone",
        description="Formal business tone",
        embedding_source="Formal business tone",
    )
    point_id = client.upsert_preference("user-1", pref, [0.1] * 768)
    assert isinstance(point_id, str)
    mock_qdrant.upsert_points.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_memory.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'memory.client'"

- [ ] **Step 3: Write docker-compose.yml**

```yaml
# docker-compose.yml
services:
  qdrant:
    image: qdrant/qdrant:v1.11.0
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_storage:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  qdrant_storage:
```

- [ ] **Step 4: Write init script**

```python
# scripts/init_qdrant.py
import os

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    HnswConfigDiff,
    ScalarQuantization,
    ScalarQuantizationConfig,
    VectorParams,
)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "user_preferences"


def init_collection():
    client = QdrantClient(url=QDRANT_URL)

    if client.collection_exists(COLLECTION_NAME):
        print(f"Collection '{COLLECTION_NAME}' already exists, skipping.")
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=768,
            distance=Distance.COSINE,
            on_disk=True,
        ),
        hnsw_config=HnswConfigDiff(
            m=16,
            ef_construct=128,
            full_scan_threshold=10000,
        ),
        quantization_config=ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                type="int8",
                always_ram=True,
            )
        ),
    )

    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="user_id",
        field_schema={"type": "keyword", "is_tenant": True},
    )
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="preference_type",
        field_schema="keyword",
    )
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="created_at",
        field_schema="integer",
    )
    print(f"Collection '{COLLECTION_NAME}' initialized successfully.")


if __name__ == "__main__":
    init_collection()
```

- [ ] **Step 5: Write Python memory models**

```python
# python_worker/memory/models.py
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class PreferenceItem(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    category: str = Field(..., pattern=r"^(color_scheme|font_style|layout_style|tone)$")
    description: str = Field(..., min_length=1, max_length=500)
    embedding_source: str = Field(..., description="Original text used to generate embedding")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_node: Optional[str] = Field(default=None)
    metadata: Optional[dict] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _sync_embedding_source(self):
        if self.embedding_source != self.description:
            self.embedding_source = self.description
        return self
```

- [ ] **Step 6: Write Python memory client**

```python
# python_worker/memory/client.py
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    PointStruct,
    PointIdsList,
)

from memory.models import PreferenceItem

COLLECTION_NAME = "user_preferences"


class MemoryClient:
    def __init__(self, client: QdrantClient):
        self.client = client

    def upsert_preference(
        self,
        user_id: str,
        preference: PreferenceItem,
        vector: list[float],
    ) -> str:
        """Upsert a preference. Replaces existing same-type preference for the user."""
        existing = self.client.scroll_points(
            collection_name=COLLECTION_NAME,
            filter=Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(
                        key="preference_type", match=MatchValue(value=preference.category)
                    ),
                ]
            ),
            limit=1,
        )

        point_id = str(existing.result[0].id) if existing.result else str(uuid4())

        self.client.upsert_points(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "user_id": user_id,
                        "preference_type": preference.category,
                        "raw_text": preference.description,
                        "created_at": int(preference.created_at.timestamp()),
                        "source_node": preference.source_node,
                        "confidence": preference.confidence,
                        "metadata": preference.metadata,
                    },
                )
            ],
        )
        return point_id

    def search_preferences(
        self,
        user_id: str,
        query_vector: list[float],
        limit: int = 2,
        score_threshold: float = 0.65,
    ) -> list[dict]:
        """Search user preferences by vector similarity."""
        results = self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                ]
            ),
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
            with_vector=False,
        )
        return [
            {
                "id": str(r.id),
                "score": r.score,
                "type": r.payload.get("preference_type"),
                "text": r.payload.get("raw_text"),
                "confidence": r.payload.get("confidence"),
            }
            for r in results
        ]
```

- [ ] **Step 7: Write embedding generator**

```python
# python_worker/memory/embeddings.py
from openai import OpenAI

from config import LLMConfig


def get_embedding(text: str, dimensions: int = 768) -> list[float]:
    """Generate embedding vector for text using OpenAI API."""
    config = LLMConfig()
    client = OpenAI(api_key=config.openai_api_key or None)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        dimensions=dimensions,
    )
    return response.data[0].embedding
```

Note: Add `openai = "^1.35"` to `python_worker/pyproject.toml` dependencies.

- [ ] **Step 8: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_memory.py -v`
Expected: PASS (1 test)

- [ ] **Step 9: Commit**

```bash
git add scripts/ python_worker/memory/ python_worker/tests/test_memory.py docker-compose.yml
git commit -m "feat: add Qdrant memory layer with collection init and Python client"
```
