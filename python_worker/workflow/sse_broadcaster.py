import asyncio
from typing import Any

# Global event queue store: workflow_id -> Queue
_workflow_events: dict[str, asyncio.Queue[dict]] = {}


def register_workflow(workflow_id: str) -> None:
    """Register a new workflow for SSE event collection."""
    _workflow_events[workflow_id] = asyncio.Queue(maxsize=200)


def broadcast_sse(node_id: str, status: str, **kwargs: Any) -> None:
    """Broadcast a node status event.

    This iterates all active workflows and places the event in their queues.
    In production, use a proper pub/sub system (Redis, etc.).
    """
    event = {"node_id": node_id, "status": status, **kwargs}
    for queue in _workflow_events.values():
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def get_event_queue(workflow_id: str) -> asyncio.Queue[dict] | None:
    """Get the event queue for a workflow."""
    return _workflow_events.get(workflow_id)


def unregister_workflow(workflow_id: str) -> None:
    """Remove a workflow's event queue to prevent memory leaks."""
    _workflow_events.pop(workflow_id, None)
