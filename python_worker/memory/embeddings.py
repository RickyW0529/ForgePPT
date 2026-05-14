from openai import OpenAI

from config import LLMConfig


def get_embedding(text: str, dimensions: int = 768) -> list[float]:
    """Generate embedding vector for text using OpenAI API."""
    config = LLMConfig()
    client = OpenAI(api_key=config.openai_api_key or None)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        dimensions=dimensions,
    )
    return response.data[0].embedding
