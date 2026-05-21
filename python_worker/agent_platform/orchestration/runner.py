"""Runner — entry point for Prefect to invoke the agent subgraph (Module 4.8)."""

from __future__ import annotations

from agent_platform.context.builders import build_planner_context
from agent_platform.orchestration.agent_graph import build_agent_subgraph
from agent_platform.orchestration.merge_graph import build_merge_subgraph
from agent_platform.orchestration.plans import AgentTrace
from agent_platform.orchestration.role_registry import get_role
from agent_platform.orchestration.state import AgentGraphState, MergeGraphState
from agent_platform.providers import get_router
from agent_platform.tools.builtin import BUILTIN_TOOLS
from agent_platform.tools.registry import ToolRegistry
from models.ppt_state import PPTState
from models.workflow_def import AgentNodeConfig, MergeNodeConfig


async def run_agent_subgraph(
    ppt_state: PPTState,
    config: AgentNodeConfig,
    edge_scope: list[int] | None = None,
) -> tuple[PPTState, AgentTrace]:
    """Execute the agent Plan-Solve subgraph.

    Returns the modified ``PPTState`` and an ``AgentTrace`` for observability.
    """
    # 1. Tool registry
    registry = ToolRegistry()
    for tool in BUILTIN_TOOLS:
        registry.register(tool)

    # 2. Router
    router = get_router()

    # 3. Build graph
    graph = build_agent_subgraph(registry, router)

    # 4. Compute allowed pages
    allowed_pages = list(edge_scope) if edge_scope is not None else list(config.page_scope)
    if not allowed_pages:
        allowed_pages = list(range(1, ppt_state.slide_count + 1))

    # 5. Build planner context
    role = get_role(config.role)
    planner_ctx = build_planner_context(
        state=ppt_state,
        scope=allowed_pages,
        role=config.role,
        prompt=config.prompt,
        tool_registry=registry,
    )

    # 6. Initial state
    initial_state: AgentGraphState = {
        "initial_ppt_state": ppt_state,
        "config": config,
        "role": config.role,
        "allowed_pages": allowed_pages,
        "planner_context": planner_ctx,
        "current_plan": None,
        "plan_iteration": 0,
        "plan_failures": [],
        "step_results": [],
        "last_validation_ok": True,
        "working_ppt_state": ppt_state,
        "trace": None,
    }

    # 7. Invoke
    final_state = await graph.ainvoke(initial_state)

    # 8. Extract results
    working = final_state["working_ppt_state"]
    trace = final_state.get("trace")
    if trace is None:
        trace = AgentTrace(node_id=config.role, status="failed")

    return working, trace


async def run_merge_subgraph(
    inputs: list[PPTState],
    config: MergeNodeConfig,
) -> tuple[PPTState, AgentTrace]:
    """Execute the merge Plan-Solve subgraph.

    Returns the merged ``PPTState`` and an ``AgentTrace`` for observability.
    """
    if not inputs:
        raise ValueError("merge subgraph requires at least one input PPTState")

    # 1. Router
    router = get_router()

    # 2. Build graph
    graph = build_merge_subgraph(router)

    # 3. Initial state
    initial_state: MergeGraphState = {
        "inputs": inputs,
        "config": config,
        "prompt": config.prompt,
        "current_plan": None,
        "plan_iteration": 0,
        "plan_failures": [],
        "step_results": [],
        "last_validation_ok": True,
        "branch_diffs": [],
        "working_ppt_state": inputs[0],
        "trace": None,
    }

    # 4. Invoke
    final_state = await graph.ainvoke(initial_state)

    # 5. Extract results
    working = final_state["working_ppt_state"]
    trace = final_state.get("trace")
    if trace is None:
        trace = AgentTrace(node_id="merge", status="failed")

    return working, trace
