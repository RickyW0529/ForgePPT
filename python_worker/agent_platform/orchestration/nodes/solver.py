"""Solver node — executes plan steps via sandboxed tool calls (Module 4.5)."""

from __future__ import annotations

from collections import deque
from typing import Any

from agent_platform.orchestration.plans import AgentPlan, PlanStep, StepResult
from agent_platform.orchestration.state import AgentGraphState
from agent_platform.tools.descriptor import Capability
from agent_platform.tools.registry import ToolRegistry
from agent_platform.tools.sandbox import ToolContext, ToolExecutionError, sandboxed_execute


def _topological_order(steps: list[PlanStep]) -> list[PlanStep]:
    """Return steps in dependency-respecting order (Kahn's algorithm)."""
    step_map = {s.step_id: s for s in steps}
    in_degree: dict[str, int] = {s.step_id: 0 for s in steps}
    dependents: dict[str, list[str]] = {s.step_id: [] for s in steps}

    for s in steps:
        for dep in s.depends_on:
            if dep in in_degree:
                in_degree[s.step_id] += 1
                dependents[dep].append(s.step_id)

    queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
    result: list[PlanStep] = []

    while queue:
        sid = queue.popleft()
        result.append(step_map[sid])
        for dep_sid in dependents[sid]:
            in_degree[dep_sid] -= 1
            if in_degree[dep_sid] == 0:
                queue.append(dep_sid)

    return result


def make_solver_node(registry: ToolRegistry):
    """Return an async LangGraph node that executes ``state["current_plan"]``."""

    async def solver_node(state: AgentGraphState) -> dict[str, Any]:
        plan: AgentPlan | None = state.get("current_plan")
        if plan is None or not plan.steps:
            return {
                "step_results": [],
                "working_ppt_state": state["working_ppt_state"],
            }

        working = state["working_ppt_state"].model_dump()
        step_results: list[StepResult] = []
        ordered = _topological_order(plan.steps)

        for step in ordered:
            tool = registry.get(step.tool)
            # Grant exactly the capabilities the tool declares.
            ctx = ToolContext(
                role=state["role"],
                step_id=step.step_id,
                trace_id=state["config"].role,
                granted_capabilities=set(tool.descriptor.capabilities),
                timeout_sec=tool.descriptor.timeout_sec,
            )

            # MVP: pass first slide_number as target, else None.
            target: Any = None
            if step.target.slide_numbers:
                target = step.target.slide_numbers[0]

            try:
                output = await sandboxed_execute(
                    tool,
                    ppt_state=working,
                    params=step.params,
                    target=target,
                    ctx=ctx,
                )
                working = output.new_state
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        status="ok",
                        output=output.summary,
                    )
                )
            except ToolExecutionError as exc:
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        status="error",
                        error=str(exc),
                    )
                )
                # MVP: always break on first error (continue_on_error=False).
                break

        from models.ppt_state import PPTState

        return {
            "working_ppt_state": PPTState.model_validate(working),
            "step_results": step_results,
        }

    return solver_node
