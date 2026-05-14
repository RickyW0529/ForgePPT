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
