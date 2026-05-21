"""Unified request/response types used by every LLM call.

Spec: docs/superpowers/specs/2026-05-21-agent-platform/03-llm-provider-management.md
"""

from __future__ import annotations

import inspect
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


# ---------------------------------------------------------------------------
# Token accounting
# ---------------------------------------------------------------------------


class TokenUsage(BaseModel):
    """Per-call token accounting.

    `cached_input_tokens` and `reasoning_output_tokens` are subsets of
    `input_tokens` / `output_tokens` respectively, exposed so BudgetTracker
    can apply different unit prices.
    """

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    reasoning_output_tokens: int = Field(default=0, ge=0)

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


# ---------------------------------------------------------------------------
# Request metadata
# ---------------------------------------------------------------------------


class RequestPurpose(str, Enum):
    """Why this LLM call is being made — drives routing."""

    PLANNER = "planner"
    REFLECTOR = "reflector"
    SOLVER_INNER = "solver_inner"
    MERGE_PLANNER = "merge_planner"
    EMBEDDING = "embedding"


class RequestMetadata(BaseModel):
    """Sidecar metadata routed alongside the LLM request.

    `cost_budget_remaining` is required — callers must always plumb a real
    BudgetTracker value through, never a sentinel default.
    """

    model_config = ConfigDict(extra="forbid")

    purpose: RequestPurpose
    trace_id: str
    workflow_id: str
    cost_budget_remaining: float = Field(gt=0)
    latency_budget_ms: int = Field(default=60_000, gt=0)
    role: str | None = None


# ---------------------------------------------------------------------------
# Chat content
# ---------------------------------------------------------------------------


ChatRole = Literal["system", "user", "assistant", "tool"]


class ChatMessage(BaseModel):
    """Single chat turn. Tool messages carry `tool_call_id`."""

    model_config = ConfigDict(extra="forbid")

    role: ChatRole
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class ToolCall(BaseModel):
    """A tool invocation emitted by the model."""

    model_config = ConfigDict(extra="forbid")

    call_id: str
    name: str
    arguments: dict[str, Any]


# ---------------------------------------------------------------------------
# Request / response
# ---------------------------------------------------------------------------


class LLMRequest(BaseModel):
    """Provider-agnostic request shape.

    Structured output is opt-in via `output_schema`. If provided, the adapter
    MUST coerce the model output into an instance of that BaseModel subclass
    and populate `LLMResponse.parsed`. `response_format="text"` with
    `output_schema=None` is the plain-text path.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    response_format: Literal["text", "json"] = "text"
    output_schema: type[BaseModel] | None = None
    tools: list[dict[str, Any]] | None = None
    seed: int | None = None
    metadata: RequestMetadata

    @field_validator("output_schema")
    @classmethod
    def _output_schema_is_base_model(
        cls, v: type[BaseModel] | None
    ) -> type[BaseModel] | None:
        if v is None:
            return v
        if not (inspect.isclass(v) and issubclass(v, BaseModel)):
            raise ValueError("output_schema must be a subclass of pydantic.BaseModel")
        return v


FinishReason = Literal["stop", "length", "tool_calls", "content_filter", "error"]


class LLMResponse(BaseModel):
    """Provider-agnostic response shape.

    `text` is always populated (possibly empty when only tool_calls are
    emitted). `parsed` is populated only when the originating request had
    `output_schema` set.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    text: str
    parsed: BaseModel | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tokens: TokenUsage
    latency_ms: int = Field(ge=0)
    provider: str
    model: str
    cost_usd: float = Field(ge=0.0)
    finish_reason: FinishReason
