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
