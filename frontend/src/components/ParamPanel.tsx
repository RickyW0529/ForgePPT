import { useRef, useState } from 'react';
import { useTaskStore } from '@/stores/useTaskStore';
import { useFileStore } from '@/stores/useFileStore';
import { useUIStore } from '@/stores/useUIStore';
import { Upload, Pencil, Download, Loader2 } from 'lucide-react';

interface ParamPanelProps {
  nodeId: string;
}

export default function ParamPanel({ nodeId }: ParamPanelProps) {
  const nodeStatuses = useTaskStore((s) => s.nodeStatuses);
  const fileName = useFileStore((s) => s.fileName);
  const isUploading = useFileStore((s) => s.isUploading);
  const uploadError = useFileStore((s) => s.uploadError);
  const uploadFile = useFileStore((s) => s.uploadFile);
  const setNodeStatus = useTaskStore((s) => s.setNodeStatus);
  const addToast = useUIStore((s) => s.addToast);
  const status = nodeStatuses[nodeId] ?? 'idle';
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFile = async (file: File) => {
    try {
      setNodeStatus('node-upload', 'processing');
      await uploadFile(file);
      setNodeStatus('node-upload', 'completed');
      addToast({ type: 'success', message: `Uploaded: ${file.name}` });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setNodeStatus('node-upload', 'error');
      addToast({ type: 'error', message: msg });
    }
  };

  const onClickDropzone = () => {
    if (!isUploading) {
      fileInputRef.current?.click();
    }
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = '';
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  if (nodeId === 'node-upload') {
    const dropBorder = isDragOver
      ? 'border-deepblue-500 bg-deepblue-50'
      : uploadError
      ? 'border-red-400'
      : 'border-gray-300 hover:border-deepblue-400';

    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-deepblue-600">
          <Upload size={18} />
          <h4 className="font-medium">上传与解析</h4>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
          className="hidden"
          onChange={onFileChange}
        />

        <div
          onClick={onClickDropzone}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${dropBorder} ${
            isUploading ? 'opacity-60 cursor-not-allowed' : ''
          }`}
        >
          {isUploading ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2 size={20} className="text-deepblue-500 animate-spin" />
              <p className="text-sm text-gray-600">Uploading and parsing...</p>
            </div>
          ) : (
            <>
              <p className="text-sm text-gray-600">Click or drag PPTX file here</p>
              <p className="text-xs text-gray-400 mt-1">.pptx only | Max 50MB</p>
            </>
          )}
        </div>

        {uploadError && (
          <div className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded">{uploadError}</div>
        )}

        {fileName && !uploadError && (
          <div className="flex items-center gap-2 text-sm text-green-600 bg-green-50 px-3 py-2 rounded">
            <span>✓</span>
            <span>{fileName}</span>
          </div>
        )}

        <div className="text-xs text-gray-500">
          Status: <span className="font-medium capitalize">{status}</span>
        </div>
      </div>
    );
  }

  if (nodeId === 'node-editor') {
    return <EditorParamPanel status={status} />;
  }

  if (nodeId === 'node-export') {
    const exportPath = useTaskStore((s) => s.exportPath);
    const downloadUrl = exportPath ? `/api/v1/download?path=${encodeURIComponent(exportPath)}` : null;

    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-deepblue-600">
          <Download size={18} />
          <h4 className="font-medium">导出打包</h4>
        </div>
        <div className="text-xs text-gray-500">
          状态: <span className="font-medium capitalize">{status}</span>
        </div>
        {downloadUrl ? (
          <a
            href={downloadUrl}
            download
            className="block w-full bg-green-600 text-white text-center py-2 rounded-lg hover:bg-green-700 transition-colors"
          >
            下载修改后的 PPT
          </a>
        ) : (
          <button
            disabled
            className="w-full bg-gray-300 text-white py-2 rounded-lg cursor-not-allowed"
          >
            等待执行完成
          </button>
        )}
      </div>
    );
  }

  return <p className="text-sm text-gray-500">未知节点</p>;
}

function EditorParamPanel({ status }: { status: string }) {
  const [mode, setMode] = useState<'refine' | 'svg' | 'theme'>('theme');
  const [prompt, setPrompt] = useState('');
  const parsedState = useFileStore((s) => s.parsedState);
  const createTask = useTaskStore((s) => s.createTask);
  const isExecuting = useTaskStore((s) => s.isExecuting);
  const addToast = useUIStore((s) => s.addToast);

  const handleExecute = async () => {
    if (!parsedState) {
      addToast({ type: 'error', message: '请先上传 PPT 文件' });
      return;
    }
    if (!prompt.trim()) {
      addToast({ type: 'error', message: '请输入编辑指令' });
      return;
    }

    const type = mode === 'theme' ? 'theme' : mode === 'refine' ? 'refine' : 'placeholder';
    await createTask(parsedState, [{ type, prompt: prompt.trim() }]);
  };

  const placeholder =
    mode === 'refine'
      ? '输入改写指令，例如：将这段话精简为3个要点'
      : mode === 'svg'
      ? '描述你想要的视觉风格，例如：蓝色科技风格几何图形'
      : '描述整体风格，例如：改成深蓝色科技风格，字体加粗';

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-deepblue-600">
        <Pencil size={18} />
        <h4 className="font-medium">编辑</h4>
      </div>

      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setMode('theme')}
          className={`flex-1 py-2 text-sm font-medium border-b-2 transition-colors ${
            mode === 'theme'
              ? 'border-deepblue-500 text-deepblue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          全局风格
        </button>
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
        placeholder={placeholder}
        className="w-full h-24 p-3 text-sm border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-deepblue-400 focus:border-transparent"
        maxLength={500}
      />
      <div className="text-right text-xs text-gray-400">{prompt.length}/500</div>

      <div className="text-xs text-gray-500">
        状态: <span className="font-medium capitalize">{status}</span>
      </div>

      <button
        onClick={handleExecute}
        disabled={isExecuting || !parsedState}
        className="w-full bg-deepblue-500 text-white py-2 rounded-lg hover:bg-deepblue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isExecuting ? (
          <span className="flex items-center justify-center gap-2">
            <Loader2 size={16} className="animate-spin" />
            执行中...
          </span>
        ) : mode === 'refine' ? (
          '执行'
        ) : mode === 'svg' ? (
          '生成'
        ) : (
          '应用风格'
        )}
      </button>
    </div>
  );
}
