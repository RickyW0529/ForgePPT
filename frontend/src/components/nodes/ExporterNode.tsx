import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Download } from 'lucide-react';
import type { NodeProps } from '@xyflow/react';
import type { ExporterNodeData } from '@/types/nodes';

const ExporterNode = memo(({ selected, data }: NodeProps<{ data: ExporterNodeData }>) => {
  const status = data?.status ?? 'idle';
  const borderColor =
    status === 'completed'
      ? 'border-green-500'
      : status === 'processing'
      ? 'border-blue-400'
      : 'border-deepblue-500';

  return (
    <div
      className={`w-[180px] bg-white rounded-lg border-2 ${borderColor} shadow-sm p-3 transition-all ${
        selected ? 'ring-2 ring-deepblue-400' : ''
      }`}
    >
      <div className="flex flex-col items-center gap-1">
        <Download size={20} className="text-deepblue-500" />
        <span className="text-sm font-medium text-slate-700">导出 PPTX</span>
      </div>
      <Handle type="target" position={Position.Left} className="w-2.5 h-2.5 bg-deepblue-400" />
    </div>
  );
});

export default ExporterNode;
