# 03 - React Flow Canvas and Custom Nodes

**Files:**
- Create: `frontend/src/components/FlowCanvas.tsx`
- Create: `frontend/src/components/nodes/UploadParserNode.tsx`
- Create: `frontend/src/components/nodes/EditorNode.tsx`
- Create: `frontend/src/components/nodes/ExporterNode.tsx`
- Create: `frontend/src/components/nodes/index.ts`
- Create: `frontend/src/components/edges/LockedEdge.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/tests/App.test.tsx`

---

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
