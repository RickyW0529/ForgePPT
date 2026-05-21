"""Tests for WorkingMemory (Module 6.2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agent_platform.memory.models import MemoryItem, MemoryQuery, MemoryRecall
from agent_platform.memory.working import WorkingMemory


@pytest.fixture
def working_memory():
    return WorkingMemory(ttl_sec=3600, capacity=10)


@pytest.mark.asyncio
async def test_store_and_recall(working_memory):
    item = MemoryItem(
        user_id="user-1",
        type="working",
        content="Hello world",
        source="agent",
        tags=["greeting"],
    )
    await working_memory.store(item)

    results = await working_memory.recall(MemoryQuery(user_id="user-1"))
    assert len(results) == 1
    assert results[0].item.content == "Hello world"
    assert results[0].score == 1.0


@pytest.mark.asyncio
async def test_capacity_eviction(working_memory):
    working_memory.capacity = 2
    items = [
        MemoryItem(
            user_id="user-1", type="working", content=f"item-{i}", source="agent"
        )
        for i in range(3)
    ]
    for item in items:
        await working_memory.store(item)

    results = await working_memory.recall(MemoryQuery(user_id="user-1"))
    assert len(results) == 2
    contents = {r.item.content for r in results}
    assert "item-0" not in contents


@pytest.mark.asyncio
async def test_tag_filtering(working_memory):
    items = [
        MemoryItem(
            user_id="user-1", type="working", content="A", source="agent", tags=["x"]
        ),
        MemoryItem(
            user_id="user-1",
            type="working",
            content="B",
            source="agent",
            tags=["x", "y"],
        ),
        MemoryItem(
            user_id="user-1", type="working", content="C", source="agent", tags=["y"]
        ),
    ]
    for item in items:
        await working_memory.store(item)

    results = await working_memory.recall(MemoryQuery(user_id="user-1", tags=["x"]))
    assert len(results) == 2
    contents = {r.item.content for r in results}
    assert contents == {"A", "B"}


@pytest.mark.asyncio
async def test_text_substring_filtering(working_memory):
    items = [
        MemoryItem(
            user_id="user-1",
            type="working",
            content="The quick brown fox",
            source="agent",
        ),
        MemoryItem(
            user_id="user-1", type="working", content="Lazy dog", source="agent"
        ),
    ]
    for item in items:
        await working_memory.store(item)

    results = await working_memory.recall(MemoryQuery(user_id="user-1", text="fox"))
    assert len(results) == 1
    assert results[0].item.content == "The quick brown fox"


@pytest.mark.asyncio
async def test_update(working_memory):
    item = MemoryItem(
        user_id="user-1", type="working", content="Original", source="agent"
    )
    await working_memory.store(item)

    await working_memory.update(item.item_id, {"content": "Updated"})

    results = await working_memory.recall(MemoryQuery(user_id="user-1"))
    assert len(results) == 1
    assert results[0].item.content == "Updated"


@pytest.mark.asyncio
async def test_update_missing_raises(working_memory):
    with pytest.raises(ValueError, match="not found"):
        await working_memory.update("nonexistent", {"content": "x"})


@pytest.mark.asyncio
async def test_forget(working_memory):
    item = MemoryItem(
        user_id="user-1", type="working", content="Forget me", source="agent"
    )
    await working_memory.store(item)

    await working_memory.forget(item.item_id)

    results = await working_memory.recall(MemoryQuery(user_id="user-1"))
    assert len(results) == 0


@pytest.mark.asyncio
async def test_stats(working_memory):
    items = [
        MemoryItem(user_id="user-1", type="working", content="w1", source="agent"),
        MemoryItem(user_id="user-1", type="working", content="w2", source="agent"),
        MemoryItem(user_id="user-1", type="episodic", content="e1", source="agent"),
    ]
    for item in items:
        await working_memory.store(item)

    stats = await working_memory.stats()
    assert stats.total_items == 3
    assert stats.by_type["working"] == 2
    assert stats.by_type["episodic"] == 1


@pytest.mark.asyncio
async def test_ttl_expiration(working_memory):
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    item = MemoryItem(
        user_id="user-1",
        type="working",
        content="Expired",
        source="agent",
        expires_at=past,
    )
    await working_memory.store(item)

    results = await working_memory.recall(MemoryQuery(user_id="user-1"))
    assert len(results) == 0

    stats = await working_memory.stats()
    assert stats.total_items == 0
