import { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
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
  const {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    addNode,
    setSelectedNodeId,
  } = useWorkflowStore();

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
