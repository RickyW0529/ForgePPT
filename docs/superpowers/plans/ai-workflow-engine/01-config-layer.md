# 01 - Configuration Layer

**Files:**
- Create: `python_worker/config.py`
- Modify: `python_worker/pyproject.toml` (add pydantic-settings, langchain deps)
- Modify: `python_worker/requirements.txt`

---

- [ ] **Step 1: Write the failing test**

```python
# python_worker/tests/test_config.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python_worker && pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'config'"

- [ ] **Step 3: Add dependencies**

Append to `python_worker/pyproject.toml` dependencies:

```toml
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "python-pptx>=1.0.0",
    "pillow>=10.0",
    "langchain>=0.3.0",
    "langchain-openai>=0.2.0",
    "langchain-anthropic>=0.2.0",
    "langgraph>=0.2.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
]
```

Append to `python_worker/requirements.txt`:

```text
pydantic-settings>=2.0
langchain>=0.3.0
langchain-openai>=0.2.0
langchain-anthropic>=0.2.0
langgraph>=0.2.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
httpx>=0.27.0
```

- [ ] **Step 4: Write minimal implementation**

```python
# python_worker/config.py
from pydantic_settings import BaseSettings


class LLMConfig(BaseSettings):
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.3
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    class Config:
        env_prefix = "PPT_"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd python_worker && pytest tests/test_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add python_worker/config.py python_worker/tests/test_config.py python_worker/pyproject.toml python_worker/requirements.txt
git commit -m "feat: add LLM configuration layer with env overrides"
```
