import { useState } from 'react';
import { useTaskStore } from '@/stores/useTaskStore';
import { useFileStore } from '@/stores/useFileStore';
import { Upload, Pencil, Download } from 'lucide-react';

interface ParamPanelProps {
  nodeId: string;
}

export default function ParamPanel({ nodeId }: ParamPanelProps) {
  const nodeStatuses = useTaskStore((s) => s.nodeStatuses);
  const fileName = useFileStore((s) => s.fileName);
  const status = nodeStatuses[nodeId] ?? 'idle';

  if (nodeId === 'node-upload') {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-deepblue-600">
          <Upload size={18} />
          <h4 className="font-medium">上传与解析</h4>
        </div>
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-deepblue-400 transition-colors">
          <p className="text-sm text-gray-600">拖拽 PPTX 文件至此处</p>
          <p className="text-xs text-gray-400 mt-1">支持 .pptx 格式 | 最大 50MB</p>
        </div>
        {fileName && (
          <div className="flex items-center gap-2 text-sm text-green-600 bg-green-50 px-3 py-2 rounded">
            <span>✓</span>
            <span>{fileName}</span>
          </div>
        )}
        <div className="text-xs text-gray-500">
          状态: <span className="font-medium capitalize">{status}</span>
        </div>
      </div>
    );
  }

  if (nodeId === 'node-editor') {
    return <EditorParamPanel status={status} />;
  }

  if (nodeId === 'node-export') {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-deepblue-600">
          <Download size={18} />
          <h4 className="font-medium">导出打包</h4>
        </div>
        <div className="text-xs text-gray-500">
          状态: <span className="font-medium capitalize">{status}</span>
        </div>
        <button className="w-full bg-deepblue-500 text-white py-2 rounded-lg hover:bg-deepblue-600 transition-colors">
          导出
        </button>
      </div>
    );
  }

  return <p className="text-sm text-gray-500">未知节点</p>;
}

function EditorParamPanel({ status }: { status: string }) {
  const [mode, setMode] = useState<'refine' | 'svg'>('refine');
  const [prompt, setPrompt] = useState('');

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-deepblue-600">
        <Pencil size={18} />
        <h4 className="font-medium">编辑</h4>
      </div>

      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setMode('refine')}
          className={`flex-1 py-2 text-sm font-medium border-b-2 transition-colors ${
            mode === 'refine'
              ? 'border-deepblue-500 text-deepblue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          文本改写
        </button>
        <button
          onClick={() => setMode('svg')}
          className={`flex-1 py-2 text-sm font-medium border-b-2 transition-colors ${
            mode === 'svg'
              ? 'border-deepblue-500 text-deepblue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          SVG 生成
        </button>
      </div>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder={
          mode === 'refine'
            ? '输入改写指令，例如：将这段话精简为3个要点'
            : '描述你想要的视觉风格，例如：蓝色科技风格几何图形'
        }
        className="w-full h-24 p-3 text-sm border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-deepblue-400 focus:border-transparent"
        maxLength={500}
      />
      <div className="text-right text-xs text-gray-400">{prompt.length}/500</div>

      <div className="text-xs text-gray-500">
        状态: <span className="font-medium capitalize">{status}</span>
      </div>

      <button className="w-full bg-deepblue-500 text-white py-2 rounded-lg hover:bg-deepblue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
        {mode === 'refine' ? '执行' : '生成'}
      </button>
    </div>
  );
}
