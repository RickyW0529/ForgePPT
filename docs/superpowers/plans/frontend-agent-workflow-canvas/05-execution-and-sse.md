### Task 5: Execution Button, Workflow SSE, and Integration

**Files:**
- Modify: `frontend/src/components/HeaderBar.tsx`
- Create: `frontend/src/hooks/useWorkflowSSE.ts`
- Modify: `frontend/src/App.tsx`

---

- [ ] **Step 1: Write workflow SSE hook**

Create `frontend/src/hooks/useWorkflowSSE.ts`:

```typescript
import { useEffect, useRef } from 'react';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import { useUIStore } from '@/stores/useUIStore';

export function useWorkflowSSE() {
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const setNodeStatus = useWorkflowStore((s) => s.setNodeStatus);
  const setExportPath = useWorkflowStore((s) => s.setExportPath);
  const setExecuting = useWorkflowStore((s) => s.setExecuting);
  const addToast = useUIStore((s) => s.addToast);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!workflowId) return;

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const connect = async () => {
      try {
        const resp = await fetch(`/api/v1/workflows/${workflowId}/events`, {
          signal: ctrl.signal,
          headers: { Accept: 'text/event-stream' },
        });

        if (!resp.ok || !resp.body) {
          throw new Error(`SSE connection failed: ${resp.status}`);
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const chunk of lines) {
            const dataLine = chunk.split('\n').find((l) => l.startsWith('data:'));
            if (!dataLine) continue;

            const jsonStr = dataLine.slice(5).trim();
            try {
              const event = JSON.parse(jsonStr);
              if (event.node_id) {
                setNodeStatus(event.node_id, event.status);
                if (event.status === 'error') {
                  addToast({ type: 'error', message: `节点 ${event.node_id} 执行失败` });
                }
              }
              if (event.export_path) {
                setExportPath(event.export_path);
                setExecuting(false);
                addToast({ type: 'success', message: '工作流执行完成' });
              }
            } catch {
              // Ignore malformed SSE data
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          console.error('SSE error:', err);
          addToast({ type: 'error', message: 'SSE 连接断开' });
          setExecuting(false);
        }
      }
    };

    connect();

    return () => {
      ctrl.abort();
    };
  }, [workflowId, setNodeStatus, setExportPath, setExecuting, addToast]);
}
```

---

- [ ] **Step 2: Rewrite HeaderBar with Execute button**

Modify `frontend/src/components/HeaderBar.tsx`:

```tsx
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import { useFileStore } from '@/stores/useFileStore';
import { useUIStore } from '@/stores/useUIStore';
import { Play, Loader2 } from 'lucide-react';

export default function HeaderBar() {
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const isExecuting = useWorkflowStore((s) => s.isExecuting);
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const setWorkflowId = useWorkflowStore((s) => s.setWorkflowId);
  const setExecuting = useWorkflowStore((s) => s.setExecuting);
  const resetExecution = useWorkflowStore((s) => s.resetExecution);
  const filePath = useFileStore((s) => s.parsedState);
  const addToast = useUIStore((s) => s.addToast);

  const handleExecute = async () => {
    if (!filePath) {
      addToast({ type: 'error', message: '请先上传 PPT 文件' });
      return;
    }

    const uploadNodes = nodes.filter((n) => n.type === 'upload');
    if (uploadNodes.length !== 1) {
      addToast({ type: 'error', message: '画布必须有且仅有一个上传节点' });
      return;
    }

    const exportNodes = nodes.filter((n) => n.type === 'export');
    if (exportNodes.length < 1) {
      addToast({ type: 'error', message: '画布至少需要有一个导出节点' });
      return;
    }

    resetExecution();
    setExecuting(true);

    const workflowDef = {
      workflow_id: crypto.randomUUID(),
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: n.data,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
      })),
    };

    try {
      const resp = await fetch('/api/v1/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_definition: workflowDef,
          file_path: '/tmp/forgeppt_uploads/uploaded.pptx',
        }),
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || `Workflow submission failed: ${resp.status}`);
      }

      const json = await resp.json();
      setWorkflowId(json.workflow_id || json.data?.workflow_id);
      addToast({ type: 'success', message: '工作流已提交' });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '提交失败';
      addToast({ type: 'error', message: msg });
      setExecuting(false);
    }
  };

  const overallStatus = isExecuting
    ? 'processing'
    : workflowId
    ? 'completed'
    : 'idle';

  const statusLabel: Record<string, string> = {
    idle: '等待执行',
    processing: '执行中',
    completed: '已完成',
    error: '执行失败',
  };

  const statusColor: Record<string, string> = {
    idle: 'bg-gray-200 text-gray-700',
    processing: 'bg-blue-200 text-blue-800',
    completed: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
  };

  return (
    <header className="h-12 bg-deepblue-800 text-white flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-lg">PPT Agent</span>
        <span className="w-2 h-2 rounded-full bg-green-400" />
      </div>
      <div className="flex items-center gap-3">
        <div className={`px-3 py-1 rounded-full text-xs font-medium ${statusColor[overallStatus]}`}>
          {statusLabel[overallStatus]}
        </div>
        <button
          onClick={handleExecute}
          disabled={isExecuting}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-gray-500 disabled:cursor-not-allowed rounded text-xs font-medium transition-colors"
        >
          {isExecuting ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              执行中
            </>
          ) : (
            <>
              <Play size={14} />
              执行工作流
            </>
          )}
        </button>
      </div>
    </header>
  );
}
```

---

- [ ] **Step 3: Update App.tsx to include SSE hook**

Modify `frontend/src/App.tsx`:

```tsx
import { ReactFlowProvider } from '@xyflow/react';
import FlowCanvas from './components/FlowCanvas';
import HeaderBar from './components/HeaderBar';
import SidebarPanel from './components/SidebarPanel';
import ToastContainer from './components/ToastContainer';
import NodePalette from './components/NodePalette';
import { useWorkflowSSE } from './hooks/useWorkflowSSE';

function SSEConnector() {
  useWorkflowSSE();
  return null;
}

export default function App() {
  return (
    <div className="h-screen w-screen flex flex-col">
      <SSEConnector />
      <HeaderBar />
      <main className="flex-1 flex overflow-hidden">
        <ReactFlowProvider>
          <NodePalette />
          <FlowCanvas />
        </ReactFlowProvider>
        <SidebarPanel />
      </main>
      <ToastContainer />
    </div>
  );
}
```

---

- [ ] **Step 4: Verify build**

```bash
cd /Users/wangruiqi/RustroverProjects/ForgePPT/frontend
npm run build
```

Expected: Build succeeds with no errors.

---

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/HeaderBar.tsx frontend/src/hooks/useWorkflowSSE.ts frontend/src/App.tsx
git commit -m "feat: add workflow execution button and SSE streaming

Co-Authored-By: Claude <noreply@anthropic.com>"
```
