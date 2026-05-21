"""Tests for memory models (Module 6.1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agent_platform.memory.models import (
    MemoryConfig,
    MemoryItem,
    MemoryQuery,
    MemoryRecall,
    MemoryStats,
)


def test_memory_item_valid():
    item = MemoryItem(
        user_id="default",
        type="episodic",
        content="User asked for a blue theme",
        source="user_feedback",
    )
    assert item.user_id == "default"
    assert item.type == "episodic"
    assert item.content == "User asked for a blue theme"
    assert item.modality == "text"
    assert item.importance == 0.5
    assert item.confidence == 1.0
    assert item.payload == {}
    assert item.tags == []
    assert item.item_id is not None


def test_memory_item_forbids_extra_fields():
    with pytest.raises(ValidationError):
        MemoryItem(
            user_id="default",
            type="working",
            content="test",
            source="agent",
            unknown_field="bad",
        )


def test_memory_item_type_literal_validation():
    with pytest.raises(ValidationError):
        MemoryItem(
            user_id="default",
            type="invalid_type",  # type: ignore[arg-type]
            content="test",
            source="agent",
        )


def test_memory_item_importance_bounds():
    with pytest.raises(ValidationError):
        MemoryItem(
            user_id="default",
            type="episodic",
            content="test",
            source="agent",
            importance=1.5,
        )
    with pytest.raises(ValidationError):
        MemoryItem(
            user_id="default",
            type="episodic",
            content="test",
            source="agent",
            importance=-0.1,
        )


def test_memory_item_with_all_fields():
    now = datetime.now(timezone.utc)
    item = MemoryItem(
        item_id="uuid-123",
        user_id="default",
        workflow_id="wf-1",
        type="working",
        content="test content",
        payload={"key": "value"},
        modality="text",
        embedding=[0.1] * 768,
        embedding_model="text-embedding-3-small",
        tags=["tag1", "tag2"],
        importance=0.8,
        confidence=0.95,
        created_at=now,
        accessed_at=now,
        expires_at=now,
        source="agent_observation",
    )
    assert item.workflow_id == "wf-1"
    assert item.payload == {"key": "value"}
    assert item.embedding == [0.1] * 768
    assert item.tags == ["tag1", "tag2"]


def test_memory_config_defaults():
    cfg = MemoryConfig()
    assert cfg.working_ttl_sec == 3600
    assert cfg.working_capacity == 200
    assert cfg.episodic_retention_days == 90
    assert cfg.semantic_min_confidence == 0.7
    assert cfg.embedding_dim == 768
    assert cfg.default_top_k == 5
    assert cfg.score_threshold == 0.55


def test_memory_config_forbids_extra():
    with pytest.raises(ValidationError):
        MemoryConfig(unknown=42)  # type: ignore[call-arg]


def test_memory_query_defaults():
    q = MemoryQuery(user_id="default")
    assert q.user_id == "default"
    assert q.text is None
    assert q.tags == []
    assert q.filters == {}
    assert q.top_k == 5
    assert q.score_threshold is None
    assert q.time_range is None


def test_memory_query_forbids_extra():
    with pytest.raises(ValidationError):
        MemoryQuery(user_id="default", extra_field="x")  # type: ignore[call-arg]


def test_memory_recall_valid():
    item = MemoryItem(
        user_id="default",
        type="episodic",
        content="test",
        source="agent",
    )
    recall = MemoryRecall(item=item, score=0.85, explanation="exact match")
    assert recall.score == 0.85
    assert recall.explanation == "exact match"


def test_memory_recall_score_bounds():
    item = MemoryItem(
        user_id="default",
        type="episodic",
        content="test",
        source="agent",
    )
    with pytest.raises(ValidationError):
        MemoryRecall(item=item, score=1.5)
    with pytest.raises(ValidationError):
        MemoryRecall(item=item, score=-0.1)


def test_memory_recall_forbids_extra():
    item = MemoryItem(
        user_id="default",
        type="episodic",
        content="test",
        source="agent",
    )
    with pytest.raises(ValidationError):
        MemoryRecall(item=item, score=0.5, extra="bad")  # type: ignore[call-arg]


def test_memory_stats_valid():
    stats = MemoryStats(total_items=42, by_type={"episodic": 40, "working": 2})
    assert stats.total_items == 42
    assert stats.by_type["episodic"] == 40


def test_memory_stats_forbids_extra():
    with pytest.raises(ValidationError):
        MemoryStats(total_items=1, by_type={}, extra="bad")  # type: ignore[call-arg]
