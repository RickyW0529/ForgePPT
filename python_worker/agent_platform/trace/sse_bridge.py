"""Bridge AgentTrace events to SSE broadcaster."""

from __future__ import annotations

from agent_platform.orchestration.plans import AgentTrace


def emit_trace_sse(node_id: str, trace: AgentTrace) -> None:
    """Emit trace-derived SSE events for the frontend.

    Emits:
    - node status with trace metadata
    - step-level events if available
    """
    from workflow.sse_broadcaster import broadcast_sse

    broadcast_sse(
        node_id,
        "completed",
        trace_status=trace.status,
        plan_summary=getattr(trace.plan, "summary", None) if trace.plan else None,
        step_count=len(trace.step_results) if trace.step_results else 0,
        failure_count=len(trace.plan_failures) if trace.plan_failures else 0,
    )

    if trace.step_results:
        for i, step in enumerate(trace.step_results):
            broadcast_sse(
                node_id,
                "step_completed",
                step_index=i,
                step_status=step.status,
                step_tool=step.tool if hasattr(step, "tool") else None,
            )
