# Agent Workflow Orchestration Design

## Goal

Transform the current fixed 3-node pipeline (upload → editor → export) into a **user-composable Agent workflow canvas**. Users can drag Agent nodes onto a canvas, connect them into arbitrary DAGs (branches, parallel paths, merges), assign page scopes per branch, and execute the entire graph on the backend with real-time SSE progress streaming.

Each Agent is an LLM-powered editing unit with a predefined role (text refinement, color optimization, layout design, etc.) but user-configurable parameters (prompt, temperature, model, page scope). Agents communicate only through their upstream predecessor's output — no shared global state beyond the initial PPTState.

## Architecture

### Two-Layer Execution Model

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (React Flow)                        │
│  Canvas: drag nodes, draw edges, configure node parameters       │
│  "Execute" → POST /api/v1/workflows                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend: Gateway + Worker                     │
│                                                                  │
│  ┌──────────────────────┐    ┌────────────────────────────────┐ │
│  │  DAG Orchestrator    │    │   Agent Nodes (LangChain)      │ │
│  │  (Prefect 3)          │───▶│   - TextRefinerAgent            │ │
│  │                      │    │   - ColorOptimizerAgent          │ │
│  │  Responsibilities:   │    │   - LayoutDesignerAgent          │ │
│  │  - Topology sort     │    │   - (more predefined roles)      │ │
│  │  - Parallel dispatch │    │                                  │ │
│  │  - State merge       │    │  Each Agent:                     │ │
│  │  - SSE broadcast     │    │  - Receives full PPTState        │ │
│  │                      │    │  - Outputs full PPTState         │ │
│  └──────────────────────┘    │  - Internal LLM + Tool Calling   │ │
│                              └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**宏观编排层 (DAG Orchestrator):**
- **Prefect 3** — handles topology, parallel execution, retries, and task caching
- No LangGraph at this layer
- Receives a workflow definition JSON from frontend
- Dynamically builds Prefect Flow at runtime, dispatches Agent nodes as Prefect Tasks, merges state

**微观 Agent 层:**
- Each Agent is a self-contained LangChain/LangGraph unit
- Has its own system prompt, tool set, and LLM configuration
- Input: `PPTState` (or filtered subset based on page scope)
- Output: `PPTState` (modified pages + untouched pages carried forward)

## Agent Definition

### Predefined Agent Roles

| Role | System Prompt Focus | Available Tools | Default Page Scope |
|------|---------------------|-----------------|-------------------|
| `text_refiner` | Rewrite, summarize, translate text | `ppt_apply_text` | All pages |
| `color_optimizer` | Adjust font colors, suggest palettes | `ppt_apply_style` | All pages |
| `layout_designer` | Reposition elements, resize shapes | `ppt_apply_layout` | All pages |
| `svg_generator` | Create SVG placeholders | `ppt_apply_svg` | Targeted slides |
| `theme_designer` | Overall style theming | `ppt_apply_style` | All pages |

### User-Configurable Parameters (per node)

```typescript
interface AgentNodeConfig {
  role: string;           // predefined role key
  prompt: string;         // user override / addition to system prompt
  temperature: number;    // 0.0 - 1.0
  model?: string;         // override default model
  pageScope: number[];    // which pages this agent processes (1-based)
}
```

## Data Flow

### Core Principle

> **Within a branch: full PPTState is passed sequentially. Between branches: isolation until merge.**

### Sub-Flow (Branch) Internal Flow

```
PageAllocator Node
  │
  ├─→ [Branch A: pages 1, 3]
  │     TextRefinerAgent (processes pages 1,3)
  │       → outputs full PPTState (pages 1,3 modified, page 2 untouched)
  │     ColorOptimizerAgent (receives above, processes pages 1,3)
  │       → outputs full PPTState (pages 1,3 styled, page 2 untouched)
  │     (→ continues to MergeAgent or End)
  │
  └─→ [Branch B: pages 2]
        LayoutDesignerAgent (processes page 2)
          → outputs full PPTState (page 2 modified, pages 1,3 untouched)
        (→ continues to MergeAgent or End)
```

Each Agent in a branch receives the **complete PPTState from its direct predecessor**, including pages it does NOT modify. This ensures:
- Downstream Agents see upstream changes to all pages
- No context loss when passing between Agents
- Agent implementations remain simple (always read/write full state)

### Page Overlap Handling

If two branches both modify the same page (e.g., Branch A modifies page 1, Branch B also modifies page 1), the conflict is resolved at **merge time**, not during execution.

**Merge Strategy Options (user-configurable per merge node):**

| Strategy | Behavior |
|----------|----------|
| `last_write_wins` | Later branch in DAG order overwrites earlier |
| `error_on_conflict` | Throw error if same page modified by multiple branches |
| `smart_merge` | Attempt field-level merge (text from A, style from B) — future work |

