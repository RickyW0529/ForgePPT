"""Tests for ToolDescriptor, Capability, SideEffect, ToolManifest (Module 2)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from agent_platform.tools.descriptor import (
    Capability,
    SideEffect,
    ToolDescriptor,
    ToolManifest,
)


class _FakeInput(BaseModel):
    value: int


class _FakeOutput(BaseModel):
    result: str


class TestToolDescriptor:
    def test_minimal_descriptor(self):
        d = ToolDescriptor(
            name="test_tool",
            description="A test tool",
            input_schema=_FakeInput,
            output_schema=_FakeOutput,
        )
        assert d.name == "test_tool"
        assert d.namespace == "forgeppt"
        assert d.version == "1.0.0"
        assert d.cost_class == "cheap"
        assert d.idempotent is True
        assert d.capabilities == []

    def test_capabilities_list(self):
        d = ToolDescriptor(
            name="style_tool",
            description="Apply style",
            input_schema=_FakeInput,
            output_schema=_FakeOutput,
            capabilities=[Capability.READ_STYLE, Capability.WRITE_STYLE],
        )
        assert Capability.READ_STYLE in d.capabilities
        assert Capability.WRITE_STYLE in d.capabilities

    def test_invalid_cost_class_rejected(self):
        with pytest.raises(ValidationError):
            ToolDescriptor(
                name="t",
                description="d",
                input_schema=_FakeInput,
                output_schema=_FakeOutput,
                cost_class="invalid",  # type: ignore[arg-type]
            )

    def test_side_effects(self):
        d = ToolDescriptor(
            name="mutator",
            description="mutates",
            input_schema=_FakeInput,
            output_schema=_FakeOutput,
            side_effects=[SideEffect(type="mutate_state", scope="slide")],
        )
        assert len(d.side_effects) == 1
        assert d.side_effects[0].type == "mutate_state"

    def test_required_role_grants(self):
        d = ToolDescriptor(
            name="admin_tool",
            description="admin only",
            input_schema=_FakeInput,
            output_schema=_FakeOutput,
            required_role_grants=["admin", "editor"],
        )
        assert "admin" in d.required_role_grants


class TestToolManifest:
    def test_from_descriptor(self):
        d = ToolDescriptor(
            name="test_tool",
            description="A test tool",
            input_schema=_FakeInput,
            output_schema=_FakeOutput,
            capabilities=[Capability.READ_TEXT],
            cost_class="cheap",
        )
        manifest = ToolManifest.from_descriptor(d)
        assert manifest.name == "test_tool"
        assert manifest.description == "A test tool"
        assert manifest.cost_class == "cheap"
        assert "input_schema_json" in manifest.model_dump()
        # Internal fields should NOT appear
        assert "side_effects" not in manifest.model_dump()
        assert "required_role_grants" not in manifest.model_dump()
