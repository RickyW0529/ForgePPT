"""In-memory registry mapping adapter names + supported models to instances.

The registry is the single source of truth for "which adapter can serve
this model"; the router consults it on every call to resolve a chain of
candidates.
"""

from __future__ import annotations

from collections import defaultdict

from agent_platform.providers.adapters import ProviderAdapter


class ProviderRegistry:
    """Registers ProviderAdapter instances and indexes them by model."""

    def __init__(self) -> None:
        self._by_name: dict[str, ProviderAdapter] = {}
        self._by_model: dict[str, list[ProviderAdapter]] = defaultdict(list)

    def register(self, adapter: ProviderAdapter) -> None:
        if adapter.name in self._by_name:
            raise ValueError(f"adapter '{adapter.name}' already registered")
        self._by_name[adapter.name] = adapter
        for model in adapter.supported_models:
            self._by_model[model].append(adapter)

    def get(self, name: str) -> ProviderAdapter:
        try:
            return self._by_name[name]
        except KeyError as exc:
            raise KeyError(f"unknown provider: {name}") from exc

    def has(self, name: str) -> bool:
        return name in self._by_name

    def find_by_model(self, model: str) -> list[ProviderAdapter]:
        return list(self._by_model.get(model, []))

    def all(self) -> list[ProviderAdapter]:
        return list(self._by_name.values())
