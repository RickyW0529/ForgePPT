import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Download } from 'lucide-react';
import type { WorkflowNodeData } from '@/types/workflow';

const statusBorder: Record<string, string> = {
  idle: 'border-gray-300',
  pending: 'border-yellow-400',
  processing: 'border-blue-500',
  completed: 'border-green-500',
  error: 'border-red-500',
};

function ExportNode({ data, selected }: NodeProps<Node<WorkflowNodeData>>) {
  return (
    <div
      className={`bg-white rounded-lg shadow-md border-2 ${statusBorder[data.status]} ${
        selected ? 'ring-2 ring-deepblue-400' : ''
      } min-w-[140px]`}
    >
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-deepblue-500" />
      <div className="flex items-center gap-2 px-3 py-2 bg-green-50 rounded-t-lg border-b border-green-100">
        <Download size={14} className="text-green-600" />
        <span className="text-xs font-medium text-green-700">导出</span>
      </div>
      <div className="px-3 py-2 text-xs text-gray-500">
        {data.status === 'completed' ? '可下载' : '等待执行'}
      </div>
    </div>
  );
}

export default memo(ExportNode);
