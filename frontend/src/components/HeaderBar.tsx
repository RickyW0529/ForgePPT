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
  const addToast = useUIStore((s) => s.addToast);
  const [executionError, setExecutionError] = useState<string | null>(null);

  const handleExecute = async () => {
    setExecutionError(null);
    if (!parsedState) {
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
        <div aria-live="polite" className={`px-3 py-1 rounded-full text-xs font-medium ${statusColor[overallStatus]}`}>
          {statusLabel[overallStatus]}
        </div>
        <button
          onClick={handleExecute}
          disabled={isExecuting}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-gray-500 disabled:cursor-not-allowed rounded text-xs font-medium transition-colors"
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
