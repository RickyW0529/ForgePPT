import { useState } from 'react';
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
  const parsedState = useFileStore((s) => s.parsedState);
  const filePath = useFileStore((s) => s.filePath);
  const addToast = useUIStore((s) => s.addToast);
  const [executionError, setExecutionError] = useState<string | null>(null);

  const handleExecute = async () => {
    setExecutionError(null);
    if (!parsedState || !filePath) {
      addToast({ type: 'error', message: '请先上传 PPT 文件' });
      return;
    }

    const uploadNodes = nodes.filter((n) => n.type === 'upload');
    if (uploadNodes.length < 1) {
      addToast({ type: 'error', message: '画布至少需要一个上传节点' });
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
        data: e.data || {},
      })),
    };

    try {
      const resp = await fetch('/api/v1/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_definition: workflowDef,
          file_path: filePath,
        }),
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || `Workflow submission failed: ${resp.status}`);
      }

      const json = await resp.json();
      const wfId = json.workflow_id || json.data?.workflow_id;
      if (!wfId) throw new Error('服务器未返回 workflow_id');
      setWorkflowId(wfId);
      addToast({ type: 'success', message: '工作流已提交' });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '提交失败';
      setExecutionError(msg);
      addToast({ type: 'error', message: msg });
      setExecuting(false);
    }
  };

  const overallStatus = isExecuting
    ? 'processing'
    : executionError
    ? 'error'
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
    idle: 'bg-slate-100 text-slate-600 border-slate-200',
    processing: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    completed: 'bg-deepblue-50 text-deepblue-700 border-deepblue-200',
    error: 'bg-rose-50 text-rose-700 border-rose-200',
  };

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-white/90 px-5 shadow-[0_1px_0_rgba(255,255,255,0.7)] backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-deepblue-700 text-sm font-semibold text-white shadow-soft">
          P
        </div>
        <div>
          <div className="text-sm font-semibold text-slate-900">PPT Agent</div>
          <div className="text-xs text-muted">Workflow canvas for PPT editing</div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div aria-live="polite" className={`rounded-full border px-3 py-1 text-xs font-medium ${statusColor[overallStatus]}`}>
          {statusLabel[overallStatus]}
        </div>
        <button
          onClick={handleExecute}
          disabled={isExecuting}
          className="flex items-center gap-1.5 rounded-full bg-deepblue-700 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-deepblue-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isExecuting ? (
            <>
              <Loader2 size={14} className="animate-spin" aria-hidden="true" />
              执行中
            </>
          ) : (
            <>
              <Play size={14} aria-hidden="true" />
              执行工作流
            </>
          )}
        </button>
      </div>
    </header>
  );
}
