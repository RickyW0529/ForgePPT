from collections import deque

from models.workflow_def import WorkflowDef


def validate_dag(wf: WorkflowDef) -> None:
    """Validate workflow DAG constraints.

    Raises:
        ValueError: If DAG is invalid (cycle, missing nodes, disconnected).
    """
    node_ids = {n.id for n in wf.nodes}

    # Exactly one upload
    upload_nodes = [n for n in wf.nodes if n.type == "upload"]
    if len(upload_nodes) != 1:
        raise ValueError(f"Expected exactly one upload node, found {len(upload_nodes)}")

    # At least one export
    export_nodes = [n for n in wf.nodes if n.type == "export"]
    if len(export_nodes) < 1:
        raise ValueError("Expected at least one export node")

    # All edge endpoints exist
    for edge in wf.edges:
        if edge.source not in node_ids:
            raise ValueError(f"Edge references unknown source: {edge.source}")
        if edge.target not in node_ids:
            raise ValueError(f"Edge references unknown target: {edge.target}")

    # Cycle detection (Kahn's algorithm)
    in_degree = {n.id: 0 for n in wf.nodes}
    adj = {n.id: [] for n in wf.nodes}
    for edge in wf.edges:
        adj[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    queue = deque([n for n, d in in_degree.items() if d == 0])
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(wf.nodes):
        raise ValueError("Workflow graph contains a cycle")

    # Disconnected subgraph check: all nodes must be reachable from upload
    upload_id = upload_nodes[0].id
    reachable = set()
    stack = [upload_id]
    while stack:
        cur = stack.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        for succ in wf.get_successors(cur):
            if succ not in reachable:
                stack.append(succ)

    if reachable != node_ids:
        unreachable = node_ids - reachable
        raise ValueError(f"Disconnected subgraph detected: {unreachable}")


def topological_sort(wf: WorkflowDef) -> list[str]:
    """Return a topological ordering of node IDs."""
    in_degree = {n.id: 0 for n in wf.nodes}
    adj = {n.id: [] for n in wf.nodes}
    for edge in wf.edges:
        adj[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    queue = deque([n for n, d in in_degree.items() if d == 0])
    result = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(wf.nodes):
        raise ValueError("Cycle detected during topological sort")
    return result
