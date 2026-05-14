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
