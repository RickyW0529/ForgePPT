"""Sandboxed tool execution with capability checks and input validation."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from typing import Protocol

from agent_platform.tools.descriptor import Capability, ToolDescriptor


class ToolContext(BaseModel):
    """Execution context passed to every tool invocation."""

    model_config = ConfigDict(extra="forbid")
    role: str
    step_id: str
    trace_id: str
    granted_capabilities: set[Capability]
    timeout_sec: float


class ToolMetrics(BaseModel):
    """Optional metrics for a single tool execution."""

    model_config = ConfigDict(extra="forbid")
    latency_ms: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0


class ToolOutput(BaseModel):
    """Immutable output produced by a tool."""

    model_config = ConfigDict(extra="forbid")
    new_state: dict[str, Any]  # Replacement state (not in-place mutation)
    summary: dict[str, Any] = {}
    metrics: ToolMetrics = ToolMetrics()


class ToolExecutionError(Exception):
    """Structured error raised by the sandbox or tools."""

    def __init__(
        self,
        *,
        code: Literal[
            "invalid_target",
            "scope_violation",
            "external_unavailable",
            "timeout",
            "internal_error",
            "llm_failure",
            "invalid_input",
            "permission_denied",
        ],
        message: str,
        retryable: bool = False,
        suggested_fix: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.suggested_fix = suggested_fix


class PermissionDeniedError(ToolExecutionError):
    """Role lacks required capabilities. Non-retryable."""

    def __init__(self, message: str) -> None:
        super().__init__(
            code="permission_denied",
            message=message,
            retryable=False,
        )


class Tool(Protocol):
    """Protocol that every ForgePPT tool must satisfy."""

    descriptor: ToolDescriptor

    async def execute(
        self,
        ppt_state: dict[str, Any],
        params: BaseModel,
        target: Any,
        ctx: ToolContext,
    ) -> ToolOutput: ...


async def sandboxed_execute(
    tool: "Tool",
    *,
    ppt_state: dict[str, Any],
    params: dict[str, Any],
    target: Any,
    ctx: ToolContext,
) -> ToolOutput:
    """Execute a tool inside the sandbox.

    Steps:
      1. Capability check — role must have all declared capabilities.
      2. Input validation — params must conform to descriptor.input_schema.
      3. Timeout enforcement — asyncio.wait_for.
      4. Return ToolOutput (immutable).
    """
    desc = tool.descriptor
    needed = set(desc.capabilities)
    if not needed.issubset(ctx.granted_capabilities):
        missing = needed - ctx.granted_capabilities
        raise PermissionDeniedError(
            f"role '{ctx.role}' lacks capabilities: {', '.join(sorted(missing))}"
        )

    # Input re-validation (defense against planner bypass)
    try:
        validated = desc.input_schema.model_validate(params)
    except Exception as exc:
        raise ToolExecutionError(
            code="invalid_input",
            message=f"input validation failed: {exc}",
            retryable=False,
            suggested_fix="check parameter types against the tool schema",
        ) from exc

    try:
        return await asyncio.wait_for(
            tool.execute(ppt_state, validated, target, ctx),
            timeout=desc.timeout_sec,
        )
    except asyncio.TimeoutError as exc:
        raise ToolExecutionError(
            code="timeout",
            message=f"tool '{desc.name}' exceeded {desc.timeout_sec}s timeout",
            retryable=True,
            suggested_fix="increase timeout or split work into smaller chunks",
        ) from exc
    except ToolExecutionError:
        raise
    except Exception as exc:
        raise ToolExecutionError(
            code="internal_error",
            message=f"tool '{desc.name}' failed: {exc}",
            retryable=True,
            suggested_fix="review tool implementation for unhandled exceptions",
        ) from exc
