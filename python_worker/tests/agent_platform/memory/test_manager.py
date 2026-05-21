"""Tests for MemoryManager (Module 6.3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.memory.manager import MemoryManager
from agent_platform.memory.models import (
    MemoryConfig,
    MemoryItem,
    MemoryQuery,
    MemoryRecall,
    MemoryStats,
)


@pytest.fixture
def memory_manager():
    config = MemoryConfig()
    working = MagicMock()
    working.type = "working"
    episodic = MagicMock()
    episodic.type = "episodic"
    return MemoryManager(config=config, working=working, episodic=episodic)


@pytest.mark.asyncio
async def test_remember_routes_to_working(memory_manager):
    item = MemoryItem(
        user_id="user-1",
        type="working",
        content="working item",
        source="agent",
    )
    memory_manager.working.store = AsyncMock(return_value=item.item_id)
    memory_manager.episodic.store = AsyncMock()

    result = await memory_manager.remember(item)
    assert result == item.item_id
    memory_manager.working.store.assert_awaited_once_with(item)
    memory_manager.episodic.store.assert_not_awaited()


@pytest.mark.asyncio
async def test_remember_routes_to_episodic(memory_manager):
    item = MemoryItem(
        user_id="user-1",
        type="episodic",
        content="episodic item",
        source="agent",
    )
    memory_manager.episodic.store = AsyncMock(return_value=item.item_id)
    memory_manager.working.store = AsyncMock()

    result = await memory_manager.remember(item)
    assert result == item.item_id
    memory_manager.episodic.store.assert_awaited_once_with(item)
    memory_manager.working.store.assert_not_awaited()


@pytest.mark.asyncio
async def test_remember_raises_on_unsupported_type(memory_manager):
    item = MemoryItem(
        user_id="user-1",
        type="semantic",
        content="semantic item",
        source="agent",
    )
    with pytest.raises(ValueError, match="Unsupported"):
        await memory_manager.remember(item)


@pytest.mark.asyncio
async def test_recall_merges_results(memory_manager):
    item_w = MemoryItem(user_id="user-1", type="working", content="w", source="agent")
    item_e = MemoryItem(user_id="user-1", type="episodic", content="e", source="agent")

    memory_manager.working.recall = AsyncMock(
        return_value=[MemoryRecall(item=item_w, score=0.9)]
    )
    memory_manager.episodic.recall = AsyncMock(
        return_value=[MemoryRecall(item=item_e, score=0.8)]
    )

    results = await memory_manager.recall(MemoryQuery(user_id="user-1"))
    assert len(results) == 2
    assert results[0].score == 0.9
    assert results[1].score == 0.8


@pytest.mark.asyncio
async def test_forget_from_all_types(memory_manager):
    memory_manager.working.forget = AsyncMock()
    memory_manager.episodic.forget = AsyncMock()

    await memory_manager.forget("item-1")
    memory_manager.working.forget.assert_awaited_once_with("item-1")
    memory_manager.episodic.forget.assert_awaited_once_with("item-1")


@pytest.mark.asyncio
async def test_forget_from_specific_type(memory_manager):
    memory_manager.working.forget = AsyncMock()
    memory_manager.episodic.forget = AsyncMock()

    await memory_manager.forget("item-1", memory_type="working")
    memory_manager.working.forget.assert_awaited_once_with("item-1")
    memory_manager.episodic.forget.assert_not_awaited()


@pytest.mark.asyncio
async def test_stats_aggregates(memory_manager):
    memory_manager.working.stats = AsyncMock(
        return_value=MemoryStats(total_items=2, by_type={"working": 2})
    )
    memory_manager.episodic.stats = AsyncMock(
        return_value=MemoryStats(total_items=3, by_type={"episodic": 3})
    )

    stats = await memory_manager.stats()
    assert stats.total_items == 5
    assert stats.by_type == {"working": 2, "episodic": 3}
