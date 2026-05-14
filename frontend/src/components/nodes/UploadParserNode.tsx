import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Upload } from 'lucide-react';
import type { NodeProps } from '@xyflow/react';
import type { UploadNodeData } from '@/types/nodes';

const UploadParserNode = memo(({ selected, data }: NodeProps<{ data: UploadNodeData }>) => {
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
        <Upload size={20} className="text-deepblue-500" />
        <span className="text-sm font-medium text-slate-700">上传解析</span>
        {data?.fileName && (
          <span className="text-xs text-slate-500 truncate max-w-full">{data.fileName}</span>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="w-2.5 h-2.5 bg-deepblue-400" />
    </div>
  );
});

export default UploadParserNode;
