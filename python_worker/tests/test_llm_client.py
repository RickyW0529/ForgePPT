from unittest.mock import MagicMock, patch

import pytest
from langchain_core.language_models import BaseChatModel

from llm.client import get_llm_client, TokenUsageCallback


def test_get_llm_client_openai():
    """Factory should return a BaseChatModel for OpenAI."""
    with patch.dict("os.environ", {"PPT_LLM_PROVIDER": "openai", "PPT_OPENAI_API_KEY": "test-key"}):
        client = get_llm_client()
        assert isinstance(client, BaseChatModel)


def test_get_llm_client_unsupported_provider():
    """Factory should raise ValueError for unsupported providers."""
    with patch.dict("os.environ", {"PPT_LLM_PROVIDER": "unknown"}):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_llm_client()


def test_token_usage_callback():
    """TokenUsageCallback should accumulate usage metadata."""
    cb = TokenUsageCallback()
    # Simulate on_llm_end with mock response
    mock_response = MagicMock()
    mock_response.generations = [[MagicMock()]]
    mock_response.generations[0][0].message.usage_metadata = {
        "input_tokens": 100,
        "output_tokens": 50,
    }
    cb.on_llm_end(mock_response)
    total = cb.get_total_usage()
    assert total["total_input"] == 100
    assert total["total_output"] == 50
    assert total["calls_count"] == 1
