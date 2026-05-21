"""Tests for EpisodicMemory (Module 6.2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.memory.episodic import EpisodicMemory
from agent_platform.memory.models import MemoryItem
from agent_platform.memory.stores.sqlite_store import SQLiteDocumentStore


@pytest.fixture
def sqlite_store(tmp_path):
    return SQLiteDocumentStore(db_path=str(tmp_path / "memory.db"))


@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.upsert = AsyncMock()
    store.delete = AsyncMock()
    return store


@pytest.fixture
def episodic_memory(sqlite_store, mock_vector_store):
    return EpisodicMemory(
        doc_store=sqlite_store,
        vector_store=mock_vector_store,
        collection="episodic",
    )


@pytest.mark.asyncio
async def test_store_and_get(episodic_memory, sqlite_store):
    item = MemoryItem(
        user_id="user-1",
        type="episodic",
        content="An event",
        source="agent",
    )
    item_id = await episodic_memory.store(item)
    assert item_id == item.item_id

    doc = await sqlite_store.get(item.item_id, table="episodic")
    assert doc is not None
    assert doc["content"] == "An event"
    assert doc["type"] == "episodic"


@pytest.mark.asyncio
async def test_store_with_embedding(episodic_memory, mock_vector_store):
    item = MemoryItem(
        user_id="user-1",
        type="episodic",
        content="An event",
        source="agent",
        embedding=[0.1] * 768,
    )
    await episodic_memory.store(item)

    mock_vector_store.upsert.assert_awaited_once()
    call_kwargs = mock_vector_store.upsert.await_args.kwargs
    assert call_kwargs["collection"] == "episodic"
    assert call_kwargs["item_id"] == item.item_id
    assert call_kwargs["vector"] == [0.1] * 768
    assert call_kwargs["payload"] == {"user_id": "user-1"}


@pytest.mark.asyncio
async def test_forget_removes_from_both(episodic_memory, sqlite_store, mock_vector_store):
    item = MemoryItem(
        user_id="user-1",
        type="episodic",
        content="Delete me",
        source="agent",
        embedding=[0.1] * 768,
    )
    await episodic_memory.store(item)
    await episodic_memory.forget(item.item_id)

    assert await sqlite_store.get(item.item_id, table="episodic") is None
    mock_vector_store.delete.assert_awaited_once_with("episodic", item.item_id)


@pytest.mark.asyncio
async def test_stats(episodic_memory):
    for i in range(3):
        item = MemoryItem(
            user_id="user-1",
            type="episodic",
            content=f"event-{i}",
            source="agent",
        )
        await episodic_memory.store(item)

    stats = await episodic_memory.stats()
    assert stats.total_items == 3
    assert stats.by_type["episodic"] == 3


@pytest.mark.asyncio
async def test_recall_returns_empty(episodic_memory):
    query = MagicMock()
    results = await episodic_memory.recall(query)
    assert results == []


@pytest.mark.asyncio
async def test_update_patches_fields(episodic_memory, sqlite_store, mock_vector_store):
    item = MemoryItem(
        user_id="user-1",
        type="episodic",
        content="Original",
        source="agent",
    )
    await episodic_memory.store(item)

    await episodic_memory.update(item.item_id, {"content": "Updated", "importance": 0.9})

    doc = await sqlite_store.get(item.item_id, table="episodic")
    assert doc["content"] == "Updated"
    assert doc["importance"] == 0.9
    mock_vector_store.upsert.assert_not_awaited()
    mock_vector_store.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_embedding_updates_qdrant(episodic_memory, sqlite_store, mock_vector_store):
    item = MemoryItem(
        user_id="user-1",
        type="episodic",
        content="Original",
        source="agent",
        embedding=[0.1] * 768,
    )
    await episodic_memory.store(item)
    mock_vector_store.reset_mock()

    await episodic_memory.update(
        item.item_id, {"embedding": [0.2] * 768}
    )

    doc = await sqlite_store.get(item.item_id, table="episodic")
    assert doc["embedding"] == [0.2] * 768
    mock_vector_store.delete.assert_awaited_once_with("episodic", item.item_id)
    mock_vector_store.upsert.assert_awaited_once()
    call_kwargs = mock_vector_store.upsert.await_args.kwargs
    assert call_kwargs["vector"] == [0.2] * 768
