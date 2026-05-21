"""Planner node — LLM call that outputs an AgentPlan (Module 4.6)."""

from __future__ import annotations

import json
from typing import Any

from agent_platform.context.builders import PlannerContext
from agent_platform.orchestration.plans import AgentPlan
from agent_platform.orchestration.state import AgentGraphState
from agent_platform.providers.models import ChatMessage, LLMRequest, RequestMetadata, RequestPurpose
from agent_platform.providers.router import ProviderRouter

# MVP: generous per-plan budget until Module 7 wires in real accounting.
_DEFAULT_PLAN_BUDGET_USD = 10.0


def _build_messages(ctx: PlannerContext, failures: list) -> list[ChatMessage]:
    """Serialize PlannerContext into a system + user message pair."""
    system = ctx.role_system_prompt

    parts: list[str] = [
        f"Deck meta: {json.dumps(ctx.deck_meta, ensure_ascii=False)}",
        f"Slides in scope: {[s.model_dump() for s in ctx.slides_in_scope]}",
        f"Available tools: {[t.model_dump() for t in ctx.available_tools]}",
        f"User instruction: {ctx.user_prompt}",
    ]
    if ctx.memory_snippets:
        parts.append(f"Memory snippets: {ctx.memory_snippets}")
    if failures:
        parts.append(
            f"Previous plan failures: {[f.model_dump() for f in failures]}"
        )

    return [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content="\n\n".join(parts)),
    ]


def make_planner_node(router: ProviderRouter):
    """Return an async LangGraph node that calls the LLM to produce an AgentPlan."""

    async def planner_node(state: AgentGraphState) -> dict[str, Any]:
        iteration = state.get("plan_iteration", 0) + 1
        ctx: PlannerContext = state["planner_context"]
        config = state["config"]

        messages = _build_messages(ctx, state.get("plan_failures", []))

        request = LLMRequest(
            model=config.model or "gpt-4o-mini",
            messages=messages,
            temperature=config.temperature,
            response_format="json",
            output_schema=AgentPlan,
            metadata=RequestMetadata(
                purpose=RequestPurpose.PLANNER,
                trace_id=config.role,
                workflow_id="",
                cost_budget_remaining=_DEFAULT_PLAN_BUDGET_USD,
            ),
        )

        response = await router.complete(request)

        # If structured output parsing succeeded, parsed is an AgentPlan instance.
        plan: AgentPlan | None = None
        if response.parsed is not None and isinstance(response.parsed, AgentPlan):
            plan = response.parsed
        else:
            # Fallback: try to parse from text (defensive).
            try:
                text = response.text
                # Strip markdown fences if present
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else ""
                if text.endswith("```"):
                    text = text.rsplit("\n", 1)[0] if "\n" in text else ""
                plan = AgentPlan.model_validate_json(text)
            except Exception:
                pass

        return {
            "plan_iteration": iteration,
            "current_plan": plan,
        }

    return planner_node
