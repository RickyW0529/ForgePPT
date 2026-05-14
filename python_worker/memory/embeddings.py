from openai import OpenAI

from config import LLMConfig


def get_embedding(text: str, dimensions: int = 768) -> list[float]:
    """Generate embedding vector for text using the configured provider."""
    config = LLMConfig()
    provider = config.embedding_provider

    if provider == "zhipu":
        client = OpenAI(
            api_key=config.zhipu_api_key or None,
            base_url=config.embedding_base_url or "https://open.bigmodel.cn/api/paas/v4/",
        )
        model = config.embedding_model or "embedding-3"
        response = client.embeddings.create(
            model=model,
            input=text,
        )
        vec = response.data[0].embedding
        # Zhipu embedding-3 returns 2048 dims by default.
        # Truncate if a smaller dimension is configured.
        if len(vec) > dimensions:
            vec = vec[:dimensions]
        return vec
    else:
        # openai (default)
        client = OpenAI(api_key=config.openai_api_key or None)
        model = config.embedding_model or "text-embedding-3-small"
        response = client.embeddings.create(
            model=model,
            input=text,
            dimensions=dimensions,
        )
        return response.data[0].embedding
