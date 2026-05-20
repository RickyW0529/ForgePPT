import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Merge } from 'lucide-react';
import type { WorkflowNodeData } from '@/types/workflow';

const statusBorder: Record<string, string> = {
  idle: 'border-gray-300',
  pending: 'border-yellow-400',
  processing: 'border-blue-500',
  completed: 'border-green-500',
  error: 'border-red-500',
};

function MergeNode({ data, selected }: NodeProps<Node<WorkflowNodeData>>) {
  return (
    <div
      className={`bg-white rounded-lg shadow-md border-2 ${statusBorder[data.status]} ${
        selected ? 'ring-2 ring-deepblue-400' : ''
      } min-w-[140px]`}
    >
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-deepblue-500" />
      <div className="flex items-center gap-2 px-3 py-2 bg-orange-50 rounded-t-lg border-b border-orange-100">
        <Merge size={14} className="text-orange-600" />
        <span className="text-xs font-medium text-orange-700">合并</span>
      </div>
      <div className="px-3 py-2 text-xs text-gray-500 truncate max-w-[140px]">
        {data.prompt ? data.prompt : 'AI Composer'}
      </div>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-deepblue-500" />
    </div>
  );
}

export default memo(MergeNode);
