"""Tests for trace store (Module 7)."""

from __future__ import annotations

import pytest

from agent_platform.orchestration.plans import AgentPlan, AgentTrace, StepResult
from agent_platform.providers.models import TokenUsage
from agent_platform.trace.store import TraceStore


@pytest.fixture
def trace_store(tmp_path):
    path = tmp_path / "traces.db"
    store = TraceStore(db_path=str(path))
    return store


@pytest.mark.asyncio
async def test_save_and_list(trace_store):
    trace = AgentTrace(
        node_id="agent-1",
        status="success",
        plan=AgentPlan(summary="test plan", steps=[]),
        step_results=[StepResult(step_id="s1", status="ok")],
    )
    await trace_store.save(trace, workflow_id="wf-1")

    traces = await trace_store.list_traces()
    assert len(traces) == 1
    assert traces[0]["node_id"] == "agent-1"
    assert traces[0]["workflow_id"] == "wf-1"
    assert traces[0]["status"] == "success"
    assert traces[0]["plan"] is not None


@pytest.mark.asyncio
async def test_filter_by_workflow_id(trace_store):
    trace1 = AgentTrace(node_id="agent-1", status="success")
    trace2 = AgentTrace(node_id="agent-2", status="partial")
    await trace_store.save(trace1, workflow_id="wf-1")
    await trace_store.save(trace2, workflow_id="wf-2")

    traces = await trace_store.list_traces(workflow_id="wf-1")
    assert len(traces) == 1
    assert traces[0]["node_id"] == "agent-1"


@pytest.mark.asyncio
async def test_filter_by_node_id(trace_store):
    trace1 = AgentTrace(node_id="agent-1", status="success")
    trace2 = AgentTrace(node_id="agent-2", status="failed")
    await trace_store.save(trace1, workflow_id="wf-1")
    await trace_store.save(trace2, workflow_id="wf-1")

    traces = await trace_store.list_traces(node_id="agent-2")
    assert len(traces) == 1
    assert traces[0]["node_id"] == "agent-2"


@pytest.mark.asyncio
async def test_empty_list(trace_store):
    traces = await trace_store.list_traces()
    assert traces == []


@pytest.mark.asyncio
async def test_save_with_tokens_and_latency(trace_store):
    trace = AgentTrace(
        node_id="agent-1",
        status="success",
        tokens=TokenUsage(input_tokens=100, output_tokens=50),
        latency_ms=1234,
    )
    await trace_store.save(trace, workflow_id="wf-1")

    traces = await trace_store.list_traces()
    assert len(traces) == 1
    assert traces[0]["latency_ms"] == 1234
    assert traces[0]["tokens"] is not None
