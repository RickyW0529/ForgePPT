"""LangGraph TypedDict state schemas (Module 4.1)."""

from __future__ import annotations

from typing import Annotated

from typing_extensions import TypedDict

from agent_platform.context.builders import PlannerContext
from agent_platform.orchestration.plans import (
    AgentPlan,
    AgentTrace,
    MergePlan,
    PlanFailure,
    StepResult,
)
from models.ppt_state import PPTState
from models.workflow_def import AgentNodeConfig, MergeNodeConfig


def _add(left: list, right: list) -> list:
    """Reducer: append right to left."""
    return left + right


class AgentGraphState(TypedDict):
    """State carried through the agent subgraph.

    Non-serializable dependencies (ToolRegistry, ProviderRouter) are *not*
    stored here; they are closed over by the graph builder factory.
    """

    # Inputs (immutable after init)
    initial_ppt_state: PPTState
    config: AgentNodeConfig
    role: str
    allowed_pages: list[int]  # computed from config.page_scope + edge_scope in init

    # Process state
    planner_context: PlannerContext
    current_plan: AgentPlan | None
    plan_iteration: int
    plan_failures: Annotated[list[PlanFailure], _add]
    step_results: Annotated[list[StepResult], _add]
    last_validation_ok: bool

    # Working copy of PPTState (replaced by solver after each step)
    working_ppt_state: PPTState

    # Output
    trace: AgentTrace | None


class MergeGraphState(TypedDict):
    """State carried through the merge subgraph."""

    # Inputs
    inputs: list[PPTState]
    config: MergeNodeConfig
    prompt: str

    # Process state
    current_plan: MergePlan | None
    plan_iteration: int
    plan_failures: Annotated[list[PlanFailure], _add]
    step_results: Annotated[list[StepResult], _add]
    last_validation_ok: bool
    branch_diffs: list[list[int]]

    # Working output
    working_ppt_state: PPTState
    trace: AgentTrace | None
