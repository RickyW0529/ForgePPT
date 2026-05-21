"""In-process working memory (Module 6.2)."""

from __future__ import annotations

from datetime import datetime, timezone

from agent_platform.memory.models import MemoryItem, MemoryQuery, MemoryRecall, MemoryStats


class WorkingMemory:
    """In-process working memory backed by a dict + access-order list.

    Provides exact-match recall by user_id, tags, and text substring.
    Eviction is LRU-based with an optional TTL.
    """

    type = "working"

    def __init__(self, ttl_sec: int = 3600, capacity: int = 200):
        self.ttl_sec = ttl_sec
        self.capacity = capacity
        self._items: dict[str, MemoryItem] = {}
        self._access_order: list[str] = []  # most recent at end

    async def store(self, item: MemoryItem) -> str:
        """Store item in memory. Evict oldest if over capacity."""
        now = datetime.now(timezone.utc)
        await self._evict_expired(now)

        while len(self._items) >= self.capacity:
            if not self._access_order:
                break
            oldest_id = self._access_order.pop(0)
            self._items.pop(oldest_id, None)

        self._items[item.item_id] = item
        if item.item_id in self._access_order:
            self._access_order.remove(item.item_id)
        self._access_order.append(item.item_id)
        return item.item_id

    async def recall(self, query: MemoryQuery) -> list[MemoryRecall]:
        """Exact match by tags + text substring, LRU-ordered. No embedding."""
        now = datetime.now(timezone.utc)
        await self._evict_expired(now)

        matched_ids: list[str] = []
        for item_id in reversed(self._access_order):
            item = self._items[item_id]
            if item.user_id != query.user_id:
                continue
            if query.tags and not all(tag in item.tags for tag in query.tags):
                continue
            if query.text and query.text not in item.content:
                continue
            matched_ids.append(item_id)
            item.accessed_at = now

        # Promote matched items to most-recent position
        for item_id in matched_ids:
            self._access_order.remove(item_id)
            self._access_order.append(item_id)

        return [MemoryRecall(item=self._items[item_id], score=1.0) for item_id in matched_ids]

    async def update(self, item_id: str, patch: dict) -> None:
        """Patch fields of an existing item."""
        if item_id not in self._items:
            raise ValueError(f"item_id '{item_id}' not found")

        updated = self._items[item_id].model_copy(update=patch)
        updated.accessed_at = datetime.now(timezone.utc)
        self._items[item_id] = updated

        self._access_order.remove(item_id)
        self._access_order.append(item_id)

    async def forget(self, item_id: str) -> None:
        """Remove item."""
        self._items.pop(item_id, None)
        if item_id in self._access_order:
            self._access_order.remove(item_id)

    async def stats(self) -> MemoryStats:
        """Return total count and breakdown by type."""
        by_type: dict[str, int] = {}
        for item in self._items.values():
            by_type[item.type] = by_type.get(item.type, 0) + 1
        return MemoryStats(total_items=len(self._items), by_type=by_type)

    async def _evict_expired(self, now: datetime) -> None:
        """Lazy TTL eviction."""
        expired = [
            item_id
            for item_id in list(self._items.keys())
            if self._items[item_id].expires_at is not None
            and self._items[item_id].expires_at < now
        ]
        for item_id in expired:
            await self.forget(item_id)
