from __future__ import annotations

import asyncio
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    PointStruct,
    ScoredPoint,
)


class QdrantVectorStore:
    """Async vector store backed by Qdrant.

    Accepts an existing *sync* ``QdrantClient`` instance and runs blocking
    operations via ``asyncio.to_thread`` so that the public API is fully async.
    """

    def __init__(
        self,
        url: str,
        collection_prefix: str = "fppt",
        client: QdrantClient | None = None,
    ):
        self.collection_prefix = collection_prefix
        self.client = client if client is not None else QdrantClient(url=url)

    def _collection_name(self, collection: str) -> str:
        return f"{self.collection_prefix}_{collection}"

    async def upsert(
        self,
        collection: str,
        item_id: str,
        vector: list[float],
        payload: dict,
    ) -> None:
        point = PointStruct(id=item_id, vector=vector, payload=payload)
        await asyncio.to_thread(
            self.client.upsert,
            collection_name=self._collection_name(collection),
            points=[point],
        )

    async def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
        filter: dict | None = None,
    ) -> list[ScoredPoint]:
        qdrant_filter = self._build_filter(filter) if filter else None
        results = await asyncio.to_thread(
            self.client.query_points,
            collection_name=self._collection_name(collection),
            query=vector,
            query_filter=qdrant_filter,
            limit=top_k,
            with_payload=True,
            with_vector=False,
        )
        return results.points if hasattr(results, "points") else list(results)

    async def delete(self, collection: str, item_id: str) -> None:
        await asyncio.to_thread(
            self.client.delete,
            collection_name=self._collection_name(collection),
            points_selector=[item_id],
        )

    @staticmethod
    def _build_filter(filter_dict: dict) -> Filter:
        """Convert a flat dict of exact-match conditions to a Qdrant Filter."""
        conditions: list[Any] = []
        for key, value in filter_dict.items():
            conditions.append(
                FieldCondition(key=key, match=MatchValue(value=value))
            )
        return Filter(must=conditions)
