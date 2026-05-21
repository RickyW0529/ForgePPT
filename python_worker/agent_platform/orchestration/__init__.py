"""Agent orchestration: LangGraph Plan-Solve subgraphs."""

from __future__ import annotations

from agent_platform.orchestration.agent_graph import build_agent_subgraph
from agent_platform.orchestration.merge_graph import build_merge_subgraph
from agent_platform.orchestration.plans import AgentPlan, AgentTrace, PlanStep, TargetSelector
from agent_platform.orchestration.role_registry import AGENT_ROLES, AgentRole, get_role
from agent_platform.orchestration.runner import run_agent_subgraph, run_merge_subgraph

__all__ = [
    "AgentPlan",
    "AgentRole",
    "AgentTrace",
    "AGENT_ROLES",
    "PlanStep",
    "TargetSelector",
    "build_agent_subgraph",
    "build_merge_subgraph",
    "get_role",
    "run_agent_subgraph",
    "run_merge_subgraph",
]
