### Task 1: Workflow Types & Zustand Store

**Files:**
- Create: `frontend/src/types/workflow.ts`
- Create: `frontend/src/stores/useWorkflowStore.ts`

---

- [ ] **Step 1: Write workflow types**

Create `frontend/src/types/workflow.ts`:

```typescript
export type TaskStatus = 'idle' | 'pending' | 'processing' | 'completed' | 'error';

export type NodeType = 'upload' | 'page_allocator' | 'agent' | 'merge' | 'export';

export interface Position {
  x: number;
  y: number;
}

export interface WorkflowNodeData {
  // upload
  fileName?: string;
  // agent
  role?: string;
  prompt?: string;
  temperature?: number;
  model?: string;
  pageScope?: number[];
  // page_allocator
  branches?: Record<string, number[]>;
  // merge
  mergeStrategy?: 'last_write_wins' | 'error_on_conflict';
  // common
  status: TaskStatus;
}

export interface WorkflowDef {
  workflow_id: string;
  nodes: Array<{
    id: string;
    type: NodeType;
    position: Position;
    data: WorkflowNodeData;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
  }>;
}
```

---

- [ ] **Step 2: Write Zustand store**

Create `frontend/src/stores/useWorkflowStore.ts`:

```typescript
import { create } from 'zustand';
import type { Node, Edge } from '@xyflow/react';
import type { WorkflowNodeData, TaskStatus } from '@/types/workflow';

interface WorkflowState {
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  isExecuting: boolean;
  workflowId: string | null;
  exportPath: string | null;

  // Actions
  setNodes: (nodes: Node<WorkflowNodeData>[] | ((prev: Node<WorkflowNodeData>[]) => Node<WorkflowNodeData>[])) => void;
  setEdges: (edges: Edge[] | ((prev: Edge[]) => Edge[])) => void;
  addNode: (node: Node<WorkflowNodeData>) => void;
  updateNodeData: (nodeId: string, data: Partial<WorkflowNodeData>) => void;
  removeNode: (nodeId: string) => void;
  setSelectedNodeId: (id: string | null) => void;
  setNodeStatus: (nodeId: string, status: TaskStatus) => void;
  setExecuting: (v: boolean) => void;
  setWorkflowId: (id: string | null) => void;
  setExportPath: (path: string | null) => void;
  resetExecution: () => void;
  reset: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  isExecuting: false,
  workflowId: null,
  exportPath: null,

  setNodes: (updater) =>
    set((state) => ({
      nodes: typeof updater === 'function' ? updater(state.nodes) : updater,
    })),

  setEdges: (updater) =>
    set((state) => ({
      edges: typeof updater === 'function' ? updater(state.edges) : updater,
    })),

  addNode: (node) =>
    set((state) => ({
      nodes: [...state.nodes, node],
    })),

  updateNodeData: (nodeId, data) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n
      ),
    })),

  removeNode: (nodeId) =>
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== nodeId),
      edges: state.edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
      selectedNodeId: state.selectedNodeId === nodeId ? null : state.selectedNodeId,
    })),

  setSelectedNodeId: (id) => set({ selectedNodeId: id }),

  setNodeStatus: (nodeId, status) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, status } } : n
      ),
    })),

  setExecuting: (v) => set({ isExecuting: v }),
  setWorkflowId: (id) => set({ workflowId: id }),
  setExportPath: (path) => set({ exportPath: path }),

  resetExecution: () =>
    set((state) => ({
      isExecuting: false,
      workflowId: null,
      exportPath: null,
      nodes: state.nodes.map((n) => ({ ...n, data: { ...n.data, status: 'idle' } })),
    })),

  reset: () =>
    set({
      nodes: [],
      edges: [],
      selectedNodeId: null,
      isExecuting: false,
      workflowId: null,
      exportPath: null,
    }),
}));
```

---

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend
npx tsc --noEmit
```

Expected: No errors.

---

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/workflow.ts frontend/src/stores/useWorkflowStore.ts
git commit -m "feat: add workflow types and Zustand store for agent canvas

Co-Authored-By: Claude <noreply@anthropic.com>"
```
