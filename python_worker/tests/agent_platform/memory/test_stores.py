"""Tests for memory storage backends (Module 6.1)."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from agent_platform.memory.stores.qdrant_store import QdrantVectorStore
from agent_platform.memory.stores.sqlite_store import SQLiteDocumentStore


# ---------------------------------------------------------------------------
# SQLiteDocumentStore
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_store():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    store = SQLiteDocumentStore(db_path=path)
    yield store


@pytest.mark.asyncio
async def test_sqlite_insert_and_get(sqlite_store):
    doc = {
        "item_id": "item-1",
        "user_id": "default",
        "workflow_id": "wf-1",
        "type": "episodic",
        "content": "User asked for blue theme",
        "payload": {"theme": "blue"},
        "modality": "text",
        "embedding": [0.1] * 768,
        "embedding_model": "text-embedding-3-small",
        "tags": ["theme", "color"],
        "importance": 0.8,
        "confidence": 0.95,
        "created_at": datetime.now(timezone.utc),
        "accessed_at": datetime.now(timezone.utc),
        "expires_at": None,
        "source": "user_feedback",
    }
    item_id = await sqlite_store.insert(doc)
    assert item_id == "item-1"

    retrieved = await sqlite_store.get("item-1")
    assert retrieved is not None
    assert retrieved["item_id"] == "item-1"
    assert retrieved["user_id"] == "default"
    assert retrieved["content"] == "User asked for blue theme"
    assert retrieved["payload"] == {"theme": "blue"}
    assert retrieved["tags"] == ["theme", "color"]
    assert retrieved["embedding"] == [0.1] * 768
    assert isinstance(retrieved["created_at"], datetime)


@pytest.mark.asyncio
async def test_sqlite_query_and_delete(sqlite_store):
    docs = [
        {
            "item_id": "item-1",
            "user_id": "default",
            "type": "episodic",
            "content": "First event",
            "source": "agent",
            "created_at": datetime.now(timezone.utc),
            "accessed_at": datetime.now(timezone.utc),
        },
        {
            "item_id": "item-2",
            "user_id": "default",
            "type": "working",
            "content": "Second event",
            "source": "agent",
            "created_at": datetime.now(timezone.utc),
            "accessed_at": datetime.now(timezone.utc),
        },
        {
            "item_id": "item-3",
            "user_id": "other",
            "type": "episodic",
            "content": "Third event",
            "source": "user",
            "created_at": datetime.now(timezone.utc),
            "accessed_at": datetime.now(timezone.utc),
        },
    ]
    for doc in docs:
        await sqlite_store.insert(doc)

    # Query by type
    episodic = await sqlite_store.query(where={"type": "episodic"})
    assert len(episodic) == 2

    # Query by user_id
    default_user = await sqlite_store.query(where={"user_id": "default"})
    assert len(default_user) == 2

    # Query with limit
    limited = await sqlite_store.query(limit=1)
    assert len(limited) == 1

    # Query with order_by
    ordered = await sqlite_store.query(order_by="item_id")
    assert ordered[0]["item_id"] == "item-1"

    # Count
    assert await sqlite_store.count() == 3

    # Delete
    await sqlite_store.delete("item-2")
    assert await sqlite_store.count() == 2
    assert await sqlite_store.get("item-2") is None


@pytest.mark.asyncio
async def test_sqlite_insert_requires_item_id(sqlite_store):
    with pytest.raises(ValueError, match="item_id"):
        await sqlite_store.insert({"user_id": "default", "type": "episodic"})


@pytest.mark.asyncio
async def test_sqlite_get_missing_returns_none(sqlite_store):
    assert await sqlite_store.get("nonexistent") is None


# ---------------------------------------------------------------------------
# QdrantVectorStore
# ---------------------------------------------------------------------------


class _FakeQueryResponse:
    def __init__(self, points):
        self.points = points


@pytest.fixture
def mock_qdrant_client():
    client = MagicMock()
    client.upsert.return_value = None
    client.delete.return_value = None

    fake_hit = MagicMock()
    fake_hit.id = "point-1"
    fake_hit.score = 0.92
    fake_hit.payload = {"content": "hello"}
    client.query_points.return_value = _FakeQueryResponse(points=[fake_hit])
    return client


@pytest.mark.asyncio
async def test_qdrant_upsert(mock_qdrant_client):
    store = QdrantVectorStore(client=mock_qdrant_client)
    await store.upsert(
        collection="fppt_episodic",
        item_id="point-1",
        vector=[0.1] * 768,
        payload={"user_id": "default"},
    )
    mock_qdrant_client.upsert.assert_called_once()
    call_kwargs = mock_qdrant_client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == "fppt_episodic"
    assert len(call_kwargs["points"]) == 1
    assert call_kwargs["points"][0].id == "point-1"


@pytest.mark.asyncio
async def test_qdrant_search(mock_qdrant_client):
    store = QdrantVectorStore(client=mock_qdrant_client)
    results = await store.search(
        collection="fppt_episodic",
        vector=[0.1] * 768,
        top_k=5,
        filter={"user_id": "default"},
    )
    assert len(results) == 1
    mock_qdrant_client.query_points.assert_called_once()
    call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
    assert call_kwargs["collection_name"] == "fppt_episodic"
    assert call_kwargs["limit"] == 5
    assert call_kwargs["with_payload"] is True


@pytest.mark.asyncio
async def test_qdrant_delete(mock_qdrant_client):
    store = QdrantVectorStore(client=mock_qdrant_client)
    await store.delete(collection="fppt_episodic", item_id="point-1")
    mock_qdrant_client.delete.assert_called_once()
    call_kwargs = mock_qdrant_client.delete.call_args.kwargs
    assert call_kwargs["collection_name"] == "fppt_episodic"
