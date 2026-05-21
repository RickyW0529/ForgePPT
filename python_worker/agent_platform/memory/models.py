from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    model_config = {"extra": "forbid"}

    item_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    workflow_id: str | None = None
    type: Literal["working", "episodic", "semantic", "perceptual"]
    content: str
    payload: dict = {}
    modality: Literal["text", "image", "audio", "mixed"] = "text"
    embedding: list[float] | None = None
    embedding_model: str | None = None
    tags: list[str] = []
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    source: str


class MemoryConfig(BaseModel):
    model_config = {"extra": "forbid"}

    working_ttl_sec: int = 3600
    working_capacity: int = 200
    episodic_retention_days: int = 90
    semantic_min_confidence: float = 0.7
    embedding_dim: int = 768
    default_top_k: int = 5
    score_threshold: float = 0.55


class MemoryQuery(BaseModel):
    model_config = {"extra": "forbid"}

    user_id: str
    text: str | None = None
    tags: list[str] = []
    filters: dict = {}
    top_k: int = 5
    score_threshold: float | None = None
    time_range: tuple[datetime, datetime] | None = None


class MemoryRecall(BaseModel):
    model_config = {"extra": "forbid"}

    item: MemoryItem
    score: float = Field(..., ge=0.0, le=1.0)
    explanation: str | None = None


class MemoryStats(BaseModel):
    model_config = {"extra": "forbid"}

    total_items: int
    by_type: dict[str, int]


class BaseMemory(Protocol):
    """Protocol for memory *type* implementations (WorkingMemory, EpisodicMemory, etc.).

    This is **not** a storage backend interface — stores (SQLiteDocumentStore,
    QdrantVectorStore) expose lower-level primitives (insert, get, query).
    Higher-level memory types satisfy this protocol and orchestrate one or more
    stores to provide unified store/recall/forget semantics.
    """

    type: str

    async def store(self, item: MemoryItem) -> str:
        ...

    async def recall(self, query: MemoryQuery) -> list[MemoryRecall]:
        ...

    async def update(self, item_id: str, patch: dict) -> None:
        ...

    async def forget(self, item_id: str) -> None:
        ...

    async def stats(self) -> MemoryStats:
        ...
