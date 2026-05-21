"""Tests for ToolRegistry (Module 2)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from agent_platform.tools.descriptor import Capability, ToolDescriptor
from agent_platform.tools.registry import ToolRegistry


class _In(BaseModel):
    v: int


class _Out(BaseModel):
    r: str


class _FakeTool:
    def __init__(self, name: str, capabilities: list[Capability] | None = None):
        self.descriptor = ToolDescriptor(
            name=name,
            description=f"tool {name}",
            input_schema=_In,
            output_schema=_Out,
            capabilities=capabilities or [],
            required_role_grants=["editor"],
        )
        self.execute = AsyncMock()


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        t = _FakeTool("alpha")
        reg.register(t)
        assert reg.get("alpha") is t

    def test_get_unknown_raises(self):
        reg = ToolRegistry()
        with pytest.raises(KeyError):
            reg.get("nope")

    def test_discover_by_capability(self):
        reg = ToolRegistry()
        a = _FakeTool("read", [Capability.READ_TEXT])
        b = _FakeTool("write", [Capability.WRITE_TEXT])
        c = _FakeTool("both", [Capability.READ_TEXT, Capability.WRITE_TEXT])
        reg.register(a)
        reg.register(b)
        reg.register(c)

        found = reg.discover(capabilities={Capability.READ_TEXT})
        names = {t.descriptor.name for t in found}
        assert names == {"read", "both"}

    def test_discover_by_role(self):
        reg = ToolRegistry()
        t = _FakeTool("editor_tool", [Capability.WRITE_TEXT])
        t.descriptor.required_role_grants = ["editor"]
        reg.register(t)

        # Role "editor" should find it
        assert len(reg.discover(role="editor")) == 1
        # Role "viewer" should not
        assert len(reg.discover(role="viewer")) == 0

    def test_discover_by_namespace(self):
        reg = ToolRegistry()
        t = _FakeTool("ns_tool")
        t.descriptor.namespace = "custom"
        reg.register(t)

        assert len(reg.discover(namespace="custom")) == 1
        assert len(reg.discover(namespace="forgeppt")) == 0

    def test_manifest_for_role(self):
        reg = ToolRegistry()
        t = _FakeTool("manifest_tool", [Capability.READ_TEXT])
        reg.register(t)

        manifests = reg.manifest_for_role("editor")
        assert len(manifests) == 1
        assert manifests[0].name == "manifest_tool"
        assert "input_schema_json" in manifests[0].model_dump()
