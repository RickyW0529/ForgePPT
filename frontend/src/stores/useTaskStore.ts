import { create } from 'zustand';
import type { TaskStatus } from '@/types/nodes';

interface TaskState {
  taskId: string | null;
  overallStatus: TaskStatus;
  nodeStatuses: Record<string, TaskStatus>;
  errorMessage: string | null;
  exportPath: string | null;
  isExecuting: boolean;
  setTaskId: (id: string) => void;
  setOverallStatus: (status: TaskStatus) => void;
  setNodeStatus: (nodeId: string, status: TaskStatus) => void;
  setError: (msg: string | null) => void;
  setExportPath: (path: string | null) => void;
  createTask: (pptState: unknown, editRequests: unknown[]) => Promise<void>;
  reset: () => void;
}

export const useTaskStore = create<TaskState>((set) => ({
  taskId: null,
  overallStatus: 'idle',
  nodeStatuses: {},
  errorMessage: null,
  exportPath: null,
  isExecuting: false,

  setTaskId: (id) => set({ taskId: id }),
  setOverallStatus: (status) => set({ overallStatus: status }),
  setNodeStatus: (nodeId, status) =>
    set((state) => ({
      nodeStatuses: { ...state.nodeStatuses, [nodeId]: status },
    })),
  setError: (msg) => set({ errorMessage: msg }),
  setExportPath: (path) => set({ exportPath: path }),

  createTask: async (pptState: unknown, editRequests: unknown[]) => {
    set({ isExecuting: true, errorMessage: null, exportPath: null, overallStatus: 'processing' });
    set((s) => ({
      nodeStatuses: { ...s.nodeStatuses, 'node-editor': 'processing', 'node-export': 'pending' },
    }));

    try {
      const resp = await fetch('/api/v1/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ppt_state: pptState, edit_requests: editRequests }),
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || `Task failed: ${resp.status}`);
      }

      const json = await resp.json();
      const data = json.data || json;

      set({
        isExecuting: false,
        overallStatus: 'completed',
        exportPath: data.export_path || null,
        taskId: data.task_id || null,
      });
      set((s) => ({
        nodeStatuses: {
          ...s.nodeStatuses,
          'node-editor': 'completed',
          'node-export': data.export_path ? 'completed' : 'error',
        },
      }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Execution failed';
      set({ isExecuting: false, overallStatus: 'error', errorMessage: msg });
      set((s) => ({
        nodeStatuses: {
          ...s.nodeStatuses,
          'node-editor': 'error',
          'node-export': 'error',
        },
      }));
    }
  },

  reset: () =>
    set({
      taskId: null,
      overallStatus: 'idle',
      nodeStatuses: {},
      errorMessage: null,
      exportPath: null,
      isExecuting: false,
    }),
}));
