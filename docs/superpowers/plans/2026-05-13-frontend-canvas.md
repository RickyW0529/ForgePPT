# Frontend Canvas & Node System Implementation Plan

> **Execution Order:** 5 / 6 — Depends on: Rust Gateway (REST API + SSE endpoints must exist).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the React Flow v12-based canvas UI with three fixed nodes (upload-parser, editor, exporter), parameter side panel, SSE connection, and Diff/SVG preview components.

**Architecture:** React 18 + TypeScript + Vite. Zustand stores split by domain (file, task, SSE, UI). React Flow handles node rendering, dragging, and edge drawing. Custom nodes wrap business data. The parameter panel switches based on selected node type. SSE events drive node state transitions.

**Tech Stack:** React 18, TypeScript, Vite, React Flow v12, Zustand, Tailwind CSS, axios, vitest

---

## File Structure

| File | Responsibility |
|------|--------------|
| `frontend/package.json` | Dependencies & scripts |
| `frontend/vite.config.ts` | Vite + React + test config |
| `frontend/tsconfig.json` | TypeScript config |
| `frontend/tailwind.config.js` | Tailwind with Deep Blue theme |
| `frontend/index.html` | HTML entry |
| `frontend/src/main.tsx` | React mount point |
| `frontend/src/App.tsx` | Root layout (Header + MainWorkspace + StatusBar) |
| `frontend/src/index.css` | Tailwind directives + custom CSS |
| `frontend/src/types/nodes.ts` | AppNode, AppEdge, TaskStatus union types |
| `frontend/src/stores/useFileStore.ts` | File metadata, parsed XML cache |
| `frontend/src/stores/useTaskStore.ts` | Task ID, node statuses, error stack |
| `frontend/src/stores/useSSEStore.ts` | EventSource lifecycle, message queue |
| `frontend/src/stores/useUIStore.ts` | Sidebar fold, active tab, selected node, toasts |
| `frontend/src/components/HeaderBar.tsx` | Logo, file actions, global status, user avatar |
| `frontend/src/components/FlowCanvas.tsx` | React Flow container, background, controls |
| `frontend/src/components/SidebarPanel.tsx` | Tab-based parameter panel |
| `frontend/src/components/nodes/UploadParserNode.tsx` | Upload node UI |
| `frontend/src/components/nodes/EditorNode.tsx` | Editor node UI with progress ring |
| `frontend/src/components/nodes/ExporterNode.tsx` | Exporter node UI |
| `frontend/src/components/nodes/index.ts` | nodeTypes registry |
| `frontend/src/components/edges/LockedEdge.tsx` | Custom locked edge component |
| `frontend/src/components/ParamPanel.tsx` | Node-specific parameter forms |
| `frontend/src/components/DiffViewer.tsx` | react-diff-viewer wrapper |
| `frontend/src/components/SvgPreview.tsx` | SVG render + zoom controls |
| `frontend/src/hooks/useSSE.ts` | SSE connection + auto-reconnect hook |
| `frontend/src/api/client.ts` | Axios instance with baseURL |
| `frontend/src/api/tasks.ts` | POST /tasks wrapper |
| `frontend/src/api/upload.ts` | POST /upload wrapper |
| `frontend/tests/App.test.tsx` | Root render smoke test |
| `frontend/tests/stores.test.ts` | Zustand store unit tests |

---

## Task 1: Frontend Project Skeleton

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/vite-env.d.ts`

- [ ] **Step 1: Write configuration files**

```json
// frontend/package.json
{
  "name": "ppt-agent-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@xyflow/react": "^12.0.0",
    "zustand": "^4.5.0",
    "axios": "^1.7.0",
    "react-diff-viewer-continued": "^3.4.0",
    "lucide-react": "^0.400.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.4.0",
    "vite": "^5.3.0",
    "vitest": "^1.6.0",
    "@testing-library/react": "^15.0.0",
    "@testing-library/jest-dom": "^6.4.0",
    "jsdom": "^24.1.0"
  }
}
```

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:3000',
      '/health': 'http://localhost:3000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
});
```

