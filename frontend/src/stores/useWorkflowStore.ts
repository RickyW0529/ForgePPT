import { create } from 'zustand';
import { applyNodeChanges, applyEdgeChanges, addEdge, type NodeChange, type EdgeChange, type Connection } from '@xyflow/react';
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
  onNodesChange: (changes: NodeChange<Node<WorkflowNodeData>>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
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

  onNodesChange: (changes) =>
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes),
    })),

  onEdgesChange: (changes) =>
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
    })),

  onConnect: (connection) =>
    set((state) => ({
      edges: addEdge(connection, state.edges),
    })),

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
    set((state) => {
      const node = state.nodes.find((n) => n.id === nodeId);
      const nextNodes = state.nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n
      );
      let nextEdges = state.edges;
      if (node?.type === 'page_allocator' && data.branches) {
        const branchNames = Object.keys(data.branches).sort();
        const outEdges = state.edges.filter((e) => e.source === nodeId);
        nextEdges = state.edges.map((e) => {
          if (e.source !== nodeId) return e;
          const idx = outEdges.findIndex((oe) => oe.id === e.id);
          const branchName = branchNames[idx];
          const pages = branchName ? (data.branches as Record<string, number[]>)[branchName] : [];
          return { ...e, data: { ...e.data, pageScope: pages } };
        });
      }
      return { nodes: nextNodes, edges: nextEdges };
    }),

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
