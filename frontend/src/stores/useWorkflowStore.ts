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
