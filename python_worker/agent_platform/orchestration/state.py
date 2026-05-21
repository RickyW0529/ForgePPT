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


class BaseGraphState(TypedDict):
    """Shared state keys used by assemble_node and repair_node."""

    config: AgentNodeConfig | MergeNodeConfig
    current_plan: AgentPlan | MergePlan | None
    plan_iteration: int
    plan_failures: Annotated[list[PlanFailure], _add]
    step_results: Annotated[list[StepResult], _add]
    last_validation_ok: bool
    working_ppt_state: PPTState
    trace: AgentTrace | None


class AgentGraphState(BaseGraphState):
    """State carried through the agent subgraph.

    Non-serializable dependencies (ToolRegistry, ProviderRouter) are *not*
    stored here; they are closed over by the graph builder factory.
    """

    # Inputs (immutable after init)
    initial_ppt_state: PPTState
    role: str
    allowed_pages: list[int]  # computed from config.page_scope + edge_scope in init

    # Process state
    planner_context: PlannerContext


class MergeGraphState(BaseGraphState):
    """State carried through the merge subgraph."""

    # Inputs
    inputs: list[PPTState]
    prompt: str

    # Process state
    branch_diffs: list[list[int]]
