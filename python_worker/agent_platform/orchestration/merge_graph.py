"""LangGraph builder for the merge Plan-Solve subgraph (Module 5)."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent_platform.orchestration.nodes.assemble import assemble_node
from agent_platform.orchestration.nodes.diff_pages import diff_pages_node
from agent_platform.orchestration.nodes.merge_planner import make_merge_planner_node
from agent_platform.orchestration.nodes.merge_solver import make_merge_solver_node
from agent_platform.orchestration.nodes.merge_validator import make_merge_validator_node
from agent_platform.orchestration.nodes.repair import repair_node, route_repair
from agent_platform.orchestration.state import MergeGraphState
from agent_platform.providers.router import ProviderRouter


def build_merge_subgraph(router: ProviderRouter) -> StateGraph:
    """Build and compile the merge subgraph.

    Flow::

        START -> init -> diff_pages -> merge_planner -> merge_validator
        merge_validator --[ok]--> merge_solver -> assemble -> END
        merge_validator --[fail]--> repair
        repair --[retry]--> merge_planner
        repair --[abort]--> assemble -> END
    """
    builder = StateGraph(MergeGraphState)

    def init_node(state: MergeGraphState) -> dict:
        updates: dict = {}
        if state.get("working_ppt_state") is None:
            updates["working_ppt_state"] = state["inputs"][0]
        if state.get("plan_iteration") is None:
            updates["plan_iteration"] = 0
        if state.get("plan_failures") is None:
            updates["plan_failures"] = []
        if state.get("step_results") is None:
            updates["step_results"] = []
        if state.get("last_validation_ok") is None:
            updates["last_validation_ok"] = True
        if state.get("branch_diffs") is None:
            updates["branch_diffs"] = []
        if state.get("current_plan") is None:
            updates["current_plan"] = None
        if state.get("trace") is None:
            updates["trace"] = None
        return updates

    builder.add_node("init", init_node)
    builder.add_node("diff_pages", diff_pages_node)
    builder.add_node("merge_planner", make_merge_planner_node(router))
    builder.add_node("merge_validator", make_merge_validator_node())
    builder.add_node("repair", repair_node)
    builder.add_node("merge_solver", make_merge_solver_node())
    builder.add_node("assemble", assemble_node)

    builder.add_edge(START, "init")
    builder.add_edge("init", "diff_pages")
    builder.add_edge("diff_pages", "merge_planner")
    builder.add_edge("merge_planner", "merge_validator")

    def route_merge_validator(state: MergeGraphState) -> str:
        if state.get("last_validation_ok"):
            return "merge_solver"
        return "repair"

    builder.add_conditional_edges(
        "merge_validator",
        route_merge_validator,
        {"merge_solver": "merge_solver", "repair": "repair"},
    )

    builder.add_conditional_edges(
        "repair",
        route_repair,
        {"planner": "merge_planner", "assemble": "assemble"},
    )

    builder.add_edge("merge_solver", "assemble")
    builder.add_edge("assemble", END)

    return builder.compile()
