import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Upload } from 'lucide-react';
import type { WorkflowNodeData } from '@/types/workflow';

const statusBorder: Record<string, string> = {
  idle: 'border-slate-200',
  pending: 'border-amber-200',
  processing: 'border-emerald-300',
  completed: 'border-deepblue-300',
  error: 'border-rose-300',
};

const statusDot: Record<string, string> = {
  idle: 'bg-slate-300',
  pending: 'bg-amber-400',
  processing: 'bg-emerald-400 animate-pulse',
  completed: 'bg-deepblue-400',
  error: 'bg-rose-400',
};

function UploadNode({ data, selected }: NodeProps<Node<WorkflowNodeData>>) {
  return (
    <div
      className={`min-w-[140px] overflow-hidden rounded-2xl border bg-white shadow-card ${statusBorder[data.status]} ${
        selected ? 'ring-2 ring-deepblue-300 ring-offset-1' : ''
      }`}
    >
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Upload size={14} className="text-slate-400" />
        <span className="text-xs font-medium text-slate-600">上传</span>
        <span className={`ml-auto h-1.5 w-1.5 rounded-full ${statusDot[data.status]}`} />
      </div>
      <div className="px-3 py-3 text-xs text-muted">
        {data.fileName || '等待文件...'}
      </div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !bg-deepblue-600" />
    </div>
  );
}

export default memo(UploadNode);
