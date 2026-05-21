"""Tool registry with capability-based discovery."""

from __future__ import annotations

from agent_platform.tools.descriptor import Capability, ToolDescriptor, ToolManifest


class ToolRegistry:
    """Registers tools and indexes them by name, capability, role, and namespace."""

    def __init__(self) -> None:
        self._by_name: dict[str, "Tool"] = {}

    def register(self, tool: "Tool") -> None:
        if tool.descriptor.name in self._by_name:
            raise ValueError(f"tool '{tool.descriptor.name}' already registered")
        self._by_name[tool.descriptor.name] = tool

    def get(self, name: str) -> "Tool":
        try:
            return self._by_name[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc

    def discover(
        self,
        capabilities: set[Capability] | None = None,
        role: str | None = None,
        namespace: str | None = None,
    ) -> list["Tool"]:
        results: list["Tool"] = []
        for tool in self._by_name.values():
            d = tool.descriptor
            if capabilities is not None:
                if not capabilities.issubset(set(d.capabilities)):
                    continue
            if role is not None:
                if d.required_role_grants and role not in d.required_role_grants:
                    continue
            if namespace is not None:
                if d.namespace != namespace:
                    continue
            results.append(tool)
        return results

    def manifest_for_role(self, role: str) -> list[ToolManifest]:
        """Return LLM-facing manifests for tools this role is allowed to use."""
        allowed = self.discover(role=role)
        return [ToolManifest.from_descriptor(t.descriptor) for t in allowed]
