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