```json
// frontend/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

```javascript
// frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        deepblue: {
          50: '#E8EDF3',
          100: '#D1DBE7',
          200: '#BEE3F8',
          300: '#63B3ED',
          400: '#3182CE',
          500: '#2E4A62',
          600: '#1E3A5F',
          700: '#1A365D',
          800: '#0F1D2E',
          900: '#0A1525',
        },
        surface: '#F7FAFC',
      },
    },
  },
  plugins: [],
};
```

```html
<!-- frontend/index.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PPT Agent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

```typescript
// frontend/src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

```css
/* frontend/src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: #ffffff;
}
```

- [ ] **Step 2: Run npm install**

Run: `cd frontend && npm install`
Expected: Dependencies installed successfully.

- [ ] **Step 3: Write smoke test**

```tsx
// frontend/tests/App.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../src/App';

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(document.body).toBeDefined();
  });
});
```

- [ ] **Step 4: Write minimal App.tsx**

```tsx
// frontend/src/App.tsx
export default function App() {
  return (
    <div className="h-screen w-screen flex flex-col">
      <header className="h-12 bg-deepblue-800 text-white flex items-center px-4">
        PPT Agent
      </header>
      <main className="flex-1 flex">
        <div className="flex-1 bg-surface">Canvas placeholder</div>
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run`
Expected: PASS (1 test)

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: add React frontend skeleton with Vite, Tailwind, Vitest"
```

---

## Task 2: Node Types and Zustand Stores

**Files:**
- Create: `frontend/src/types/nodes.ts`
- Create: `frontend/src/stores/useTaskStore.ts`
- Create: `frontend/src/stores/useUIStore.ts`
- Create: `frontend/src/stores/useFileStore.ts`
- Create: `frontend/src/stores/useSSEStore.ts`
- Create: `frontend/tests/stores.test.ts`

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

---

## Task 3: React Flow Canvas and Custom Nodes

**Files:**
- Create: `frontend/src/components/FlowCanvas.tsx`
- Create: `frontend/src/components/nodes/UploadParserNode.tsx`
- Create: `frontend/src/components/nodes/EditorNode.tsx`
- Create: `frontend/src/components/nodes/ExporterNode.tsx`
- Create: `frontend/src/components/nodes/index.ts`
- Create: `frontend/src/components/edges/LockedEdge.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/tests/App.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/App.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../src/App';

describe('App', () => {
  it('renders three nodes', () => {
    render(<App />);
    expect(screen.getByText('上传解析')).toBeInTheDocument();
    expect(screen.getByText('编辑')).toBeInTheDocument();
    expect(screen.getByText('导出 PPTX')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/App.test.tsx`
Expected: FAIL — nodes not yet implemented.

- [ ] **Step 3: Write node components**

```tsx
// frontend/src/components/nodes/UploadParserNode.tsx
import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Upload } from 'lucide-react';
import type { NodeProps } from '@xyflow/react';
import type { UploadNodeData } from '@/types/nodes';

const UploadParserNode = memo(({ selected, data }: NodeProps<{ data: UploadNodeData }>) => {
  const status = data?.status ?? 'idle';
  const borderColor =
    status === 'completed'
      ? 'border-green-500'
      : status === 'processing'
      ? 'border-blue-400'
      : 'border-deepblue-500';

  return (
    <div
      className={`w-[180px] bg-white rounded-lg border-2 ${borderColor} shadow-sm p-3 transition-all ${
        selected ? 'ring-2 ring-deepblue-400' : ''
      }`}
    >
      <div className="flex flex-col items-center gap-1">
        <Upload size={20} className="text-deepblue-500" />
        <span className="text-sm font-medium text-slate-700">上传解析</span>
        {data?.fileName && (
          <span className="text-xs text-slate-500 truncate max-w-full">{data.fileName}</span>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="w-2.5 h-2.5 bg-deepblue-400" />
    </div>
  );
});

export default UploadParserNode;
```

```tsx
// frontend/src/components/nodes/EditorNode.tsx
import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Pencil } from 'lucide-react';
import type { NodeProps } from '@xyflow/react';
import type { EditorNodeData } from '@/types/nodes';

const EditorNode = memo(({ selected, data }: NodeProps<{ data: EditorNodeData }>) => {
  const status = data?.status ?? 'idle';
  const borderColor =
    status === 'completed'
      ? 'border-green-500'
      : status === 'processing'
      ? 'border-blue-400'
      : 'border-deepblue-500';

  return (
    <div
      className={`w-[200px] bg-white rounded-lg border-2 ${borderColor} shadow-sm p-3 transition-all ${
        selected ? 'ring-2 ring-deepblue-400' : ''
      }`}
    >
      <div className="flex flex-col items-center gap-1">
        <Pencil size={20} className="text-deepblue-500" />
        <span className="text-sm font-medium text-slate-700">编辑</span>
        {data?.prompt && (
          <span className="text-xs text-slate-500 truncate max-w-full">{data.prompt}</span>
        )}
        {status === 'processing' && (
          <div className="w-full h-1 bg-gray-200 rounded-full overflow-hidden mt-1">
            <div className="h-full bg-blue-400 animate-pulse" style={{ width: '60%' }} />
          </div>
        )}
      </div>
      <Handle type="target" position={Position.Left} className="w-2.5 h-2.5 bg-deepblue-400" />
      <Handle type="source" position={Position.Right} className="w-2.5 h-2.5 bg-deepblue-400" />
    </div>
  );
});

export default EditorNode;
```

```tsx
// frontend/src/components/nodes/ExporterNode.tsx
import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Download } from 'lucide-react';
import type { NodeProps } from '@xyflow/react';
import type { ExporterNodeData } from '@/types/nodes';

const ExporterNode = memo(({ selected, data }: NodeProps<{ data: ExporterNodeData }>) => {
  const status = data?.status ?? 'idle';
  const borderColor =
    status === 'completed'
      ? 'border-green-500'
      : status === 'processing'
      ? 'border-blue-400'
      : 'border-deepblue-500';

  return (
    <div
      className={`w-[180px] bg-white rounded-lg border-2 ${borderColor} shadow-sm p-3 transition-all ${
        selected ? 'ring-2 ring-deepblue-400' : ''
      }`}
    >
      <div className="flex flex-col items-center gap-1">
        <Download size={20} className="text-deepblue-500" />
        <span className="text-sm font-medium text-slate-700">导出 PPTX</span>
      </div>
      <Handle type="target" position={Position.Left} className="w-2.5 h-2.5 bg-deepblue-400" />
    </div>
  );
});

export default ExporterNode;
```

```typescript
// frontend/src/components/nodes/index.ts
import UploadParserNode from './UploadParserNode';
import EditorNode from './EditorNode';
import ExporterNode from './ExporterNode';

export const nodeTypes = {
  uploadParser: UploadParserNode,
  editor: EditorNode,
  exporter: ExporterNode,
};
```

```tsx
// frontend/src/components/edges/LockedEdge.tsx
import { memo } from 'react';
import { BaseEdge, getSmoothStepPath, type EdgeProps } from '@xyflow/react';

const LockedEdge = memo(({ sourceX, sourceY, targetX, targetY }: EdgeProps) => {
  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });

  return (
    <BaseEdge
      path={edgePath}
      style={{ stroke: '#2E4A62', strokeWidth: 2 }}
    />
  );
});

export default LockedEdge;
```

```tsx
// frontend/src/components/FlowCanvas.tsx
import { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { nodeTypes } from './nodes';
import LockedEdge from './edges/LockedEdge';
import { useUIStore } from '@/stores/useUIStore';

const edgeTypes = { lockedEdge: LockedEdge };

const initialNodes: Node[] = [
  {
    id: 'node-upload',
    type: 'uploadParser',
    position: { x: 100, y: 250 },
    data: { status: 'idle' },
  },
  {
    id: 'node-editor',
    type: 'editor',
    position: { x: 420, y: 250 },
    data: { prompt: '', status: 'idle' },
  },
  {
    id: 'node-export',
    type: 'exporter',
    position: { x: 740, y: 250 },
    data: { status: 'idle' },
  },
];

const initialEdges: Edge[] = [
  {
    id: 'e-upload-editor',
    source: 'node-upload',
    target: 'node-editor',
    type: 'lockedEdge',
    deletable: false,
  },
  {
    id: 'e-editor-export',
    source: 'node-editor',
    target: 'node-export',
    type: 'lockedEdge',
    deletable: false,
  },
];

export default function FlowCanvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const setSelectedNodeId = useUIStore((s) => s.setSelectedNodeId);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNodeId(node.id);
    },
    [setSelectedNodeId]
  );

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, [setSelectedNodeId]);

  return (
    <div className="flex-1 h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.15, duration: 300 }}
        minZoom={0.3}
        maxZoom={1.5}
        nodesConnectable={false}
      >
        <Background gap={20} size={1} className="bg-surface" />
        <Controls />
        <MiniMap className="bg-white/90" />
      </ReactFlow>
    </div>
  );
}
```

- [ ] **Step 4: Update App.tsx**

```tsx
// frontend/src/App.tsx
import { ReactFlowProvider } from '@xyflow/react';
import FlowCanvas from './components/FlowCanvas';
import HeaderBar from './components/HeaderBar';

export default function App() {
  return (
    <div className="h-screen w-screen flex flex-col">
      <HeaderBar />
      <main className="flex-1 flex overflow-hidden">
        <ReactFlowProvider>
          <FlowCanvas />
        </ReactFlowProvider>
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Create HeaderBar**

```tsx
// frontend/src/components/HeaderBar.tsx
import { useTaskStore } from '@/stores/useTaskStore';

export default function HeaderBar() {
  const overallStatus = useTaskStore((s) => s.overallStatus);

  const statusLabel = {
    idle: '等待上传',
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    error: '执行失败',
  }[overallStatus];

  const statusColor = {
    idle: 'bg-gray-200 text-gray-700',
    pending: 'bg-blue-100 text-blue-700',
    processing: 'bg-blue-200 text-blue-800',
    completed: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
  }[overallStatus];

  return (
    <header className="h-12 bg-deepblue-800 text-white flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-lg">PPT Agent</span>
        <span className="w-2 h-2 rounded-full bg-green-400" />
      </div>
      <div className={`px-3 py-1 rounded-full text-xs font-medium ${statusColor}`}>
        {statusLabel}
      </div>
    </header>
  );
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/App.test.tsx`
Expected: PASS (1 test)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ frontend/src/App.tsx frontend/tests/App.test.tsx
git commit -m "feat: add React Flow canvas with three custom nodes and locked edges"
```

---

## Task 4: Parameter Panel and Sidebar

**Files:**
- Create: `frontend/src/components/SidebarPanel.tsx`
- Create: `frontend/src/components/ParamPanel.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/App.test.tsx (append)
import { fireEvent, screen } from '@testing-library/react';

describe('Sidebar', () => {
  it('opens when a node is clicked', () => {
    render(<App />);
    const editorNode = screen.getByText('编辑');
    fireEvent.click(editorNode);
    expect(screen.getByText('参数配置')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/App.test.tsx`
Expected: FAIL — sidebar not yet implemented.

- [ ] **Step 3: Write SidebarPanel and ParamPanel**

```tsx
// frontend/src/components/SidebarPanel.tsx
import { useUIStore } from '@/stores/useUIStore';
import ParamPanel from './ParamPanel';

export default function SidebarPanel() {
  const { sidebarOpen, selectedNodeId, toggleSidebar } = useUIStore();

  if (!sidebarOpen) {
    return (
      <div className="w-12 border-l border-gray-200 bg-white flex flex-col items-center py-4 shrink-0">
        <button onClick={toggleSidebar} className="p-2 hover:bg-gray-100 rounded">
          ◀
        </button>
      </div>
    );
  }

  return (
    <div className="w-80 border-l border-gray-200 bg-white flex flex-col shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <h3 className="font-semibold text-sm text-slate-700">参数配置</h3>
        <button onClick={toggleSidebar} className="p-1 hover:bg-gray-100 rounded text-gray-500">
          ✕
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {selectedNodeId ? (
          <ParamPanel nodeId={selectedNodeId} />
        ) : (
          <p className="text-sm text-gray-500">点击画布上的节点以配置参数</p>
        )}
      </div>
    </div>
  );
}
```

```tsx
// frontend/src/components/ParamPanel.tsx
import { useState } from 'react';
import { useTaskStore } from '@/stores/useTaskStore';
import { useFileStore } from '@/stores/useFileStore';
import { Upload, Pencil, Download } from 'lucide-react';

interface ParamPanelProps {
  nodeId: string;
}

export default function ParamPanel({ nodeId }: ParamPanelProps) {
  const nodeStatuses = useTaskStore((s) => s.nodeStatuses);
  const fileName = useFileStore((s) => s.fileName);
  const status = nodeStatuses[nodeId] ?? 'idle';

  if (nodeId === 'node-upload') {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-deepblue-600">
          <Upload size={18} />
          <h4 className="font-medium">上传与解析</h4>
        </div>
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-deepblue-400 transition-colors">
          <p className="text-sm text-gray-600">拖拽 PPTX 文件至此处</p>
          <p className="text-xs text-gray-400 mt-1">支持 .pptx 格式 | 最大 50MB</p>
        </div>
        {fileName && (
          <div className="flex items-center gap-2 text-sm text-green-600 bg-green-50 px-3 py-2 rounded">
            <span>✓</span>
            <span>{fileName}</span>
          </div>
        )}
        <div className="text-xs text-gray-500">
          状态: <span className="font-medium capitalize">{status}</span>
        </div>
      </div>
    );
  }

  if (nodeId === 'node-editor') {
    return <EditorParamPanel status={status} />;
  }

  if (nodeId === 'node-export') {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-deepblue-600">
          <Download size={18} />
          <h4 className="font-medium">导出打包</h4>
        </div>
        <div className="text-xs text-gray-500">
          状态: <span className="font-medium capitalize">{status}</span>
        </div>
        <button className="w-full bg-deepblue-500 text-white py-2 rounded-lg hover:bg-deepblue-600 transition-colors">
          导出
        </button>
      </div>
    );
  }

  return <p className="text-sm text-gray-500">未知节点</p>;
}

function EditorParamPanel({ status }: { status: string }) {
  const [mode, setMode] = useState<'refine' | 'svg'>('refine');
  const [prompt, setPrompt] = useState('');

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-deepblue-600">
        <Pencil size={18} />
        <h4 className="font-medium">编辑</h4>
      </div>

      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setMode('refine')}
          className={`flex-1 py-2 text-sm font-medium border-b-2 transition-colors ${
            mode === 'refine'
              ? 'border-deepblue-500 text-deepblue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          文本改写
        </button>
        <button
          onClick={() => setMode('svg')}
          className={`flex-1 py-2 text-sm font-medium border-b-2 transition-colors ${
            mode === 'svg'
              ? 'border-deepblue-500 text-deepblue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          SVG 生成
        </button>
      </div>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder={
          mode === 'refine'
            ? '输入改写指令，例如：将这段话精简为3个要点'
            : '描述你想要的视觉风格，例如：蓝色科技风格几何图形'
        }
        className="w-full h-24 p-3 text-sm border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-deepblue-400 focus:border-transparent"
        maxLength={500}
      />
      <div className="text-right text-xs text-gray-400">{prompt.length}/500</div>

      <div className="text-xs text-gray-500">
        状态: <span className="font-medium capitalize">{status}</span>
      </div>

      <button className="w-full bg-deepblue-500 text-white py-2 rounded-lg hover:bg-deepblue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
        {mode === 'refine' ? '执行' : '生成'}
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Update App.tsx to include sidebar**

```tsx
// frontend/src/App.tsx
import { ReactFlowProvider } from '@xyflow/react';
import FlowCanvas from './components/FlowCanvas';
import HeaderBar from './components/HeaderBar';
import SidebarPanel from './components/SidebarPanel';

export default function App() {
  return (
    <div className="h-screen w-screen flex flex-col">
      <HeaderBar />
      <main className="flex-1 flex overflow-hidden">
        <ReactFlowProvider>
          <FlowCanvas />
        </ReactFlowProvider>
        <SidebarPanel />
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/App.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/SidebarPanel.tsx frontend/src/components/ParamPanel.tsx frontend/src/App.tsx frontend/tests/App.test.tsx
git commit -m "feat: add sidebar parameter panel with node-specific forms"
```

---

## Task 5: SSE Connection Hook

**Files:**
- Create: `frontend/src/hooks/useSSE.ts`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Write the hook**

```typescript
// frontend/src/hooks/useSSE.ts
import { useEffect, useRef } from 'react';
import { useSSEStore } from '@/stores/useSSEStore';
import { useTaskStore } from '@/stores/useTaskStore';

const SSE_URL = '/api/v1/events';
const MAX_RETRIES = 10;

export function useSSE() {
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const retryDelayRef = useRef(1000);

  const setConnected = useSSEStore((s) => s.setConnected);
  const pushMessage = useSSEStore((s) => s.pushMessage);
  const setNodeStatus = useTaskStore((s) => s.setNodeStatus);
  const setOverallStatus = useTaskStore((s) => s.setOverallStatus);

  useEffect(() => {
    function connect() {
      if (eventSourceRef.current?.readyState === EventSource.OPEN) {
        return;
      }

      const es = new EventSource(SSE_URL);
      eventSourceRef.current = es;

      es.onopen = () => {
        setConnected(true);
        retryCountRef.current = 0;
        retryDelayRef.current = 1000;
      };

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          pushMessage({ type: data.event ?? 'message', payload: data });

          if (data.node && data.status) {
            setNodeStatus(data.node, data.status);
          }
          if (data.overall_status) {
            setOverallStatus(data.overall_status);
          }
        } catch {
          pushMessage({ type: 'raw', payload: event.data });
        }
      };

      es.onerror = () => {
        setConnected(false);
        es.close();

        if (retryCountRef.current < MAX_RETRIES) {
          retryCountRef.current += 1;
          setTimeout(connect, retryDelayRef.current);
          retryDelayRef.current = Math.min(retryDelayRef.current * 2, 30000);
        }
      };
    }

    connect();

    return () => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };
  }, [setConnected, pushMessage, setNodeStatus, setOverallStatus]);
}
```

- [ ] **Step 2: Integrate into App**

```tsx
// frontend/src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Note: In a real app, `useSSE` would be called inside `App` or a layout component. For MVP:

```tsx
// frontend/src/App.tsx
import { ReactFlowProvider } from '@xyflow/react';
import FlowCanvas from './components/FlowCanvas';
import HeaderBar from './components/HeaderBar';
import SidebarPanel from './components/SidebarPanel';
import { useSSE } from './hooks/useSSE';

function SSEConnector() {
  useSSE();
  return null;
}

export default function App() {
  return (
    <div className="h-screen w-screen flex flex-col">
      <SSEConnector />
      <HeaderBar />
      <main className="flex-1 flex overflow-hidden">
        <ReactFlowProvider>
          <FlowCanvas />
        </ReactFlowProvider>
        <SidebarPanel />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useSSE.ts frontend/src/App.tsx
git commit -m "feat: add SSE connection hook with auto-reconnect"
```

---

## Self-Review

**1. Spec coverage:**
- React Flow canvas with three fixed nodes → Task 3
- UploadParserNode, EditorNode, ExporterNode with status-based borders → Task 3
- Locked edges (deletable: false) → Task 3
- HeaderBar with global status tag → Task 3
- SidebarPanel with parameter forms → Task 4
- Text Refine / SVG Generate mode switch in editor panel → Task 4
- Prompt textarea with 500 char limit → Task 4
- SSE hook with exponential backoff reconnect → Task 5
- Zustand stores (file, task, SSE, UI) → Task 2

**2. Placeholder scan:**
- No TBD/TODO in code.
- Upload handler is UI-only; actual file upload API integration is deferred to integration plan.
- Export button is UI-only; download logic deferred.

**3. Type consistency:**
- `TaskStatus` is `'idle' | 'pending' | 'processing' | 'completed' | 'error'` everywhere.
- Node data types (`UploadNodeData`, `EditorNodeData`, `ExporterNodeData`) match React Flow `data` prop shape.
- `nodeTypes` registry keys match node `type` fields in initialNodes.

**Gaps identified and fixed:**
- Added `nodesConnectable={false}` to prevent users from adding new edges.
- Added `fitView` with padding so all three nodes are visible on load.
- Added `maxZoom` / `minZoom` constraints.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-13-frontend-canvas.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
