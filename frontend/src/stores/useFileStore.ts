import { create } from 'zustand';

interface FileState {
  fileName: string | null;
  fileSize: number | null;
  parsedState: unknown | null;
  setFile: (name: string, size: number) => void;
  setParsedState: (state: unknown) => void;
  reset: () => void;
}

export const useFileStore = create<FileState>((set) => ({
  fileName: null,
  fileSize: null,
  parsedState: null,
  setFile: (name, size) => set({ fileName: name, fileSize: size }),
  setParsedState: (state) => set({ parsedState: state }),
  reset: () => set({ fileName: null, fileSize: null, parsedState: null }),
}));
