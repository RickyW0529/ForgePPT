from unittest.mock import MagicMock

import pytest
from memory.client import MemoryClient
from memory.models import PreferenceItem


def test_upsert_preference():
    """Upsert should return a point_id string."""
    mock_qdrant = MagicMock()
    mock_qdrant.scroll_points.return_value = MagicMock(result=[])
    mock_qdrant.upsert_points.return_value = None

    client = MemoryClient(mock_qdrant)
    pref = PreferenceItem(
        user_id="user-1",
        category="tone",
        description="Formal business tone",
        embedding_source="Formal business tone",
    )
    point_id = client.upsert_preference("user-1", pref, [0.1] * 768)
    assert isinstance(point_id, str)
    mock_qdrant.upsert_points.assert_called_once()
