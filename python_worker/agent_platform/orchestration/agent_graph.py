"""LangGraph builder for the agent Plan-Solve subgraph (Module 4.8)."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent_platform.orchestration.nodes.assemble import assemble_node
from agent_platform.orchestration.nodes.planner import make_planner_node
from agent_platform.orchestration.nodes.repair import repair_node, route_repair
from agent_platform.orchestration.nodes.solver import make_solver_node
from agent_platform.orchestration.nodes.validator import make_validator_node
from agent_platform.orchestration.state import AgentGraphState
from agent_platform.providers.router import ProviderRouter
from agent_platform.tools.registry import ToolRegistry


def build_agent_subgraph(
    tool_registry: ToolRegistry,
    router: ProviderRouter,
) -> StateGraph:
    """Build and compile the agent subgraph.

    Flow::

        START -> init -> planner -> validator
        validator --[ok]--> solver -> assemble -> END
        validator --[fail]--> repair
        repair --[retry]--> planner
        repair --[abort]--> assemble -> END
    """
    builder = StateGraph(AgentGraphState)

    # Minimal init: ensure defaults for fields the runner may not pre-populate.
    def init_node(state: AgentGraphState) -> dict:
        updates: dict = {}
        if state.get("working_ppt_state") is None:
            updates["working_ppt_state"] = state["initial_ppt_state"]
        if state.get("plan_iteration") is None:
            updates["plan_iteration"] = 0
        if state.get("plan_failures") is None:
            updates["plan_failures"] = []
        if state.get("step_results") is None:
            updates["step_results"] = []
        if state.get("last_validation_ok") is None:
            updates["last_validation_ok"] = True
        return updates

    builder.add_node("init", init_node)
    builder.add_node("planner", make_planner_node(router))
    builder.add_node("validator", make_validator_node(tool_registry))
    builder.add_node("repair", repair_node)
    builder.add_node("solver", make_solver_node(tool_registry))
    builder.add_node("assemble", assemble_node)

    builder.add_edge(START, "init")
    builder.add_edge("init", "planner")
    builder.add_edge("planner", "validator")

    def route_validator(state: AgentGraphState) -> str:
        if state.get("last_validation_ok"):
            return "solver"
        return "repair"

    builder.add_conditional_edges(
        "validator",
        route_validator,
        {"solver": "solver", "repair": "repair"},
    )

    builder.add_conditional_edges(
        "repair",
        route_repair,
        {"planner": "planner", "assemble": "assemble"},
    )

    builder.add_edge("solver", "assemble")
    builder.add_edge("assemble", END)

    return builder.compile()
