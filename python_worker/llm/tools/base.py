from typing import Any, Callable
from pydantic import BaseModel


class BaseToolInput(BaseModel):
    """All tool inputs inherit from this."""
    pass


class ToolDefinition:
    """Wraps a callable tool with metadata for LLM binding."""

    def __init__(
        self,
        name: str,
        description: str,
        roles: list[str],
        input_model: type[BaseModel],
        func: Callable[[Any], Any],
    ):
        self.name = name
        self.description = description
        self.roles = set(roles)
        self.input_model = input_model
        self.func = func

    def invoke(self, params: dict) -> Any:
        validated = self.input_model.model_validate(params)
        return self.func(validated)
