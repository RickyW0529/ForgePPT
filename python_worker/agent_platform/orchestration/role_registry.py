"""Agent role definitions (Module 4.2).

Replaces the legacy `workflow/agent_registry.AGENT_ROLES` with a typed,
extensible registry.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentRole(BaseModel):
    """Static configuration for an agent persona."""

    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    system_prompt: str
    default_model: str | None = None


AGENT_ROLES: dict[str, AgentRole] = {
    "text_refiner": AgentRole(
        key="text_refiner",
        name="Text Refiner",
        system_prompt=(
            "You are a text refinement expert. Rewrite, summarize, or translate text "
            "in the provided PPT slides based on the user's instruction."
        ),
    ),
    "color_optimizer": AgentRole(
        key="color_optimizer",
        name="Color Optimizer",
        system_prompt=(
            "You are a color optimization expert. Adjust font colors and suggest palettes "
            "for the provided PPT slides based on the user's instruction."
        ),
    ),
    "layout_designer": AgentRole(
        key="layout_designer",
        name="Layout Designer",
        system_prompt=(
            "You are a layout design expert. Reposition elements and resize shapes "
            "in the provided PPT slides based on the user's instruction."
        ),
    ),
    "svg_generator": AgentRole(
        key="svg_generator",
        name="SVG Generator",
        system_prompt=(
            "You are an SVG generation expert. Create SVG placeholders for slides "
            "based on the user's visual description."
        ),
    ),
    "theme_designer": AgentRole(
        key="theme_designer",
        name="Theme Designer",
        system_prompt=(
            "You are a theme design expert. Apply overall style theming to the provided "
            "PPT slides based on the user's instruction."
        ),
    ),
}


def get_role(key: str) -> AgentRole:
    """Lookup an agent role by key."""
    role = AGENT_ROLES.get(key)
    if role is None:
        raise ValueError(f"Unknown agent role: {key}")
    return role
