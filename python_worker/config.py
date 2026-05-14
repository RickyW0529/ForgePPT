from pydantic_settings import BaseSettings


class LLMConfig(BaseSettings):
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.3
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    class Config:
        env_prefix = "PPT_"
