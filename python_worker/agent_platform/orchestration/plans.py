"""Structured plan, step, trace, and failure models (Module 4.1)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TargetSelector(BaseModel):
    """Which slides / elements a plan step targets."""

    model_config = ConfigDict(extra="forbid")
    slide_numbers: list[int] = Field(default_factory=list)
    text_ids: list[str] = Field(default_factory=list)
    element_ids: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    """A single step inside an AgentPlan."""

    model_config = ConfigDict(extra="forbid")
    step_id: str
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    target: TargetSelector = Field(default_factory=TargetSelector)
    rationale: str = ""
    depends_on: list[str] = Field(default_factory=list)


class AgentPlan(BaseModel):
    """Structured output from the planner LLM."""

    model_config = ConfigDict(extra="forbid")
    summary: str
    steps: list[PlanStep]
    rationale: str = ""
    plan_version: int = 1
    estimated_token_cost: int = 0


class PlanFailure(BaseModel):
    """A single validation or execution failure."""

    model_config = ConfigDict(extra="forbid")
    iteration: int
    failure_type: Literal[
        "schema",
        "tool_unknown",
        "param_invalid",
        "scope_violation",
        "dependency_invalid",
        "conflict",
    ]
    step_index: int | None = None
    detail: str


class StepResult(BaseModel):
    """Outcome of executing one plan step."""

    model_config = ConfigDict(extra="forbid")
    step_id: str
    status: Literal["ok", "error", "skipped"]
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class MergeSlideRef(BaseModel):
    """A single slide selection in a merge plan."""

    model_config = ConfigDict(extra="forbid")
    source_branch: int
    source_page: int
    target_page: int


class MergePlan(BaseModel):
    """Structured output from the merge planner LLM."""

    model_config = ConfigDict(extra="forbid")
    summary: str
    slides: list[MergeSlideRef]
    rationale: str = ""


class AgentTrace(BaseModel):
    """Observability record for a single agent subgraph run."""

    model_config = ConfigDict(extra="forbid")
    node_id: str = ""
    plan: AgentPlan | MergePlan | None = None
    step_results: list[StepResult] = Field(default_factory=list)
    plan_failures: list[PlanFailure] = Field(default_factory=list)
    status: Literal["success", "partial", "failed"] = "failed"
