### Task 2: React Flow Node Components

**Files:**
- Create: `frontend/src/components/nodes/UploadNode.tsx`
- Create: `frontend/src/components/nodes/AgentNode.tsx`
- Create: `frontend/src/components/nodes/PageAllocatorNode.tsx`
- Create: `frontend/src/components/nodes/MergeNode.tsx`
- Create: `frontend/src/components/nodes/ExportNode.tsx`
- Modify: `frontend/src/components/nodes/index.ts`

---

- [ ] **Step 1: Create node components**

Create `frontend/src/components/nodes/UploadNode.tsx`:

```tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Upload } from 'lucide-react';
import type { WorkflowNodeData } from '@/types/workflow';

const statusBorder: Record<string, string> = {
  idle: 'border-gray-300',
  pending: 'border-yellow-400',
  processing: 'border-blue-500',
  completed: 'border-green-500',
  error: 'border-red-500',
};

function UploadNode({ data, selected }: NodeProps<{ data: WorkflowNodeData }>) {
  return (
    <div
      className={`bg-white rounded-lg shadow-md border-2 ${statusBorder[data.status]} ${
        selected ? 'ring-2 ring-deepblue-400' : ''
      } min-w-[140px]`}
    >
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-t-lg border-b border-gray-100">
        <Upload size={14} className="text-gray-600" />
        <span className="text-xs font-medium text-gray-700">上传</span>
      </div>
      <div className="px-3 py-2 text-xs text-gray-500">
        {data.fileName || '等待文件...'}
      </div>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-deepblue-500" />
    </div>
  );
}

export default memo(UploadNode);
```

Create `frontend/src/components/nodes/AgentNode.tsx`:

```tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
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

function AgentNode({ data, selected }: NodeProps<{ data: WorkflowNodeData }>) {
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
```

Create `frontend/src/components/nodes/PageAllocatorNode.tsx`:

```tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { GitBranch } from 'lucide-react';
import type { WorkflowNodeData } from '@/types/workflow';

const statusBorder: Record<string, string> = {
  idle: 'border-gray-300',
  pending: 'border-yellow-400',
  processing: 'border-blue-500',
  completed: 'border-green-500',
  error: 'border-red-500',
};

function PageAllocatorNode({ data, selected }: NodeProps<{ data: WorkflowNodeData }>) {
  const branchCount = data.branches ? Object.keys(data.branches).length : 0;
  return (
    <div
      className={`bg-white rounded-lg shadow-md border-2 ${statusBorder[data.status]} ${
        selected ? 'ring-2 ring-deepblue-400' : ''
      } min-w-[140px]`}
    >
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-deepblue-500" />
      <div className="flex items-center gap-2 px-3 py-2 bg-purple-50 rounded-t-lg border-b border-purple-100">
        <GitBranch size={14} className="text-purple-600" />
        <span className="text-xs font-medium text-purple-700">页面分配</span>
      </div>
      <div className="px-3 py-2 text-xs text-gray-500">
        {branchCount} 个分支
      </div>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-deepblue-500" />
    </div>
  );
}

export default memo(PageAllocatorNode);
```

Create `frontend/src/components/nodes/MergeNode.tsx`:

```tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Merge } from 'lucide-react';
import type { WorkflowNodeData } from '@/types/workflow';

const statusBorder: Record<string, string> = {
  idle: 'border-gray-300',
  pending: 'border-yellow-400',
  processing: 'border-blue-500',
  completed: 'border-green-500',
  error: 'border-red-500',
};

function MergeNode({ data, selected }: NodeProps<{ data: WorkflowNodeData }>) {
  return (
    <div
      className={`bg-white rounded-lg shadow-md border-2 ${statusBorder[data.status]} ${
        selected ? 'ring-2 ring-deepblue-400' : ''
      } min-w-[140px]`}
    >
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-deepblue-500" />
      <div className="flex items-center gap-2 px-3 py-2 bg-orange-50 rounded-t-lg border-b border-orange-100">
        <Merge size={14} className="text-orange-600" />
        <span className="text-xs font-medium text-orange-700">合并</span>
      </div>
      <div className="px-3 py-2 text-xs text-gray-500">
        {data.mergeStrategy === 'last_write_wins' ? '后写优先' : '冲突报错'}
      </div>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-deepblue-500" />
    </div>
  );
}

export default memo(MergeNode);
```

Create `frontend/src/components/nodes/ExportNode.tsx`:

```tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Download } from 'lucide-react';
import type { WorkflowNodeData } from '@/types/workflow';

const statusBorder: Record<string, string> = {
  idle: 'border-gray-300',
  pending: 'border-yellow-400',
  processing: 'border-blue-500',
  completed: 'border-green-500',
  error: 'border-red-500',
};

function ExportNode({ data, selected }: NodeProps<{ data: WorkflowNodeData }>) {
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
```

---

- [ ] **Step 2: Update node types index**

Modify `frontend/src/components/nodes/index.ts`:

```typescript
import UploadNode from './UploadNode';
import AgentNode from './AgentNode';
import PageAllocatorNode from './PageAllocatorNode';
import MergeNode from './MergeNode';
import ExportNode from './ExportNode';

export const nodeTypes = {
  upload: UploadNode,
  agent: AgentNode,
  page_allocator: PageAllocatorNode,
  merge: MergeNode,
  export: ExportNode,
};
```

---

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend
npx tsc --noEmit
```

Expected: No errors.

---

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/nodes/
git commit -m "feat: add React Flow custom node components for agent workflow

Co-Authored-By: Claude <noreply@anthropic.com>"
```
