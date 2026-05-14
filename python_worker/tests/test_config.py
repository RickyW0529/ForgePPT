import os

import pytest
from config import LLMConfig


def test_default_config():
    """Default config should use OpenAI gpt-4o-mini."""
    config = LLMConfig()
    assert config.llm_provider == "openai"
    assert config.llm_model == "gpt-4o-mini"
    assert config.llm_temperature == 0.3


def test_env_override():
    """Environment variables should override defaults."""
    os.environ["PPT_LLM_MODEL"] = "gpt-4o"
    os.environ["PPT_LLM_TEMPERATURE"] = "0.5"
    try:
        config = LLMConfig()
        assert config.llm_model == "gpt-4o"
        assert config.llm_temperature == 0.5
    finally:
        del os.environ["PPT_LLM_MODEL"]
        del os.environ["PPT_LLM_TEMPERATURE"]
