"""Assemble node — builds the final AgentTrace (Module 4.7)."""

from __future__ import annotations

from typing import Any

from agent_platform.orchestration.plans import AgentTrace
from agent_platform.orchestration.state import AgentGraphState


def assemble_node(state: AgentGraphState) -> dict[str, Any]:
    """Build the final trace from execution state.

    If ``repair`` already set an abort trace, we pass through.
    """
    if state.get("trace") is not None:
        return {}

    step_results = state.get("step_results", [])
    all_ok = all(r.status == "ok" for r in step_results)
    status: Any = "success" if all_ok else "partial"

    node_id = getattr(state["config"], "role", "merge")
    trace = AgentTrace(
        node_id=node_id,
        plan=state.get("current_plan"),
        step_results=step_results,
        plan_failures=state.get("plan_failures", []),
        status=status,
    )
    return {"trace": trace}
