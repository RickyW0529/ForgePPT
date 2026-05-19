### Task 4: ParamPanel Rewrite

**Files:**
- Modify: `frontend/src/components/ParamPanel.tsx`

---

- [ ] **Step 1: Rewrite ParamPanel for all node types**

Replace the contents of `frontend/src/components/ParamPanel.tsx`:

```tsx
import { useRef, useState } from 'react';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import { useFileStore } from '@/stores/useFileStore';
import { useUIStore } from '@/stores/useUIStore';
import { Upload, Download, Bot, GitBranch, Merge, Loader2, Trash2 } from 'lucide-react';
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

export default function ParamPanel({ nodeId }: ParamPanelProps) {
  const nodes = useWorkflowStore((s) => s.nodes);
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);
  const removeNode = useWorkflowStore((s) => s.removeNode);
  const node = nodes.find((n) => n.id === nodeId);
  const addToast = useUIStore((s) => s.addToast);

  if (!node) return <p className="text-sm text-gray-500">节点未找到</p>;

  const data = node.data as WorkflowNodeData;

  const handleUpdate = (patch: Partial<WorkflowNodeData>) => {
    updateNodeData(nodeId, patch);
  };

  const handleDelete = () => {
    removeNode(nodeId);
    addToast({ type: 'info', message: '节点已删除' });
  };

  if (node.type === 'upload') {
    return <UploadParamPanel nodeId={nodeId} data={data} />;
  }

  if (node.type === 'agent') {
    return <AgentParamPanel nodeId={nodeId} data={data} onUpdate={handleUpdate} onDelete={handleDelete} />;
  }

  if (node.type === 'page_allocator') {
    return <PageAllocatorParamPanel nodeId={nodeId} data={data} onUpdate={handleUpdate} onDelete={handleDelete} />;
  }

  if (node.type === 'merge') {
    return <MergeParamPanel nodeId={nodeId} data={data} onUpdate={handleUpdate} onDelete={handleDelete} />;
  }

  if (node.type === 'export') {
    return <ExportParamPanel nodeId={nodeId} data={data} />;
  }

  return <p className="text-sm text-gray-500">未知节点类型</p>;
}

function UploadParamPanel({ nodeId, data }: { nodeId: string; data: WorkflowNodeData }) {
  const fileName = useFileStore((s) => s.fileName);
  const isUploading = useFileStore((s) => s.isUploading);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-deepblue-600">
        <Upload size={18} />
        <h4 className="font-medium">上传与解析</h4>
      </div>
      <div className="text-xs text-gray-500">
        状态: <span className="font-medium capitalize">{data.status}</span>
      </div>
      {fileName && (
        <div className="text-sm text-green-600 bg-green-50 px-3 py-2 rounded">
          ✓ {fileName}
        </div>
      )}
      {isUploading && (
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <Loader2 size={16} className="animate-spin" />
          上传中...
        </div>
      )}
    </div>
  );
}

function AgentParamPanel({
  nodeId,
  data,
  onUpdate,
  onDelete,
}: {
  nodeId: string;
  data: WorkflowNodeData;
  onUpdate: (patch: Partial<WorkflowNodeData>) => void;
  onDelete: () => void;
}) {
  const [prompt, setPrompt] = useState(data.prompt || '');
  const [pageScopeStr, setPageScopeStr] = useState((data.pageScope || []).join(', '));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-deepblue-600">
          <Bot size={18} />
          <h4 className="font-medium">Agent 配置</h4>
        </div>
        <button onClick={onDelete} className="p-1 text-red-400 hover:text-red-600 hover:bg-red-50 rounded">
          <Trash2 size={14} />
        </button>
      </div>

      <div>
        <label className="block text-xs text-gray-500 mb-1">角色</label>
        <select
          value={data.role || 'theme_designer'}
          onChange={(e) => onUpdate({ role: e.target.value })}
          className="w-full text-sm border border-gray-300 rounded px-2 py-1.5"
        >
          {ROLE_OPTIONS.map((r) => (
            <option key={r.key} value={r.key}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs text-gray-500 mb-1">指令 Prompt</label>
        <textarea
          value={prompt}
          onChange={(e) => {
            setPrompt(e.target.value);
            onUpdate({ prompt: e.target.value });
          }}
          placeholder="输入编辑指令..."
          className="w-full h-20 p-2 text-sm border border-gray-300 rounded resize-none"
          maxLength={500}
        />
        <div className="text-right text-xs text-gray-400">{prompt.length}/500</div>
      </div>

      <div>
        <label className="block text-xs text-gray-500 mb-1">温度 (0.0 - 1.0)</label>
        <input
          type="range"
          min={0}
          max={1}
          step={0.1}
          value={data.temperature || 0.3}
          onChange={(e) => onUpdate({ temperature: parseFloat(e.target.value) })}
          className="w-full"
        />
        <div className="text-xs text-gray-500 text-center">{data.temperature || 0.3}</div>
      </div>

      <div>
        <label className="block text-xs text-gray-500 mb-1">处理页面 (逗号分隔，空=全部)</label>
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
          className="w-full text-sm border border-gray-300 rounded px-2 py-1.5"
        />
      </div>

      <div className="text-xs text-gray-500">
        状态: <span className="font-medium capitalize">{data.status}</span>
      </div>
    </div>
  );
}

function PageAllocatorParamPanel({
  nodeId,
  data,
  onUpdate,
  onDelete,
}: {
  nodeId: string;
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
    const name = `branch-${Object.keys(branches).length + 1}`;
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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-purple-600">
          <GitBranch size={18} />
          <h4 className="font-medium">页面分配</h4>
        </div>
        <button onClick={onDelete} className="p-1 text-red-400 hover:text-red-600 hover:bg-red-50 rounded">
          <Trash2 size={14} />
        </button>
      </div>

      {Object.entries(branches).map(([name, pages]) => (
        <div key={name} className="space-y-1">
          <div className="flex items-center justify-between">
            <label className="text-xs text-gray-500">{name}</label>
            <button onClick={() => removeBranch(name)} className="text-[10px] text-red-400 hover:text-red-600">
              删除
            </button>
          </div>
          <input
            type="text"
            value={pages.join(', ')}
            onChange={(e) => updateBranch(name, e.target.value)}
            placeholder="例如: 1, 3"
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5"
          />
        </div>
      ))}

      <button
        onClick={addBranch}
        className="w-full py-1.5 text-xs text-deepblue-600 border border-deepblue-200 rounded hover:bg-deepblue-50"
      >
        + 添加分支
      </button>

      <div className="text-xs text-gray-500">
        状态: <span className="font-medium capitalize">{data.status}</span>
      </div>
    </div>
  );
}

function MergeParamPanel({
  nodeId,
  data,
  onUpdate,
  onDelete,
}: {
  nodeId: string;
  data: WorkflowNodeData;
  onUpdate: (patch: Partial<WorkflowNodeData>) => void;
  onDelete: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-orange-600">
          <Merge size={18} />
          <h4 className="font-medium">合并配置</h4>
        </div>
        <button onClick={onDelete} className="p-1 text-red-400 hover:text-red-600 hover:bg-red-50 rounded">
          <Trash2 size={14} />
        </button>
      </div>

      <div>
        <label className="block text-xs text-gray-500 mb-1">合并策略</label>
        <select
          value={data.mergeStrategy || 'last_write_wins'}
          onChange={(e) => onUpdate({ mergeStrategy: e.target.value as 'last_write_wins' | 'error_on_conflict' })}
          className="w-full text-sm border border-gray-300 rounded px-2 py-1.5"
        >
          <option value="last_write_wins">后写优先</option>
          <option value="error_on_conflict">冲突报错</option>
        </select>
      </div>

      <div className="text-xs text-gray-500">
        状态: <span className="font-medium capitalize">{data.status}</span>
      </div>
    </div>
  );
}

function ExportParamPanel({ nodeId, data }: { nodeId: string; data: WorkflowNodeData }) {
  const exportPath = useWorkflowStore((s) => s.exportPath);
  const downloadUrl = exportPath ? `/api/v1/download?path=${encodeURIComponent(exportPath)}` : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-green-600">
        <Download size={18} />
        <h4 className="font-medium">导出打包</h4>
      </div>
      <div className="text-xs text-gray-500">
        状态: <span className="font-medium capitalize">{data.status}</span>
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
        <button disabled className="w-full bg-gray-300 text-white py-2 rounded-lg cursor-not-allowed">
          等待执行完成
        </button>
      )}
    </div>
  );
}
```

---

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend
npx tsc --noEmit
```

Expected: No errors.

---

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ParamPanel.tsx
git commit -m "feat: rewrite ParamPanel for all workflow node types

Co-Authored-By: Claude <noreply@anthropic.com>"
```
