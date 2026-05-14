export type TaskStatus = 'idle' | 'pending' | 'processing' | 'completed' | 'error';

export type NodeType = 'uploadParser' | 'editor' | 'exporter';

export interface UploadNodeData {
  fileName?: string;
  status: TaskStatus;
}

export interface EditorNodeData {
  prompt: string;
  preview?: string;
  status: TaskStatus;
}

export interface ExporterNodeData {
  downloadUrl?: string;
  status: TaskStatus;
}
