import { create } from 'zustand';

interface FileState {
  fileName: string | null;
  fileSize: number | null;
  filePath: string | null;
  parsedState: unknown | null;
  isUploading: boolean;
  uploadError: string | null;
  setFile: (name: string, size: number) => void;
  setParsedState: (state: unknown) => void;
  setUploading: (v: boolean) => void;
  setUploadError: (msg: string | null) => void;
  uploadFile: (file: File) => Promise<void>;
  reset: () => void;
}

const MAX_SIZE = 50 * 1024 * 1024; // 50MB

export const useFileStore = create<FileState>((set) => ({
  fileName: null,
  fileSize: null,
  filePath: null,
  parsedState: null,
  isUploading: false,
  uploadError: null,

  setFile: (name, size) => set({ fileName: name, fileSize: size }),
  setParsedState: (state) => set({ parsedState: state }),
  setUploading: (v) => set({ isUploading: v }),
  setUploadError: (msg) => set({ uploadError: msg }),

  uploadFile: async (file: File) => {
    if (!file.name.endsWith('.pptx')) {
      throw new Error('Only .pptx files are supported');
    }
    if (file.size > MAX_SIZE) {
      throw new Error('File size exceeds 50MB limit');
    }

    set({ isUploading: true, uploadError: null });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const resp = await fetch('/api/v1/upload', {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || `Upload failed: ${resp.status}`);
      }

      const data = await resp.json();
      set({
        fileName: file.name,
        fileSize: file.size,
        filePath: data.file_path ?? null,
        parsedState: data.data ?? data,
        isUploading: false,
        uploadError: null,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      set({ isUploading: false, uploadError: msg });
      throw err;
    }
  },

  reset: () =>
    set({
      fileName: null,
      fileSize: null,
      filePath: null,
      parsedState: null,
      isUploading: false,
      uploadError: null,
    }),
}));
