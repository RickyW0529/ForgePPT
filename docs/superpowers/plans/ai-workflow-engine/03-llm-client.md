# 03 - LLM Client Abstraction

**Files:**
- Create: `python_worker/llm/client.py`
- Create: `python_worker/llm/__init__.py`
- Create: `python_worker/tests/test_llm_client.py`

---

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_llm_client.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_llm_client.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'llm.client'"

- [ ] **Step 3: Write minimal implementation**

```python
# python_worker/llm/client.py
from typing import Protocol, TypeVar

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel

from config import LLMConfig

T = TypeVar("T")


class LLMClient(Protocol):
    def invoke(self, messages: list) -> str: ...
    def with_structured_output(self, schema: type[T], method: str) -> T: ...


class TokenUsageCallback(BaseCallbackHandler):
    """Callback handler that tracks LLM token usage across invocations."""

    def __init__(self):
        self.usage_log: list[dict] = []
        self._input_tokens = 0
        self._output_tokens = 0

    def on_llm_start(self, serialized, prompts, **kwargs):
        self._input_tokens = 0
        self._output_tokens = 0

    def on_llm_end(self, response, **kwargs):
        try:
            usage = response.generations[0][0].message.usage_metadata
            self._input_tokens = usage.get("input_tokens", 0)
            self._output_tokens = usage.get("output_tokens", 0)
            self.usage_log.append({
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
                "total_tokens": self._input_tokens + self._output_tokens,
                "model": kwargs.get("invocation_params", {}).get("model_name", "unknown"),
            })
        except (AttributeError, IndexError):
            pass

    def get_total_usage(self) -> dict:
        return {
            "total_input": sum(u["input_tokens"] for u in self.usage_log),
            "total_output": sum(u["output_tokens"] for u in self.usage_log),
            "calls_count": len(self.usage_log),
        }


def get_llm_client() -> BaseChatModel:
    """Factory function returning a configured LLM client."""
    config = LLMConfig()
    provider = config.llm_provider

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.llm_model,
            temperature=config.llm_temperature,
            timeout=30,
            max_retries=2,
            api_key=config.openai_api_key or None,
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=config.llm_model,
            temperature=config.llm_temperature,
            timeout=30,
            max_retries=2,
            api_key=config.anthropic_api_key or None,
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_llm_client.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add python_worker/llm/client.py python_worker/llm/__init__.py python_worker/tests/test_llm_client.py
git commit -m "feat: add LLM client abstraction with token usage tracking"
```
