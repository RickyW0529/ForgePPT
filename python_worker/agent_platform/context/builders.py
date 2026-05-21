"""Context builders for planner, text refinement, and failure feedback (Module 3.2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from agent_platform.providers.models import ChatMessage
from agent_platform.tools.descriptor import ToolManifest
from agent_platform.tools.registry import ToolRegistry
from models.ppt_state import PPTState

from agent_platform.context.digests import (
    SlideDigest,
    StateDiffDigest,
    allocate_tier1_budget,
    build_slide_digest,
)
from agent_platform.context.models import FailureFeedback


class PlannerContext(BaseModel):
    """All the information a planner needs to generate a tool-execution plan."""

    model_config = ConfigDict(extra="forbid")
    deck_meta: dict[str, Any]
    slides_in_scope: list[SlideDigest]
    available_tools: list[ToolManifest]
    role_system_prompt: str
    user_prompt: str
    memory_snippets: list[str]
    previous_attempts: list[str]
    constraints: list[str]


def build_planner_context(
    state: PPTState,
    scope: list[int],
    role: str,
    prompt: str,
    tool_registry: ToolRegistry,
    memories: list[str] | None = None,
    attempts: list[str] | None = None,
) -> PlannerContext:
    """Assemble a PlannerContext from the current state, scope, and tool registry."""
    budget = allocate_tier1_budget(
        deck_size=len(state.slides),
        scope_size=len(scope),
    )
    sample_chars = budget["sample_chars"]

    scope_set = set(scope)
    slides_in_scope: list[SlideDigest] = []
    for slide in state.slides:
        if slide.page_num in scope_set:
            slides_in_scope.append(build_slide_digest(slide, sample_chars=sample_chars))

    available_tools = tool_registry.manifest_for_role(role)

    return PlannerContext(
        deck_meta={
            "source_file": state.source_file,
            "slide_count": state.slide_count,
        },
        slides_in_scope=slides_in_scope,
        available_tools=available_tools,
        role_system_prompt=role,
        user_prompt=prompt,
        memory_snippets=memories or [],
        previous_attempts=attempts or [],
        constraints=[],
    )


def build_text_refine_context(
    original: str,
    instruction: str,
    style_hint: str | None = None,
) -> list[ChatMessage]:
    """Build a pair of ChatMessages for a text-refinement LLM call."""
    system_msg = ChatMessage(
        role="system",
        content="You are a PPT text refinement assistant. Keep the tone professional.",
    )

    user_content = f"Original text: {original}\nInstruction: {instruction}"
    if style_hint is not None:
        user_content += f"\nStyle hint: {style_hint}"

    user_msg = ChatMessage(
        role="user",
        content=user_content,
    )

    return [system_msg, user_msg]


def build_failure_feedback(
    plan: dict[str, Any],
    failures: list[str],
    diff: StateDiffDigest | None = None,
) -> FailureFeedback:
    """Build a FailureFeedback, truncating long failure lists."""
    if len(failures) > 5:
        truncated = failures[:3] + ["..."] + failures[-2:]
    else:
        truncated = failures

    return FailureFeedback(
        previous_plan_summary=plan,
        failures=truncated,
        state_diff=diff,
    )
