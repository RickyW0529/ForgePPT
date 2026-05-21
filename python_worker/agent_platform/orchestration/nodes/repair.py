"""Plan repair node — decides whether to retry planner or abort (Module 4.4)."""

from __future__ import annotations

from typing import Any

from agent_platform.orchestration.plans import AgentTrace
from agent_platform.orchestration.state import AgentGraphState

MAX_REPLAN = 2


def repair_node(state: AgentGraphState) -> dict[str, Any]:
    """Handle a failed plan validation.

    If the planner has not yet exhausted its budget of replans, we loop
    back to ``planner`` (the edge is wired in ``agent_graph.py``).
    Otherwise we build an abort trace and short-circuit to ``assemble``.
    """
    iteration = state.get("plan_iteration", 0)
    if iteration >= MAX_REPLAN:
        node_id = getattr(state["config"], "role", "merge")
        return {
            "trace": AgentTrace(
                node_id=node_id,
                plan=state.get("current_plan"),
                plan_failures=state.get("plan_failures", []),
                status="failed",
            ),
        }
    return {}


def route_repair(state: AgentGraphState) -> str:
    """Conditional edge from repair node."""
    if state.get("trace") is not None:
        return "assemble"
    return "planner"
