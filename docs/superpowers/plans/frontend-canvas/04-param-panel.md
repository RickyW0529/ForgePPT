# 04 - Parameter Panel and Sidebar

**Files:**
- Create: `frontend/src/components/SidebarPanel.tsx`
- Create: `frontend/src/components/ParamPanel.tsx`
- Modify: `frontend/src/App.tsx`

---

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/App.test.tsx (append)
import { fireEvent, screen } from '@testing-library/react';

describe('Sidebar', () => {
  it('opens when a node is clicked', () => {
    render(<App />);
    const editorNode = screen.getByText('编辑');
    fireEvent.click(editorNode);
    expect(screen.getByText('参数配置')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/App.test.tsx`
Expected: FAIL — sidebar not yet implemented.

- [ ] **Step 3: Write SidebarPanel and ParamPanel**

```tsx
// frontend/src/components/SidebarPanel.tsx
import { useUIStore } from '@/stores/useUIStore';
import ParamPanel from './ParamPanel';

export default function SidebarPanel() {
  const { sidebarOpen, selectedNodeId, toggleSidebar } = useUIStore();

  if (!sidebarOpen) {
    return (
      <div className="w-12 border-l border-gray-200 bg-white flex flex-col items-center py-4 shrink-0">
        <button onClick={toggleSidebar} className="p-2 hover:bg-gray-100 rounded">
          ◀
        </button>
      </div>
    );
  }

  return (
    <div className="w-80 border-l border-gray-200 bg-white flex flex-col shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <h3 className="font-semibold text-sm text-slate-700">参数配置</h3>
        <button onClick={toggleSidebar} className="p-1 hover:bg-gray-100 rounded text-gray-500">
          ✕
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {selectedNodeId ? (
          <ParamPanel nodeId={selectedNodeId} />
        ) : (
          <p className="text-sm text-gray-500">点击画布上的节点以配置参数</p>
        )}
      </div>
    </div>
  );
}
```

```tsx
// frontend/src/components/ParamPanel.tsx
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
```

- [ ] **Step 4: Update App.tsx to include sidebar**

```tsx
// frontend/src/App.tsx
import { ReactFlowProvider } from '@xyflow/react';
import FlowCanvas from './components/FlowCanvas';
import HeaderBar from './components/HeaderBar';
import SidebarPanel from './components/SidebarPanel';

export default function App() {
  return (
    <div className="h-screen w-screen flex flex-col">
      <HeaderBar />
      <main className="flex-1 flex overflow-hidden">
        <ReactFlowProvider>
          <FlowCanvas />
        </ReactFlowProvider>
        <SidebarPanel />
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/App.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/SidebarPanel.tsx frontend/src/components/ParamPanel.tsx frontend/src/App.tsx frontend/tests/App.test.tsx
git commit -m "feat: add sidebar parameter panel with node-specific forms"
```
