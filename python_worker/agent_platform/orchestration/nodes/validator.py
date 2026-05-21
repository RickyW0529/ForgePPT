"""Plan validator node — pure Python, no LLM (Module 4.3)."""

from __future__ import annotations

from typing import Any

from agent_platform.orchestration.plans import AgentPlan, PlanFailure, PlanStep
from agent_platform.orchestration.state import AgentGraphState
from agent_platform.tools.registry import ToolRegistry


def _detect_cycle(steps: list[PlanStep]) -> bool:
    """Return True if the dependency graph contains a cycle."""
    step_ids = {s.step_id for s in steps}
    adj: dict[str, list[str]] = {s.step_id: list(s.depends_on) for s in steps}

    visited: set[str] = set()
    rec_stack: set[str] = set()

    def _dfs(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor not in step_ids:
                continue
            if neighbor not in visited:
                if _dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.remove(node)
        return False

    for sid in step_ids:
        if sid not in visited:
            if _dfs(sid):
                return True
    return False


def validate_plan(
    plan: AgentPlan,
    registry: ToolRegistry,
    allowed_pages: list[int] | None = None,
) -> tuple[bool, list[PlanFailure]]:
    """Validate an AgentPlan and return (ok, failures).

    Checks performed:
      1. Each step references a registered tool.
      2. Params conform to the tool's input_schema.
      3. slide_numbers are within allowed_pages (if provided and non-empty).
      4. depends_on reference existing step_ids and form a DAG (no cycles).
    """
    failures: list[PlanFailure] = []
    allowed_set = set(allowed_pages) if allowed_pages else set()
    step_ids = {s.step_id for s in plan.steps}

    # Global: cycle check first
    if plan.steps and _detect_cycle(plan.steps):
        failures.append(
            PlanFailure(
                iteration=0,
                failure_type="dependency_invalid",
                detail="dependency graph contains a cycle",
            )
        )

    for idx, step in enumerate(plan.steps):
        # 1. Tool exists
        try:
            tool = registry.get(step.tool)
        except KeyError:
            failures.append(
                PlanFailure(
                    iteration=0,
                    failure_type="tool_unknown",
                    step_index=idx,
                    detail=f"tool '{step.tool}' is not registered",
                )
            )
            continue

        # 2. Param schema
        try:
            tool.descriptor.input_schema.model_validate(step.params)
        except Exception as exc:
            failures.append(
                PlanFailure(
                    iteration=0,
                    failure_type="param_invalid",
                    step_index=idx,
                    detail=f"step '{step.step_id}' params invalid: {exc}",
                )
            )

        # 3. Scope
        if allowed_set and step.target.slide_numbers:
            invalid = set(step.target.slide_numbers) - allowed_set
            if invalid:
                failures.append(
                    PlanFailure(
                        iteration=0,
                        failure_type="scope_violation",
                        step_index=idx,
                        detail=(
                            f"step '{step.step_id}' targets slides "
                            f"{sorted(invalid)} which are outside the allowed scope"
                        ),
                    )
                )

        # 4. Dependency existence (cycle already checked globally)
        missing_deps = set(step.depends_on) - step_ids
        if missing_deps:
            failures.append(
                PlanFailure(
                    iteration=0,
                    failure_type="dependency_invalid",
                    step_index=idx,
                    detail=(
                        f"step '{step.step_id}' depends on unknown step_ids: "
                        f"{sorted(missing_deps)}"
                    ),
                )
            )

    return len(failures) == 0, failures


def make_validator_node(registry: ToolRegistry):
    """Return a LangGraph node that validates ``state["current_plan"]``."""

    def validator_node(state: AgentGraphState) -> dict[str, Any]:
        plan = state.get("current_plan")
        if plan is None:
            return {
                "last_validation_ok": False,
                "plan_failures": [
                    PlanFailure(
                        iteration=state.get("plan_iteration", 0),
                        failure_type="schema",
                        detail="current_plan is None",
                    )
                ],
            }

        ok, failures = validate_plan(
            plan,
            registry,
            allowed_pages=state.get("allowed_pages"),
        )
        # Tag each failure with the current iteration
        iteration = state.get("plan_iteration", 0)
        failures = [f.model_copy(update={"iteration": iteration}) for f in failures]

        return {
            "last_validation_ok": ok,
            "plan_failures": failures,
        }

    return validator_node
