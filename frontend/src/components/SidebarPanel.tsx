import { useWorkflowStore } from '@/stores/useWorkflowStore';
import { useUIStore } from '@/stores/useUIStore';
import ParamPanel from './ParamPanel';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function SidebarPanel() {
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);

  if (!sidebarOpen) {
    return (
      <aside className="flex w-14 shrink-0 flex-col items-center border-l border-border bg-white/90 py-4 shadow-[-1px_0_0_rgba(255,255,255,0.7)]">
        <button
          onClick={toggleSidebar}
          className="rounded-full border border-border bg-panel p-2 text-slate-500 transition-colors hover:bg-surface"
          aria-label="展开参数配置"
        >
          <ChevronLeft size={14} />
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex w-80 shrink-0 flex-col border-l border-border bg-panel shadow-[-1px_0_0_rgba(255,255,255,0.7)]">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">参数配置</h3>
          <p className="text-xs text-muted">调整选中节点的属性</p>
        </div>
        <button
          onClick={toggleSidebar}
          className="rounded-full border border-border p-2 text-slate-500 transition-colors hover:bg-surface"
          aria-label="收起参数配置"
        >
          <ChevronRight size={14} />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {selectedNodeId ? (
          <ParamPanel nodeId={selectedNodeId} />
        ) : (
          <div className="rounded-2xl border border-dashed border-border bg-surface/60 p-4 text-sm text-muted">
            点击画布上的节点以配置参数
          </div>
        )}
      </div>
    </aside>
  );
}
