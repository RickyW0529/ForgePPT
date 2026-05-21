"""Merge planner node — LLM call that outputs a MergePlan."""

from __future__ import annotations

import re
from typing import Any

from agent_platform.orchestration.plans import MergePlan
from agent_platform.orchestration.state import MergeGraphState
from agent_platform.providers.models import ChatMessage, LLMRequest, RequestMetadata, RequestPurpose
from agent_platform.providers.router import ProviderRouter

_DEFAULT_PLAN_BUDGET_USD = 10.0


def _build_messages(state: MergeGraphState) -> list[ChatMessage]:
    """Serialize merge context into a system + user message pair."""
    inputs = state["inputs"]
    base = inputs[0]
    branch_diffs = state.get("branch_diffs", [])

    system = (
        "You are a PPT merge planner. Your job is to reconcile multiple "
        "branch modifications into a single output deck. Output a JSON plan "
        "that selects which slides from which branches should appear at each "
        "position in the final deck."
    )

    parts: list[str] = [
        f"Base deck has {base.slide_count} slides.",
    ]
    for i, diff in enumerate(branch_diffs, start=1):
        parts.append(f"Branch {i} modified pages: {diff}")

    failures = state.get("plan_failures", [])
    if failures:
        parts.append(
            f"Previous plan failures: {[f.model_dump() for f in failures]}"
        )

    parts.append(f"User instruction: {state['prompt']}")

    return [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content="\n\n".join(parts)),
    ]


def make_merge_planner_node(router: ProviderRouter):
    """Return an async LangGraph node that calls the LLM to produce a MergePlan."""

    async def merge_planner_node(state: MergeGraphState) -> dict[str, Any]:
        iteration = state.get("plan_iteration", 0) + 1
        config = state["config"]

        messages = _build_messages(state)

        request = LLMRequest(
            model=getattr(config, "model", None) or "gpt-4o-mini",
            messages=messages,
            temperature=getattr(config, "temperature", 0.3),
            response_format="json",
            output_schema=MergePlan,
            metadata=RequestMetadata(
                purpose=RequestPurpose.MERGE_PLANNER,
                trace_id="merge",
                workflow_id="",
                cost_budget_remaining=_DEFAULT_PLAN_BUDGET_USD,
            ),
        )

        response = await router.complete(request)

        plan: MergePlan | None = None
        if response.parsed is not None and isinstance(response.parsed, MergePlan):
            plan = response.parsed
        else:
            try:
                text = response.text
                # Strip markdown fences if present
                m = re.search(r"```(?:json)?\s*\n(.*?)\n?```", text, re.DOTALL)
                if m:
                    text = m.group(1)
                plan = MergePlan.model_validate_json(text)
            except Exception:
                pass

        return {
            "plan_iteration": iteration,
            "current_plan": plan,
        }

    return merge_planner_node
