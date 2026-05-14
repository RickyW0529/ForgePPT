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
