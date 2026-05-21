import { useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import { useFileStore } from '@/stores/useFileStore';
import { useUIStore } from '@/stores/useUIStore';
import {
  Upload, Download, Bot, GitBranch, Merge,
  Loader2, Trash2, CheckCircle2, AlertCircle, Plus,
} from 'lucide-react';
import type { WorkflowNodeData } from '@/types/workflow';

interface ParamPanelProps {
  nodeId: string;
}

const ROLE_OPTIONS = [
  { key: 'text_refiner', label: '文本润色' },
  { key: 'color_optimizer', label: '颜色优化' },
  { key: 'layout_designer', label: '布局设计' },
  { key: 'svg_generator', label: 'SVG生成' },
  { key: 'theme_designer', label: '主题设计' },
];

const STATUS_LABELS: Record<string, string> = {
  idle: '等待',
  pending: '排队中',
  processing: '处理中',
  completed: '已完成',
  error: '出错',
};

const STATUS_BADGE_CLS: Record<string, string> = {
  idle: 'bg-slate-100 text-slate-500',
  pending: 'bg-amber-50 text-amber-600 border border-amber-200',
  processing: 'bg-emerald-50 text-emerald-600 border border-emerald-200',
  completed: 'bg-deepblue-50 text-deepblue-600 border border-deepblue-200',
  error: 'bg-rose-50 text-rose-600 border border-rose-200',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_BADGE_CLS[status] ?? 'bg-slate-100 text-slate-500'}`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-muted">
      {children}
    </label>
  );
}

function DeleteButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-md border border-border p-1.5 text-slate-400 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-500"
    >
      <Trash2 size={13} />
    </button>
  );
}

const inputCls =
  'w-full rounded-lg border border-border bg-surface/60 px-3 py-2 text-sm text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-deepblue-400 focus:bg-white focus:ring-2 focus:ring-deepblue-100';

export default function ParamPanel({ nodeId }: ParamPanelProps) {
  const nodes = useWorkflowStore((s) => s.nodes);
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);
  const removeNode = useWorkflowStore((s) => s.removeNode);
  const node = nodes.find((n) => n.id === nodeId);
  const addToast = useUIStore((s) => s.addToast);

  if (!node) return <p className="text-sm text-muted">节点未找到</p>;

  const data = node.data as WorkflowNodeData;

  const handleUpdate = (patch: Partial<WorkflowNodeData>) => {
    updateNodeData(nodeId, patch);
  };

  const handleDelete = () => {
    removeNode(nodeId);
    addToast({ type: 'info', message: '节点已删除' });
  };

  if (node.type === 'upload') {
    return <UploadParamPanel data={data} nodeId={nodeId} />;
  }

  if (node.type === 'agent') {
    return <AgentParamPanel data={data} onUpdate={handleUpdate} onDelete={handleDelete} />;
  }

  if (node.type === 'page_allocator') {
    return <PageAllocatorParamPanel data={data} onUpdate={handleUpdate} onDelete={handleDelete} />;
  }

  if (node.type === 'merge') {
    return <MergeParamPanel data={data} onUpdate={handleUpdate} onDelete={handleDelete} />;
  }

  if (node.type === 'export') {
    return <ExportParamPanel data={data} />;
  }

  return <p className="text-sm text-muted">未知节点类型</p>;
}

function UploadParamPanel({ data, nodeId }: { data: WorkflowNodeData; nodeId: string }) {
  const fileName = useFileStore((s) => s.fileName);
  const isUploading = useFileStore((s) => s.isUploading);
  const uploadError = useFileStore((s) => s.uploadError);
  const uploadFile = useFileStore((s) => s.uploadFile);
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);
  const addToast = useUIStore((s) => s.addToast);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await uploadFile(file);
      updateNodeData(nodeId, { fileName: file.name });
      addToast({ type: 'success', message: `${file.name} 上传成功` });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '上传失败';
      addToast({ type: 'error', message: msg });
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Upload size={15} className="text-slate-500" />
          <span className="text-sm font-semibold text-slate-800">上传与解析</span>
        </div>
        <StatusBadge status={data.status} />
      </div>

      <div className="border-t border-border" />

      <div className="space-y-3">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pptx"
          onChange={handleFileChange}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-deepblue-700 px-3 py-2.5 text-sm font-medium text-white transition-colors hover:bg-deepblue-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isUploading ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              上传中...
            </>
          ) : (
            <>
              <Upload size={14} />
              选择 PPTX 文件
            </>
          )}
        </button>

        {fileName && (
          <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2">
            <CheckCircle2 size={14} className="shrink-0 text-emerald-500" />
            <span className="truncate text-xs text-emerald-700">{fileName}</span>
          </div>
        )}
        {uploadError && (
          <div className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2">
            <AlertCircle size={14} className="shrink-0 text-rose-500" />
            <span className="truncate text-xs text-rose-700">{uploadError}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function AgentParamPanel({
  data,
  onUpdate,
  onDelete,
}: {
  data: WorkflowNodeData;
  onUpdate: (patch: Partial<WorkflowNodeData>) => void;
  onDelete: () => void;
}) {
  const [prompt, setPrompt] = useState(data.prompt || '');
  const [pageScopeStr, setPageScopeStr] = useState((data.pageScope || []).join(', '));
  const roleLabel = ROLE_OPTIONS.find((role) => role.key === data.role)?.label || '主题设计';

  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot size={15} className="text-deepblue-500" />
          <span className="text-sm font-semibold text-slate-800">智能体</span>
          <span className="rounded-full border border-deepblue-100 bg-deepblue-50 px-2 py-0.5 text-[11px] font-medium text-deepblue-600">
            {roleLabel}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={data.status} />
          <DeleteButton onClick={onDelete} />
        </div>
      </div>

      <div className="border-t border-border" />

      <div>
        <FieldLabel>Prompt</FieldLabel>
        <textarea
          value={prompt}
          onChange={(e) => {
            setPrompt(e.target.value);
            onUpdate({ prompt: e.target.value });
          }}
          placeholder="输入编辑指令..."
          className={`${inputCls} h-28 resize-none`}
          maxLength={500}
        />
        <div className="mt-1 text-right text-[11px] text-muted">{prompt.length} / 500</div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <FieldLabel>温度</FieldLabel>
          <span className="text-xs font-semibold text-deepblue-600">{data.temperature || 0.3}</span>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.1}
          value={data.temperature || 0.3}
          onChange={(e) => onUpdate({ temperature: parseFloat(e.target.value) })}
          className="w-full accent-deepblue-600"
        />
        <div className="mt-1 flex justify-between text-[10px] text-muted">
          <span>精确</span>
          <span>创意</span>
        </div>
      </div>

      <div>
        <FieldLabel>页面范围</FieldLabel>
        <input
          type="text"
          value={pageScopeStr}
          onChange={(e) => {
            setPageScopeStr(e.target.value);
            const pages = e.target.value
              .split(',')
              .map((s) => parseInt(s.trim(), 10))
              .filter((n) => !isNaN(n) && n > 0);
            onUpdate({ pageScope: pages });
          }}
          placeholder="例如: 1, 3, 5"
          className={inputCls}
        />
        <p className="mt-1 text-[11px] text-muted">留空表示处理全部页面</p>
      </div>
    </div>
  );
}

function PageAllocatorParamPanel({
  data,
  onUpdate,
  onDelete,
}: {
  data: WorkflowNodeData;
  onUpdate: (patch: Partial<WorkflowNodeData>) => void;
  onDelete: () => void;
}) {
  const [branches, setBranches] = useState<Record<string, number[]>>(data.branches || { 'branch-a': [] });

  const updateBranch = (name: string, pagesStr: string) => {
    const pages = pagesStr
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n) && n > 0);
    const next = { ...branches, [name]: pages };
    setBranches(next);
    onUpdate({ branches: next });
  };

  const addBranch = () => {
    const existingKeys = new Set(Object.keys(branches));
    let idx = 0;
    let name = `branch-${String.fromCharCode(97 + idx)}`;
    while (existingKeys.has(name) && idx < 25) {
      idx++;
      name = `branch-${String.fromCharCode(97 + idx)}`;
    }
    const next = { ...branches, [name]: [] };
    setBranches(next);
    onUpdate({ branches: next });
  };

  const removeBranch = (name: string) => {
    const next = { ...branches };
    delete next[name];
    setBranches(next);
    onUpdate({ branches: next });
  };

  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitBranch size={15} className="text-violet-500" />
          <span className="text-sm font-semibold text-slate-800">页面分配</span>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={data.status} />
          <DeleteButton onClick={onDelete} />
        </div>
      </div>

      <div className="border-t border-border" />

      <div className="space-y-2">
        <FieldLabel>分支配置</FieldLabel>
        {Object.entries(branches).map(([name, pages]) => (
          <div key={name} className="rounded-lg border border-border bg-surface/60 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-600">{name}</span>
              <button
                onClick={() => removeBranch(name)}
                className="text-[11px] text-rose-400 transition-colors hover:text-rose-600"
              >
                删除
              </button>
            </div>
            <input
              type="text"
              value={pages.join(', ')}
              onChange={(e) => updateBranch(name, e.target.value)}
              placeholder="页面编号，如 1, 3, 5"
              className={inputCls}
            />
          </div>
        ))}
      </div>

      <button
        onClick={addBranch}
        className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted transition-colors hover:border-deepblue-300 hover:bg-deepblue-50 hover:text-deepblue-600"
      >
        <Plus size={13} />
        添加分支
      </button>
    </div>
  );
}

function MergeParamPanel({
  data,
  onUpdate,
  onDelete,
}: {
  data: WorkflowNodeData;
  onUpdate: (patch: Partial<WorkflowNodeData>) => void;
  onDelete: () => void;
}) {
  const [prompt, setPrompt] = useState(data.prompt || '');

  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Merge size={15} className="text-amber-500" />
          <span className="text-sm font-semibold text-slate-800">合并配置</span>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={data.status} />
          <DeleteButton onClick={onDelete} />
        </div>
      </div>

      <div className="border-t border-border" />

      <div>
        <FieldLabel>合并 Prompt</FieldLabel>
        <textarea
          value={prompt}
          onChange={(e) => {
            setPrompt(e.target.value);
            onUpdate({ prompt: e.target.value });
          }}
          placeholder="例如：优先保留最新内容"
          className={`${inputCls} h-28 resize-none`}
        />
      </div>
    </div>
  );
}

function ExportParamPanel({ data }: { data: WorkflowNodeData }) {
  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Download size={15} className="text-emerald-500" />
          <span className="text-sm font-semibold text-slate-800">导出</span>
        </div>
        <StatusBadge status={data.status} />
      </div>

      <div className="border-t border-border" />

      {data.status === 'completed' ? (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-3">
          <CheckCircle2 size={14} className="shrink-0 text-emerald-500" />
          <span className="text-xs text-emerald-700">工作流已完成，文件可下载</span>
        </div>
      ) : (
        <p className="text-xs text-muted">工作流执行完成后，导出文件将在此处可用。</p>
      )}
    </div>
  );
}
