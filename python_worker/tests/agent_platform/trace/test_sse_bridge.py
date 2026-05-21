"""Tests for trace SSE bridge (Module 7)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent_platform.orchestration.plans import AgentPlan, AgentTrace, StepResult
from agent_platform.trace.sse_bridge import emit_trace_sse


@pytest.fixture
def mock_broadcast_sse():
    with patch("workflow.sse_broadcaster.broadcast_sse") as mock:
        yield mock


def test_emit_trace_sse_calls_broadcast_sse(mock_broadcast_sse):
    trace = AgentTrace(
        node_id="agent-1",
        status="success",
        plan=AgentPlan(summary="dark theme", steps=[]),
    )
    emit_trace_sse("node-1", trace)

    assert mock_broadcast_sse.call_count == 1
    args, kwargs = mock_broadcast_sse.call_args
    assert args[0] == "node-1"
    assert args[1] == "completed"
    assert kwargs["trace_status"] == "success"
    assert kwargs["plan_summary"] == "dark theme"
    assert kwargs["step_count"] == 0
    assert kwargs["failure_count"] == 0


def test_emit_trace_sse_emits_step_events(mock_broadcast_sse):
    trace = AgentTrace(
        node_id="agent-1",
        status="partial",
        plan=AgentPlan(summary="multi-step", steps=[]),
        step_results=[
            StepResult(step_id="s1", status="ok"),
            StepResult(step_id="s2", status="error", error="timeout"),
        ],
    )
    emit_trace_sse("node-1", trace)

    assert mock_broadcast_sse.call_count == 3

    # First call: completed
    args, kwargs = mock_broadcast_sse.call_args_list[0]
    assert args[1] == "completed"
    assert kwargs["step_count"] == 2

    # Second call: step 0
    args, kwargs = mock_broadcast_sse.call_args_list[1]
    assert args[1] == "step_completed"
    assert kwargs["step_index"] == 0
    assert kwargs["step_status"] == "ok"
    assert kwargs["step_tool"] is None

    # Third call: step 1
    args, kwargs = mock_broadcast_sse.call_args_list[2]
    assert args[1] == "step_completed"
    assert kwargs["step_index"] == 1
    assert kwargs["step_status"] == "error"
