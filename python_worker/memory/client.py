from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    PointStruct,
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