Default: `last_write_wins`

### State Shape at Merge

```python
class MergeInput(TypedDict):
    branch_id: str
    ppt_state: PPTState
    modified_pages: list[int]   # which pages this branch actually touched

class MergeNode:
    """Wait for all upstream branches, then merge their outputs."""
    def execute(self, inputs: list[MergeInput]) -> PPTState:
        base = inputs[0]["ppt_state"]
        for inp in inputs[1:]:
            for page_num in inp["modified_pages"]:
                base.slides[page_num - 1] = inp["ppt_state"].slides[page_num - 1]
        return base
```

## Node Types

### 1. Upload Node (`upload`)
- **Role:** Entry point. Parses uploaded PPTX into `PPTState`.
- **Output:** `PPTState`
- **No LLM involved.**

### 2. Page Allocator Node (`page_allocator`)
- **Role:** Splits PPTState into branch contexts based on user configuration.
- **Configuration:**
  ```json
  {
    "branches": {
      "branch-a": [1, 3],
      "branch-b": [2]
    }
  }
  ```
- **Behavior:** Not an LLM node. Pure data routing. Passes **full PPTState** to each downstream branch, but marks each branch's `pageScope`.
- **Output:** Full `PPTState` to each downstream edge.

### 3. Agent Node (`agent`)
- **Role:** LLM-powered editing unit.
- **Input:** `PPTState` from predecessor + `AgentNodeConfig`
- **Output:** `PPTState` (modified pages changed, others carried forward)
- **Execution:** Calls internal LangChain/LangGraph pipeline.

### 4. Merge Node (`merge`)
- **Role:** Waits for all upstream branches to complete, then merges their `PPTState` outputs.
- **Configuration:** `mergeStrategy` (default: `last_write_wins`)
- **Input:** List of `PPTState` from all upstream branches
- **Output:** Single merged `PPTState`

### 5. Export Node (`export`)
- **Role:** Final node. Recomposes PPTX from `PPTState`.
- **Output:** File path to generated PPTX.
- **No LLM involved.**

## Workflow Definition Format (Frontend → Backend)

```json
{
  "workflow_id": "uuid",
  "nodes": [
    {
      "id": "node-upload",
      "type": "upload",
      "position": {"x": 100, "y": 200},
      "data": {}
    },
    {
      "id": "node-allocator",
      "type": "page_allocator",
      "position": {"x": 300, "y": 200},
      "data": {
        "branches": {
          "branch-a": [1, 3],
          "branch-b": [2]
        }
      }
    },
    {
      "id": "node-text-a",
      "type": "agent",
      "position": {"x": 500, "y": 100},
      "data": {
        "role": "text_refiner",
        "prompt": "Make the text more professional",
        "temperature": 0.3,
        "pageScope": [1, 3]
      }
    },
    {
      "id": "node-color-b",
      "type": "agent",
      "position": {"x": 500, "y": 300},
      "data": {
        "role": "color_optimizer",
        "prompt": "Use dark blue theme",
        "temperature": 0.3,
        "pageScope": [2]
      }
    },
    {
      "id": "node-merge",
      "type": "merge",
      "position": {"x": 700, "y": 200},
      "data": {
        "mergeStrategy": "last_write_wins"
      }
    },
    {
      "id": "node-export",
      "type": "export",
      "position": {"x": 900, "y": 200},
      "data": {}
    }
  ],
  "edges": [
    {"id": "e1", "source": "node-upload", "target": "node-allocator"},
    {"id": "e2a", "source": "node-allocator", "target": "node-text-a"},
    {"id": "e2b", "source": "node-allocator", "target": "node-color-b"},
    {"id": "e3a", "source": "node-text-a", "target": "node-merge"},
    {"id": "e3b", "source": "node-color-b", "target": "node-merge"},
    {"id": "e4", "source": "node-merge", "target": "node-export"}
  ]
}
```

## DAG Orchestrator Execution Model (Prefect 3)

