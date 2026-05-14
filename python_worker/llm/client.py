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


def _openai_compatible_client(
    config: LLMConfig,
    api_key: str,
    default_base_url: str,
) -> BaseChatModel:
    """Create an OpenAI-compatible client (used by OpenAI, DeepSeek, Zhipu)."""
    from langchain_openai import ChatOpenAI

    base_url = config.llm_base_url or default_base_url or None
    return ChatOpenAI(
        model=config.llm_model,
        temperature=config.llm_temperature,
        timeout=30,
        max_retries=2,
        api_key=api_key or None,
        base_url=base_url,
    )


_PROVIDER_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "deepseek": "deepseek-chat",
    "zhipu": "glm-4",
}


def _resolve_model(config: LLMConfig) -> str:
    """Return the effective model name, applying provider-specific defaults."""
    provider = config.llm_provider
    default = _PROVIDER_DEFAULT_MODELS.get(provider, "gpt-4o-mini")
    # If user explicitly set a model, use it; otherwise use provider default.
    if config.llm_model and config.llm_model != "gpt-4o-mini":
        return config.llm_model
    return default


def get_llm_client() -> BaseChatModel:
    """Factory function returning a configured LLM client."""
    config = LLMConfig()
    provider = config.llm_provider

    # Apply provider-specific model default before creating the client.
    config.llm_model = _resolve_model(config)

    if provider == "openai":
        return _openai_compatible_client(
            config,
            api_key=config.openai_api_key,
            default_base_url="",
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
    elif provider == "deepseek":
        return _openai_compatible_client(
            config,
            api_key=config.deepseek_api_key,
            default_base_url="https://api.deepseek.com/v1",
        )
    elif provider == "zhipu":
        return _openai_compatible_client(
            config,
            api_key=config.zhipu_api_key,
            default_base_url="https://open.bigmodel.cn/api/paas/v4/",
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")
