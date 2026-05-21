"""Unified memory manager (Module 6.3)."""

from __future__ import annotations

from agent_platform.memory.episodic import EpisodicMemory
from agent_platform.memory.models import MemoryConfig, MemoryItem, MemoryQuery, MemoryRecall, MemoryStats
from agent_platform.memory.working import WorkingMemory


class MemoryManager:
    """Unified entry point for working and episodic memory."""

    def __init__(
        self,
        config: MemoryConfig,
        working: WorkingMemory,
        episodic: EpisodicMemory,
    ):
        self.config = config
        self.working = working
        self.episodic = episodic

    async def remember(self, item: MemoryItem) -> str:
        """Route to the memory type indicated by item.type."""
        if item.type == "working":
            return await self.working.store(item)
        elif item.type == "episodic":
            return await self.episodic.store(item)
        else:
            raise ValueError(f"Unsupported memory type: {item.type}")

    async def recall(
        self,
        query: MemoryQuery,
        across: list[str] | None = None,
    ) -> list[MemoryRecall]:
        """Query across specified memory types and merge-sort by score."""
        across = across or ["working", "episodic"]
        results: list[MemoryRecall] = []
        for memory_type in across:
            if memory_type == "working":
                results.extend(await self.working.recall(query))
            elif memory_type == "episodic":
                results.extend(await self.episodic.recall(query))
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    async def forget(self, item_id: str, memory_type: str | None = None) -> None:
        """Forget from all types if memory_type is None, otherwise from specific type."""
        if memory_type is None:
            await self.working.forget(item_id)
            await self.episodic.forget(item_id)
        elif memory_type == "working":
            await self.working.forget(item_id)
        elif memory_type == "episodic":
            await self.episodic.forget(item_id)
        else:
            raise ValueError(f"Unsupported memory type: {memory_type}")

    async def stats(self) -> MemoryStats:
        """Aggregate stats across all memory types."""
        working_stats = await self.working.stats()
        episodic_stats = await self.episodic.stats()
        total = working_stats.total_items + episodic_stats.total_items
        by_type = dict(working_stats.by_type)
        for k, v in episodic_stats.by_type.items():
            by_type[k] = by_type.get(k, 0) + v
        return MemoryStats(total_items=total, by_type=by_type)
