"""Tests for sandboxed execution (Module 2)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from agent_platform.tools.descriptor import Capability, SideEffect, ToolDescriptor
from agent_platform.tools.sandbox import (
    PermissionDeniedError,
    ToolContext,
    ToolExecutionError,
    ToolOutput,
    sandboxed_execute,
)


class _In(BaseModel):
    v: int


class _Out(BaseModel):
    r: str


class _FakeTool:
    def __init__(
        self,
        name: str = "fake",
        capabilities: list[Capability] | None = None,
        side_effects: list[SideEffect] | None = None,
    ):
        self.descriptor = ToolDescriptor(
            name=name,
            description=f"tool {name}",
            input_schema=_In,
            output_schema=_Out,
            capabilities=capabilities or [Capability.READ_TEXT],
            side_effects=side_effects or [],
            timeout_sec=0.5,
        )
        self.execute = AsyncMock()


def _ctx(grants: set[Capability] | None = None, role: str = "editor") -> ToolContext:
    return ToolContext(
        role=role,
        step_id="s1",
        trace_id="t1",
        granted_capabilities=grants or {Capability.READ_TEXT},
        timeout_sec=5.0,
    )


class TestSandboxedExecute:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        tool = _FakeTool()
        expected = ToolOutput(new_state={"x": 1}, summary={})
        tool.execute.return_value = expected

        result = await sandboxed_execute(
            tool, ppt_state={}, params={"v": 42}, target=None, ctx=_ctx()
        )

        assert result is expected
        tool.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_params_validated_against_schema(self):
        tool = _FakeTool()
        tool.execute.return_value = ToolOutput(new_state={}, summary={})

        # Valid params should pass
        await sandboxed_execute(
            tool, ppt_state={}, params={"v": 42}, target=None, ctx=_ctx()
        )

        # Invalid params should raise ToolExecutionError
        with pytest.raises(ToolExecutionError) as exc:
            await sandboxed_execute(
                tool, ppt_state={}, params={"v": "not_an_int"}, target=None, ctx=_ctx()
            )
        assert exc.value.code == "invalid_input"

    @pytest.mark.asyncio
    async def test_permission_denied_for_missing_capability(self):
        tool = _FakeTool(capabilities=[Capability.WRITE_TEXT])
        ctx = _ctx(grants={Capability.READ_TEXT})

        with pytest.raises(PermissionDeniedError) as exc:
            await sandboxed_execute(
                tool, ppt_state={}, params={"v": 1}, target=None, ctx=ctx
            )
        assert Capability.WRITE_TEXT.value in str(exc.value)
        tool.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_permission_allowed_when_cap_granted(self):
        tool = _FakeTool(capabilities=[Capability.READ_TEXT, Capability.WRITE_TEXT])
        ctx = _ctx(grants={Capability.READ_TEXT, Capability.WRITE_TEXT})
        tool.execute.return_value = ToolOutput(new_state={}, summary={})

        await sandboxed_execute(
            tool, ppt_state={}, params={"v": 1}, target=None, ctx=ctx
        )
        tool.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_timeout_raises_tool_execution_error(self):
        import asyncio

        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(10)
            return ToolOutput(new_state={}, summary={})

        tool = _FakeTool()
        tool.descriptor.timeout_sec = 0.01
        tool.execute = slow_execute

        with pytest.raises(ToolExecutionError) as exc:
            await sandboxed_execute(
                tool, ppt_state={}, params={"v": 1}, target=None, ctx=_ctx()
            )
        assert exc.value.code == "timeout"
        assert exc.value.retryable is True
