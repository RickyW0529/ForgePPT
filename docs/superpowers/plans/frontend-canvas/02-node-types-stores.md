# 02 - Node Types and Zustand Stores

**Files:**
- Create: `frontend/src/types/nodes.ts`
- Create: `frontend/src/stores/useTaskStore.ts`
- Create: `frontend/src/stores/useUIStore.ts`
- Create: `frontend/src/stores/useFileStore.ts`
- Create: `frontend/src/stores/useSSEStore.ts`
- Create: `frontend/tests/stores.test.ts`

---

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/tests/stores.test.ts
import { describe, it, expect } from 'vitest';
import { useTaskStore } from '../src/stores/useTaskStore';
import { useUIStore } from '../src/stores/useUIStore';

describe('useTaskStore', () => {
  it('should initialize with idle status', () => {
    const state = useTaskStore.getState();
    expect(state.overallStatus).toBe('idle');
    expect(state.nodeStatuses).toEqual({});
  });

  it('should update node status', () => {
    useTaskStore.getState().setNodeStatus('editor', 'processing');
    expect(useTaskStore.getState().nodeStatuses['editor']).toBe('processing');
  });
});

describe('useUIStore', () => {
  it('should toggle sidebar', () => {
    const { toggleSidebar } = useUIStore.getState();
    toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/stores.test.ts`
Expected: FAIL with "Cannot find module '../src/stores/useTaskStore'"

- [ ] **Step 3: Write types**

```typescript
// frontend/src/types/nodes.ts
export type TaskStatus = 'idle' | 'pending' | 'processing' | 'completed' | 'error';

export type NodeType = 'uploadParser' | 'editor' | 'exporter';

export interface UploadNodeData {
  fileName?: string;
  status: TaskStatus;
}

export interface EditorNodeData {
  prompt: string;
  preview?: string;
  status: TaskStatus;
}

export interface ExporterNodeData {
  downloadUrl?: string;
  status: TaskStatus;
}
```

- [ ] **Step 4: Write stores**

```typescript
// frontend/src/stores/useTaskStore.ts
import { create } from 'zustand';
import type { TaskStatus } from '@/types/nodes';

interface TaskState {
  taskId: string | null;
  overallStatus: TaskStatus;
  nodeStatuses: Record<string, TaskStatus>;
  errorMessage: string | null;
  setTaskId: (id: string) => void;
  setOverallStatus: (status: TaskStatus) => void;
  setNodeStatus: (nodeId: string, status: TaskStatus) => void;
  setError: (msg: string | null) => void;
  reset: () => void;
}

export const useTaskStore = create<TaskState>((set) => ({
  taskId: null,
  overallStatus: 'idle',
  nodeStatuses: {},
  errorMessage: null,
  setTaskId: (id) => set({ taskId: id }),
  setOverallStatus: (status) => set({ overallStatus: status }),
  setNodeStatus: (nodeId, status) =>
    set((state) => ({
      nodeStatuses: { ...state.nodeStatuses, [nodeId]: status },
    })),
  setError: (msg) => set({ errorMessage: msg }),
  reset: () => set({ taskId: null, overallStatus: 'idle', nodeStatuses: {}, errorMessage: null }),
}));
```

```typescript
// frontend/src/stores/useUIStore.ts
import { create } from 'zustand';

interface UIState {
  sidebarOpen: boolean;
  selectedNodeId: string | null;
  activeTab: 'params' | 'prompt' | 'preview';
  toasts: Array<{ id: string; type: 'success' | 'error' | 'warning' | 'info'; message: string }>;
  toggleSidebar: () => void;
  setSelectedNodeId: (id: string | null) => void;
  setActiveTab: (tab: 'params' | 'prompt' | 'preview') => void;
  addToast: (toast: Omit<UIState['toasts'][0], 'id'>) => void;
  removeToast: (id: string) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  selectedNodeId: null,
  activeTab: 'params',
  toasts: [],
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSelectedNodeId: (id) => set({ selectedNodeId: id }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  addToast: (toast) =>
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id: Math.random().toString(36).slice(2) }],
    })),
  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}));
```

```typescript
// frontend/src/stores/useFileStore.ts
import { create } from 'zustand';

interface FileState {
  fileName: string | null;
  fileSize: number | null;
  parsedState: unknown | null;
  setFile: (name: string, size: number) => void;
  setParsedState: (state: unknown) => void;
  reset: () => void;
}

export const useFileStore = create<FileState>((set) => ({
  fileName: null,
  fileSize: null,
  parsedState: null,
  setFile: (name, size) => set({ fileName: name, fileSize: size }),
  setParsedState: (state) => set({ parsedState: state }),
  reset: () => set({ fileName: null, fileSize: null, parsedState: null }),
}));
```

```typescript
// frontend/src/stores/useSSEStore.ts
import { create } from 'zustand';

interface SSEState {
  connected: boolean;
  messages: Array<{ type: string; payload: unknown }>;
  setConnected: (v: boolean) => void;
  pushMessage: (msg: { type: string; payload: unknown }) => void;
  clearMessages: () => void;
}

export const useSSEStore = create<SSEState>((set) => ({
  connected: false,
  messages: [],
  setConnected: (v) => set({ connected: v }),
  pushMessage: (msg) =>
    set((state) => ({
      messages: [...state.messages, msg],
    })),
  clearMessages: () => set({ messages: [] }),
}));
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/stores.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/ frontend/src/stores/ frontend/tests/stores.test.ts
git commit -m "feat: add Zustand stores and node type definitions"
```