### Phase 1: Validation
- Check DAG is acyclic (Kahn's algorithm)
- Ensure exactly one upload node and at least one export node
- Validate all node types are supported
- Validate page allocator branch names match downstream edges

### Phase 2: Flow Build & Execution

Prefect 3 handles topological sorting, parallel dispatch, and dependency resolution automatically when task futures are passed as inputs. We build the DAG dynamically at runtime.

```python
from prefect import flow, task
from prefect.futures import PrefectFuture

@task(name="{node_id}", retries=1, retry_delay_seconds=5)
async def run_agent_node(node: Node, ppt_state: PPTState, config: AgentNodeConfig) -> PPTState:
    """Execute a single Agent node (LangChain/LangGraph pipeline)."""
    broadcast_sse(node.id, "started")
    result = await agent_registry.execute(node.data.role, ppt_state, config)
    broadcast_sse(node.id, "completed", output_summary=result.summary())
    return result

@task(name="{node_id}")
def run_merge_node(node: Node, inputs: list[PPTState], merge_strategy: str) -> PPTState:
    """Merge multiple branch outputs into a single PPTState."""
    broadcast_sse(node.id, "started")
    result = merge_states(inputs, strategy=merge_strategy)
    broadcast_sse(node.id, "completed")
    return result

@task(name="{node_id}")
def run_upload_node(node: Node, file_path: str) -> PPTState:
    broadcast_sse(node.id, "started")
    result = parse_pptx(file_path)
    broadcast_sse(node.id, "completed")
    return result

@task(name="{node_id}")
def run_export_node(node: Node, ppt_state: PPTState) -> str:
    broadcast_sse(node.id, "started")
    export_path = recompose_pptx(ppt_state)
    broadcast_sse(node.id, "completed", export_path=export_path)
    return export_path

@task(name="{node_id}")
def run_page_allocator(node: Node, ppt_state: PPTState) -> PPTState:
    """Pure routing node; page scope is carried in downstream edge config."""
    broadcast_sse(node.id, "started")
    broadcast_sse(node.id, "completed")
    return ppt_state

@flow(name="forgeppt-workflow")
async def execute_workflow(workflow_def: WorkflowDef, file_path: str) -> str:
    """
    Dynamically construct a Prefect Flow from the user-defined DAG.
    Returns the final export file path.
    """
    nodes = {n.id: n for n in workflow_def.nodes}
    edges = workflow_def.edges
    topo_order = topological_sort(nodes, edges)

    # Map node_id -> PrefectFuture (or concrete value for upload)
    future_cache: dict[str, PrefectFuture | PPTState | str] = {}

    for node_id in topo_order:
        node = nodes[node_id]
        preds = get_predecessors(node_id, edges)

        if node.type == "upload":
            future_cache[node_id] = run_upload_node.submit(node, file_path)

        elif node.type == "page_allocator":
            upstream = future_cache[preds[0]]
            future_cache[node_id] = run_page_allocator.submit(node, upstream)

        elif node.type == "agent":
            upstream = future_cache[preds[0]]
            future_cache[node_id] = run_agent_node.submit(
                node, upstream, node.data
            )

        elif node.type == "merge":
            # Collect all upstream branch futures
            upstream_futures = [future_cache[p] for p in preds]
            future_cache[node_id] = run_merge_node.submit(
                node, upstream_futures, node.data.mergeStrategy
            )

        elif node.type == "export":
            upstream = future_cache[preds[0]]
            future_cache[node_id] = run_export_node.submit(node, upstream)

    # Wait for the final export node and return its result
    final_future = future_cache[get_export_node_id(nodes)]
    return await final_future.result()
```

### Key Prefect Behaviors

| Concern | How Prefect 3 Handles It |
|---------|--------------------------|
| **Topological sort** | Implicit via future dependencies. `submit()` returns immediately; Prefect internally builds the DAG. |
| **Parallel execution** | Branches with independent futures run in parallel automatically. No manual `asyncio.gather()` needed. |
| **Merge synchronization** | `run_merge_node` receives futures from all upstream branches; Prefect ensures all complete before the merge task starts. |
| **Retries** | `@task(retries=1)` on Agent nodes. Upload/export/merge are deterministic, no retries needed. |
| **Caching** | Enable `@task(cache_key_fn=...)` for idempotent nodes (upload, export) to skip re-execution on retry. |
| **Timeouts** | `@task(timeout_seconds=60)` per Agent node. |

### State Resolution per Node

Because each task receives the **concrete result** of its predecessor (Prefect resolves futures before passing to the task), task implementations remain simple:

```python
# Inside run_agent_node — ppt_state is already the resolved PPTState
async def run_agent_node(node, ppt_state: PPTState, config: AgentNodeConfig):
    # ppt_state contains ALL pages (including unmodified ones from upstream)
    modified_state = await agent.execute(ppt_state, config)
    return modified_state

# Inside run_merge_node — inputs is a list of resolved PPTStates
async def run_merge_node(node, inputs: list[PPTState], merge_strategy: str):
    base = inputs[0]
    for branch_state in inputs[1:]:
        for page_num in detect_modified_pages(branch_state):
            base.slides[page_num - 1] = branch_state.slides[page_num - 1]
    return base
```

## API Design

### POST /api/v1/workflows

**Request:**
```json
{
  "workflow_definition": { /* nodes + edges JSON */ },
  "file_path": "/tmp/forgeppt_uploads/xxx.pptx"
}
```

**Response (202 Accepted):**
```json
{
  "workflow_id": "uuid",
  "status": "running",
  "message": "Workflow execution started"
}
```

### SSE /api/v1/workflows/{workflow_id}/events

Stream events:
```json
{"node_id": "node-text-a", "status": "started", "timestamp": "..."}
{"node_id": "node-text-a", "status": "completed", "output_summary": "..."}
{"node_id": "node-color-b", "status": "started", "timestamp": "..."}
{"node_id": "node-color-b", "status": "completed", "output_summary": "..."}
{"node_id": "node-merge", "status": "started", "timestamp": "..."}
{"node_id": "node-merge", "status": "completed", "timestamp": "..."}
{"node_id": "node-export", "status": "completed", "export_path": "..."}
```

### GET /api/v1/workflows/{workflow_id}

Poll for final result:
```json
{
  "workflow_id": "uuid",
  "status": "completed",
  "export_path": "/tmp/forgeppt_output_xxx.pptx",
  "node_results": {
    "node-text-a": {...},
    "node-color-b": {...}
  }
}
```

## Frontend Canvas Changes

### Node Palette
- Sidebar panel with draggable Agent role cards
- Predefined roles: Text Refiner, Color Optimizer, Layout Designer, SVG Generator, Theme Designer
- Special nodes: Upload, Page Allocator, Merge, Export

### Edge Behavior
- Default: directed flow (source → target)
- Page Allocator outputs are labeled with branch names
- Merge node auto-detects incoming edges as upstream branches

### Node Configuration Panel
When clicking a node, ParamPanel shows:
- **Agent Nodes:** Role selector, prompt textarea, temperature slider, model dropdown, page scope input
- **Page Allocator:** Branch editor (add/remove branches, assign page numbers per branch)
- **Merge Node:** Merge strategy dropdown

### Execution Flow
1. User builds graph on canvas
2. Clicks "Execute" button in header
3. Frontend serializes nodes + edges + data to JSON
4. POSTs to `/api/v1/workflows`
5. Opens SSE connection to `/api/v1/workflows/{id}/events`
6. Updates node borders/colors based on SSE events (processing → completed → error)
7. Export node becomes clickable download link when done

## Error Handling

### Node-Level Errors
- If an Agent node fails (LLM error, tool error, etc.), its status becomes `error`
- Downstream nodes that depend on it are **skipped**
- Merge nodes wait only for successful upstream branches
- SSE emits `{"node_id": "...", "status": "error", "error": "..."}`

### DAG-Level Errors
- Cyclic graph → 400 Bad Request at submission time
- Missing upload/export node → 400 Bad Request
- Disconnected subgraphs → 400 Bad Request
- Timeout per node (configurable, default 60s) → node marked `error`

### Recovery
- Users can re-execute a failed workflow after fixing the failing node's configuration
- The orchestrator reuses cached results from successful nodes (idempotent execution)

## State Persistence

### In-Memory Cache (MVP)
- Node execution results cached in memory during workflow run
- If a node is re-executed (retry), cache is invalidated for that node and all descendants
- No database required for MVP

### Future: Redis / Persistent Store
- For long-running workflows and fault tolerance
- Store intermediate PPTState snapshots
- Enable "resume from failed node"

## Out of Scope for This Design

1. **Loops / Cycles in DAG** — Only acyclic graphs. Iterative refinement can be simulated by user manually chaining the same Agent multiple times.
2. **Conditional Branching** — No `if/else` edges based on content. All branching is static based on page allocation.
3. **Human-in-the-Loop Nodes** — No pause-and-resume for user approval mid-workflow.
4. **Smart Merge (field-level)** — `smart_merge` strategy is listed but marked as future work. MVP only supports `last_write_wins` and `error_on_conflict`.
5. **Custom Agent Creation** — Users cannot define entirely new Agent roles with custom tool sets. Only configure parameters of predefined roles.

## Migration from Current System

### Current Fixed Pipeline
```
upload → editor (refine/theme/placeholder) → export
```

### Equivalent User-Defined Workflow
```
upload → page_allocator (all pages → single branch)
  → agent (theme)
  → export
```

The fixed pipeline becomes a **preset template** that users can load with one click, then modify.

## Success Criteria

1. User can build a workflow with at least 2 parallel branches, each with 2+ Agent nodes
2. Page Allocator correctly routes pages to branches
3. Parallel branches execute concurrently (verified by logs/timestamps)
4. Merge node correctly combines branch outputs
5. SSE events show real-time progress per node
6. Final export produces a valid PPTX with all branch changes applied
7. A failed node does not crash the entire workflow; downstream dependents are skipped gracefully
