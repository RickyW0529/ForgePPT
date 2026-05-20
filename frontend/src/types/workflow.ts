export type TaskStatus = 'idle' | 'pending' | 'processing' | 'completed' | 'error';

export type NodeType = 'upload' | 'page_allocator' | 'agent' | 'merge' | 'export';

export interface Position {
  x: number;
  y: number;
}

export interface WorkflowNodeData {
  [key: string]: unknown;
  // upload
  fileName?: string;
  // agent
  role?: string;
  prompt?: string;
  temperature?: number;
  model?: string;
  pageScope?: number[];
  // page_allocator
  branches?: Record<string, number[]>;
  // merge
  mergeStrategy?: 'last_write_wins' | 'error_on_conflict';
  // common
  status: TaskStatus;
}

export interface WorkflowDef {
  workflow_id: string;
  nodes: Array<{
    id: string;
    type: NodeType;
    position: Position;
    data: WorkflowNodeData;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
  }>;
}
