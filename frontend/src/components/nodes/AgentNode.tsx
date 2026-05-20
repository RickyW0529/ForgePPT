import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Bot } from 'lucide-react';
import type { WorkflowNodeData } from '@/types/workflow';

const statusBorder: Record<string, string> = {
  idle: 'border-gray-300',
  pending: 'border-yellow-400',
  processing: 'border-blue-500',
  completed: 'border-green-500',
  error: 'border-red-500',
};

const roleLabels: Record<string, string> = {
  text_refiner: '文本润色',
  color_optimizer: '颜色优化',
  layout_designer: '布局设计',
  svg_generator: 'SVG生成',
  theme_designer: '主题设计',
};

function AgentNode({ data, selected }: NodeProps<Node<WorkflowNodeData>>) {
  return (
    <div
      className={`bg-white rounded-lg shadow-md border-2 ${statusBorder[data.status]} ${
        selected ? 'ring-2 ring-deepblue-400' : ''
      } min-w-[160px]`}
    >
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-deepblue-500" />
      <div className="flex items-center gap-2 px-3 py-2 bg-deepblue-50 rounded-t-lg border-b border-deepblue-100">
        <Bot size={14} className="text-deepblue-600" />
        <span className="text-xs font-medium text-deepblue-700">
          {roleLabels[data.role || ''] || 'Agent'}
        </span>
      </div>
      <div className="px-3 py-2 text-xs text-gray-500 truncate max-w-[180px]">
        {data.prompt || '点击配置参数'}
      </div>
      {data.pageScope && data.pageScope.length > 0 && (
        <div className="px-3 pb-2 text-[10px] text-gray-400">
          页面: {data.pageScope.join(', ')}
        </div>
      )}
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-deepblue-500" />
    </div>
  );
}

export default memo(AgentNode);
