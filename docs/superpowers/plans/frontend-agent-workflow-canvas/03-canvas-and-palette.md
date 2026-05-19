### Task 3: Canvas & Node Palette

**Files:**
- Create: `frontend/src/components/NodePalette.tsx`
- Modify: `frontend/src/components/FlowCanvas.tsx`
- Modify: `frontend/src/App.tsx`

---

- [ ] **Step 1: Write NodePalette component**

Create `frontend/src/components/NodePalette.tsx`:

```tsx
import { useCallback } from 'react';
import { useReactFlow } from '@xyflow/react';
import { Bot, GitBranch, Merge, Upload, Download, Type, Palette, LayoutGrid, Image } from 'lucide-react';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import type { NodeType } from '@/types/workflow';

interface PaletteItem {
  type: NodeType | 'agent:text_refiner' | 'agent:color_optimizer' | 'agent:layout_designer' | 'agent:svg_generator' | 'agent:theme_designer';
  label: string;
  icon: React.ReactNode;
  color: string;
}

const items: PaletteItem[] = [
  { type: 'upload', label: '上传', icon: <Upload size={16} />, color: 'bg-gray-100 text-gray-700' },
  { type: 'page_allocator', label: '页面分配', icon: <GitBranch size={16} />, color: 'bg-purple-100 text-purple-700' },
  { type: 'merge', label: '合并', icon: <Merge size={16} />, color: 'bg-orange-100 text-orange-700' },
  { type: 'export', label: '导出', icon: <Download size={16} />, color: 'bg-green-100 text-green-700' },
  { type: 'agent:text_refiner', label: '文本润色', icon: <Type size={16} />, color: 'bg-blue-100 text-blue-700' },
  { type: 'agent:color_optimizer', label: '颜色优化', icon: <Palette size={16} />, color: 'bg-blue-100 text-blue-700' },
  { type: 'agent:layout_designer', label: '布局设计', icon: <LayoutGrid size={16} />, color: 'bg-blue-100 text-blue-700' },
  { type: 'agent:svg_generator', label: 'SVG生成', icon: <Image size={16} />, color: 'bg-blue-100 text-blue-700' },
  { type: 'agent:theme_designer', label: '主题设计', icon: <Bot size={16} />, color: 'bg-blue-100 text-blue-700' },
];

export default function NodePalette() {
  const { screenToFlowPosition } = useReactFlow();
  const addNode = useWorkflowStore((s) => s.addNode);

  const onDragStart = useCallback((event: React.DragEvent, item: PaletteItem) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(item));
    event.dataTransfer.effectAllowed = 'move';
  }, []);

  return (
    <div className="w-48 bg-white border-r border-gray-200 flex flex-col shrink-0 overflow-y-auto">
      <div className="px-3 py-3 border-b border-gray-200">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">节点面板</h3>
      </div>
      <div className="p-2 space-y-1">
        {items.map((item) => (
          <div
            key={item.type}
            draggable
            onDragStart={(e) => onDragStart(e, item)}
            className={`flex items-center gap-2 px-3 py-2 rounded cursor-grab hover:shadow-sm transition-shadow text-xs font-medium ${item.color}`}
          >
            {item.icon}
            {item.label}
          </div>
        ))}
      </div>
      <div className="mt-auto p-3 text-[10px] text-gray-400 border-t border-gray-200">
        拖拽节点到画布
      </div>
    </div>
  );
}
```

---

- [ ] **Step 2: Rewrite FlowCanvas**

Modify `frontend/src/components/FlowCanvas.tsx`:

```tsx
import { useCallback, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  addEdge,
  Connection,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { nodeTypes } from './nodes';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import type { WorkflowNodeData } from '@/types/workflow';

const defaultNodeData: Record<string, Partial<WorkflowNodeData>> = {
  upload: { status: 'idle' },
  page_allocator: { status: 'idle', branches: { 'branch-a': [] } },
  agent: { status: 'idle', role: 'theme_designer', prompt: '', temperature: 0.3, pageScope: [] },
  merge: { status: 'idle', mergeStrategy: 'last_write_wins' },
  export: { status: 'idle' },
};

export default function FlowCanvas() {
  const { screenToFlowPosition } = useReactFlow();
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, addNode, setSelectedNodeId } = useWorkflowStore();

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const raw = event.dataTransfer.getData('application/reactflow');
      if (!raw) return;

      const item = JSON.parse(raw);
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      let type = item.type;
      let data = { ...defaultNodeData[type] };

      if (type.startsWith('agent:')) {
        const role = type.split(':')[1];
        type = 'agent';
        data = { ...defaultNodeData.agent, role };
      }

      const id = `${type}-${Date.now()}`;
      addNode({
        id,
        type,
        position,
        data: data as WorkflowNodeData,
      });
    },
    [screenToFlowPosition, addNode]
  );

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
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        onDrop={onDrop}
        onDragOver={onDragOver}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15, duration: 300 }}
        minZoom={0.3}
        maxZoom={1.5}
        nodesConnectable={true}
        deleteKeyCode={['Backspace', 'Delete']}
      >
        <Background gap={20} size={1} className="bg-surface" />
        <Controls />
        <MiniMap className="bg-white/90" />
      </ReactFlow>
    </div>
  );
}
```

---

- [ ] **Step 3: Update App.tsx to include palette**

Modify `frontend/src/App.tsx`:

```tsx
import { ReactFlowProvider } from '@xyflow/react';
import FlowCanvas from './components/FlowCanvas';
import HeaderBar from './components/HeaderBar';
import SidebarPanel from './components/SidebarPanel';
import ToastContainer from './components/ToastContainer';
import NodePalette from './components/NodePalette';

export default function App() {
  return (
    <div className="h-screen w-screen flex flex-col">
      <HeaderBar />
      <main className="flex-1 flex overflow-hidden">
        <ReactFlowProvider>
          <NodePalette />
          <FlowCanvas />
        </ReactFlowProvider>
        <SidebarPanel />
      </main>
      <ToastContainer />
    </div>
  );
}
```

---

- [ ] **Step 4: Verify build**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend
npm run build
```

Expected: Build succeeds with no errors.

---

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/NodePalette.tsx frontend/src/components/FlowCanvas.tsx frontend/src/App.tsx
git commit -m "feat: add draggable node palette and editable canvas

Co-Authored-By: Claude <noreply@anthropic.com>"
```
