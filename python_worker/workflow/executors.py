from prefect import task

from agent_platform.orchestration.runner import run_agent_subgraph, run_merge_subgraph
from agent_platform.trace.sse_bridge import emit_trace_sse
from models.ppt_state import PPTState
from models.workflow_def import AgentNodeConfig, MergeNodeConfig
from services.parser import parse_pptx
from services.recomposer import recompose_pptx

from workflow.sse_broadcaster import broadcast_sse


@task(name="{node_id}", retries=1, retry_delay_seconds=5, timeout_seconds=60)
async def run_agent_node(node_id: str, ppt_state: PPTState, config: AgentNodeConfig, edge_scope: list[int] | None = None) -> PPTState:
    """Execute a single Agent node."""
    broadcast_sse(node_id, "started")
    result, trace = await run_agent_subgraph(ppt_state, config, edge_scope=edge_scope)
    emit_trace_sse(node_id, trace)
    return result


@task(name="{node_id}", retries=1, timeout_seconds=120)
async def run_merge_node(node_id: str, inputs: list[PPTState], config: MergeNodeConfig) -> PPTState:
    """Merge multiple branch outputs."""
    broadcast_sse(node_id, "started")
    result, trace = await run_merge_subgraph(inputs, config)
    emit_trace_sse(node_id, trace)
    return result


@task(name="{node_id}", retries=1, timeout_seconds=60)
def run_upload_node(node_id: str, file_path: str) -> PPTState:
    """Parse uploaded PPTX into PPTState."""
    broadcast_sse(node_id, "started")
    result = parse_pptx(file_path)
    broadcast_sse(node_id, "completed")
    return result


@task(name="{node_id}", retries=1, timeout_seconds=60)
def run_export_node(node_id: str, ppt_state: PPTState) -> str:
    """Recompose PPTX from PPTState."""
    broadcast_sse(node_id, "started")
    output_path = f"/tmp/forgeppt_output_{ppt_state.source_file.replace('/', '_')}"
    recompose_pptx(ppt_state.source_file, ppt_state, output_path)
    broadcast_sse(node_id, "completed", export_path=output_path)
    return output_path


@task(name="{node_id}")
def run_page_allocator_node(node_id: str, ppt_state: PPTState) -> PPTState:
    """Pure routing node; page scope is carried in downstream edge config."""
    broadcast_sse(node_id, "started")
    broadcast_sse(node_id, "completed")
    return ppt_state
