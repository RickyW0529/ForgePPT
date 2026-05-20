from typing import Any

from prefect import flow

from models.workflow_def import AgentNodeConfig, WorkflowDef, WorkflowNode
from workflow.dag import topological_sort, validate_dag
from workflow.executors import (
    run_agent_node,
    run_export_node,
    run_merge_node,
    run_page_allocator_node,
    run_upload_node,
)


def _get_export_node_id(nodes: dict[str, WorkflowNode]) -> str:
    exports = [nid for nid, n in nodes.items() if n.type == "export"]
    if not exports:
        raise ValueError("No export node found")
    return exports[0]


@flow(name="forgeppt-workflow")
async def execute_workflow(workflow_def: WorkflowDef, file_path: str) -> str:
    """Dynamically construct and execute a Prefect Flow from user-defined DAG.

    Returns the final export file path.
    """
    validate_dag(workflow_def)

    nodes = {n.id: n for n in workflow_def.nodes}
    topo_order = topological_sort(workflow_def)

    future_cache: dict[str, Any] = {}

    for node_id in topo_order:
        node = nodes[node_id]
        preds = workflow_def.get_predecessors(node_id)

        if node.type == "upload":
            future_cache[node_id] = run_upload_node.submit(node_id=node.id, file_path=file_path)

        elif node.type == "page_allocator":
            upstream = future_cache[preds[0]]
            future_cache[node_id] = run_page_allocator_node.submit(node_id=node.id, ppt_state=upstream)

        elif node.type == "agent":
            upstream = future_cache[preds[0]]
            config = AgentNodeConfig.model_validate(node.data)
            edge_scope = None
            for e in workflow_def.edges:
                if e.target == node_id and e.data.get("pageScope"):
                    edge_scope = e.data["pageScope"]
                    break
            future_cache[node_id] = run_agent_node.submit(
                node_id=node.id, ppt_state=upstream, config=config, edge_scope=edge_scope
            )

        elif node.type == "merge":
            upstream_futures = [future_cache[p] for p in preds]
            strategy = node.data.get("mergeStrategy", "last_write_wins")
            future_cache[node_id] = run_merge_node.submit(node_id=node.id, inputs=upstream_futures, merge_strategy=strategy)

        elif node.type == "export":
            upstream = future_cache[preds[0]]
            future_cache[node_id] = run_export_node.submit(node_id=node.id, ppt_state=upstream)

    final_future = future_cache[_get_export_node_id(nodes)]
    return final_future.result()
