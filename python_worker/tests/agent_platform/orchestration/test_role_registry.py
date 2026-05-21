"""Tests for AgentRole registry (Module 4.2)."""

from __future__ import annotations

import pytest

from agent_platform.orchestration.role_registry import (
    AGENT_ROLES,
    AgentRole,
    get_role,
)


class TestAgentRole:
    def test_fields(self):
        role = AgentRole(
            key="test",
            name="Test Role",
            system_prompt="You are a test.",
            default_model="gpt-4o",
        )
        assert role.key == "test"
        assert role.name == "Test Role"
        assert role.system_prompt == "You are a test."
        assert role.default_model == "gpt-4o"


class TestGetRole:
    def test_known_roles_exist(self):
        for key in ("text_refiner", "color_optimizer", "layout_designer",
                    "svg_generator", "theme_designer"):
            role = get_role(key)
            assert role is not None
            assert role.key == key
            assert role.system_prompt != ""

    def test_text_refiner_prompt(self):
        role = get_role("text_refiner")
        assert "text" in role.system_prompt.lower()

    def test_unknown_role_raises(self):
        with pytest.raises(ValueError, match="Unknown agent role"):
            get_role("nonexistent")

    def test_registry_is_dict(self):
        assert isinstance(AGENT_ROLES, dict)
        assert len(AGENT_ROLES) >= 5
