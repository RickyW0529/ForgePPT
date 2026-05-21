import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Bot } from 'lucide-react';
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
      className={`min-w-[160px] overflow-hidden rounded-2xl border bg-white shadow-card ${statusBorder[data.status]} ${
        selected ? 'ring-2 ring-deepblue-300 ring-offset-1' : ''
      }`}
    >
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !bg-deepblue-600" />
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Bot size={14} className="text-deepblue-500" />
        <span className="text-xs font-medium text-deepblue-700">
          {roleLabels[data.role || ''] || 'Agent'}
        </span>
        <span className={`ml-auto h-1.5 w-1.5 rounded-full ${statusDot[data.status]}`} />
      </div>
      <div className="px-3 py-3 text-xs text-muted truncate max-w-[180px]">
        {data.prompt || '点击配置参数'}
      </div>
      {data.pageScope && data.pageScope.length > 0 && (
        <div className="px-3 pb-3 text-[10px] text-muted">
          页面: {data.pageScope.join(', ')}
        </div>
      )}
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !bg-deepblue-600" />
    </div>
  );
}

export default memo(AgentNode);
