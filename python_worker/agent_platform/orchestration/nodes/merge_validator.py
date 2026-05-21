"""Merge plan validator node — pure Python, no LLM."""

from __future__ import annotations

from typing import Any

from agent_platform.orchestration.plans import MergePlan, MergeSlideRef, PlanFailure
from agent_platform.orchestration.state import MergeGraphState


def validate_merge_plan(
    plan: MergePlan,
    inputs: list,
) -> tuple[bool, list[PlanFailure]]:
    """Validate a MergePlan and return (ok, failures).

    Checks performed:
      1. source_branch is within [0, len(inputs) - 1].
      2. source_page is a valid page number in that branch's slides.
      3. target_page >= 1 and <= len(base.slides).
      4. No duplicate target_page values.
    """
    failures: list[PlanFailure] = []
    base = inputs[0]
    seen_targets: set[int] = set()

    for idx, ref in enumerate(plan.slides):
        # 1. source_branch range
        if ref.source_branch < 0 or ref.source_branch >= len(inputs):
            failures.append(
                PlanFailure(
                    iteration=0,
                    failure_type="scope_violation",
                    step_index=idx,
                    detail=(
                        f"slide ref {idx} has source_branch={ref.source_branch} "
                        f"which is outside range [0, {len(inputs) - 1}]"
                    ),
                )
            )
            continue

        branch = inputs[ref.source_branch]

        # 2. source_page valid
        if ref.source_page < 1 or ref.source_page > len(branch.slides):
            failures.append(
                PlanFailure(
                    iteration=0,
                    failure_type="scope_violation",
                    step_index=idx,
                    detail=(
                        f"slide ref {idx} has source_page={ref.source_page} "
                        f"but branch {ref.source_branch} only has "
                        f"{len(branch.slides)} slides"
                    ),
                )
            )
            continue

        # 3. target_page valid
        if ref.target_page < 1 or ref.target_page > len(base.slides):
            failures.append(
                PlanFailure(
                    iteration=0,
                    failure_type="scope_violation",
                    step_index=idx,
                    detail=(
                        f"slide ref {idx} has target_page={ref.target_page} "
                        f"but base deck only has {len(base.slides)} slides"
                    ),
                )
            )
            continue

        # 4. No duplicate target_page
        if ref.target_page in seen_targets:
            failures.append(
                PlanFailure(
                    iteration=0,
                    failure_type="conflict",
                    step_index=idx,
                    detail=(
                        f"slide ref {idx} has duplicate target_page="
                        f"{ref.target_page}"
                    ),
                )
            )
            continue

        seen_targets.add(ref.target_page)

    return len(failures) == 0, failures


def make_merge_validator_node():
    """Return a LangGraph node that validates ``state["current_plan"]``."""

    def merge_validator_node(state: MergeGraphState) -> dict[str, Any]:
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

        ok, failures = validate_merge_plan(plan, state["inputs"])
        iteration = state.get("plan_iteration", 0)
        failures = [f.model_copy(update={"iteration": iteration}) for f in failures]

        return {
            "last_validation_ok": ok,
            "plan_failures": failures,
        }

    return merge_validator_node
