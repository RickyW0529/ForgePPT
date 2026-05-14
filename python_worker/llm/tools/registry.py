import inspect
from typing import Any, Callable
from pydantic import BaseModel
from llm.tools.base import ToolDefinition


class ToolRegistry:
    """Singleton registry for LLM tools."""

    _instance: "ToolRegistry | None" = None
    _tools: dict[str, ToolDefinition]

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(
        self,
        name: str,
        description: str,
        roles: list[str],
        input_model: type[BaseModel],
        func: Callable[[Any], Any],
    ) -> None:
        if name in self._tools:
            raise ValueError(f"Tool '{name}' already registered")
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            roles=roles,
            input_model=input_model,
            func=func,
        )

    def get_tool(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found")
        return self._tools[name]

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_tools_for_role(self, role: str) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if role in t.roles]


def llm_tool(
    name: str,
    roles: list[str],
    description: str = "",
) -> Callable:
    """Decorator to register a function as an LLM tool.

    The decorated function must accept a single Pydantic model argument
    (its input schema) and return a JSON-serializable value.
    """
    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        if len(params) != 1:
            raise TypeError(f"Tool '{name}' must accept exactly one argument (input model)")
        input_model = params[0].annotation
        if not issubclass(input_model, BaseModel):
            raise TypeError(f"Tool '{name}' argument must be a Pydantic model")

        registry = ToolRegistry()
        registry.register(
            name=name,
            description=description or func.__doc__ or "",
            roles=roles,
            input_model=input_model,
            func=func,
        )
        return func
    return decorator
