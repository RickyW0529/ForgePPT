"""Episodic memory backed by SQLite + Qdrant (Module 6.2)."""

from __future__ import annotations

from agent_platform.memory.models import MemoryItem, MemoryQuery, MemoryRecall, MemoryStats
from agent_platform.memory.stores.qdrant_store import QdrantVectorStore
from agent_platform.memory.stores.sqlite_store import SQLiteDocumentStore


class EpisodicMemory:
    """Episodic memory backed by SQLiteDocumentStore and QdrantVectorStore.

    Semantic recall is disabled in MVP and returns an empty list.
    """

    type = "episodic"

    def __init__(
        self,
        doc_store: SQLiteDocumentStore,
        vector_store: QdrantVectorStore,
        collection: str = "episodic",
    ):
        self.doc_store = doc_store
        self.vector_store = vector_store
        self.collection = collection

    async def store(self, item: MemoryItem) -> str:
        """Write to SQLite (full document). If embedding present, also upsert to Qdrant."""
        doc = item.model_dump(mode="json")
        await self.doc_store.insert(doc, table=self.collection)
        if item.embedding is not None:
            await self.vector_store.upsert(
                collection=self.collection,
                item_id=item.item_id,
                vector=item.embedding,
                payload={"user_id": item.user_id},
            )
        return item.item_id

    async def recall(self, query: MemoryQuery) -> list[MemoryRecall]:
        # MVP: recall disabled per plan
        return []

    async def update(self, item_id: str, patch: dict) -> None:
        """Update in SQLite. If embedding changed, also update Qdrant."""
        doc = await self.doc_store.get(item_id, table=self.collection)
        if doc is None:
            raise ValueError(f"item_id '{item_id}' not found")

        doc.update(patch)
        await self.doc_store.delete(item_id, table=self.collection)
        await self.doc_store.insert(doc, table=self.collection)

        if "embedding" in patch:
            await self.vector_store.delete(self.collection, item_id)
            await self.vector_store.upsert(
                collection=self.collection,
                item_id=item_id,
                vector=patch["embedding"],
                payload={"user_id": doc.get("user_id")},
            )

    async def forget(self, item_id: str) -> None:
        """Delete from both SQLite and Qdrant."""
        await self.doc_store.delete(item_id, table=self.collection)
        await self.vector_store.delete(self.collection, item_id)

    async def stats(self) -> MemoryStats:
        """Count items in SQLite."""
        count = await self.doc_store.count(table=self.collection)
        return MemoryStats(total_items=count, by_type={"episodic": count})
