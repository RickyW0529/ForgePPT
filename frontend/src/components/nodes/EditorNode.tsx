import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Pencil } from 'lucide-react';
import type { NodeProps } from '@xyflow/react';
import type { EditorNodeData } from '@/types/nodes';

const EditorNode = memo(({ selected, data }: NodeProps<{ data: EditorNodeData }>) => {
  const status = data?.status ?? 'idle';
  const borderColor =
    status === 'completed'
      ? 'border-green-500'
      : status === 'processing'
      ? 'border-blue-400'
      : 'border-deepblue-500';

  return (
    <div
      className={`w-[200px] bg-white rounded-lg border-2 ${borderColor} shadow-sm p-3 transition-all ${
        selected ? 'ring-2 ring-deepblue-400' : ''
      }`}
    >
      <div className="flex flex-col items-center gap-1">
        <Pencil size={20} className="text-deepblue-500" />
        <span className="text-sm font-medium text-slate-700">编辑</span>
        {data?.prompt && (
          <span className="text-xs text-slate-500 truncate max-w-full">{data.prompt}</span>
        )}
        {status === 'processing' && (
          <div className="w-full h-1 bg-gray-200 rounded-full overflow-hidden mt-1">
            <div className="h-full bg-blue-400 animate-pulse" style={{ width: '60%' }} />
          </div>
        )}
      </div>
      <Handle type="target" position={Position.Left} className="w-2.5 h-2.5 bg-deepblue-400" />
      <Handle type="source" position={Position.Right} className="w-2.5 h-2.5 bg-deepblue-400" />
    </div>
  );
});

export default EditorNode;
