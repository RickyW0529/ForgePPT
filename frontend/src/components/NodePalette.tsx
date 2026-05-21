import { useCallback } from 'react';
import { Bot, GitBranch, Merge, Upload, Download, Type, Palette, LayoutGrid, Image } from 'lucide-react';
import type { NodeType } from '@/types/workflow';

interface PaletteItem {
  type: NodeType | 'agent:text_refiner' | 'agent:color_optimizer' | 'agent:layout_designer' | 'agent:svg_generator' | 'agent:theme_designer';
  label: string;
  icon: React.ReactNode;
  iconClass: string;
}

const workflowItems: PaletteItem[] = [
  { type: 'upload', label: '上传', icon: <Upload size={14} />, iconClass: 'text-slate-400' },
  { type: 'page_allocator', label: '页面分配', icon: <GitBranch size={14} />, iconClass: 'text-violet-500' },
  { type: 'merge', label: '合并', icon: <Merge size={14} />, iconClass: 'text-amber-500' },
  { type: 'export', label: '导出', icon: <Download size={14} />, iconClass: 'text-emerald-500' },
];

const agentItems: PaletteItem[] = [
  { type: 'agent:text_refiner', label: '文本润色', icon: <Type size={14} />, iconClass: 'text-deepblue-500' },
  { type: 'agent:color_optimizer', label: '颜色优化', icon: <Palette size={14} />, iconClass: 'text-deepblue-500' },
  { type: 'agent:layout_designer', label: '布局设计', icon: <LayoutGrid size={14} />, iconClass: 'text-deepblue-500' },
  { type: 'agent:svg_generator', label: 'SVG 生成', icon: <Image size={14} />, iconClass: 'text-deepblue-500' },
  { type: 'agent:theme_designer', label: '主题设计', icon: <Bot size={14} />, iconClass: 'text-deepblue-500' },
];

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-1 pb-1.5 pt-3">
      <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
        {children}
      </span>
    </div>
  );
}

export default function NodePalette() {
  const onDragStart = useCallback((event: React.DragEvent, item: PaletteItem) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(item));
    event.dataTransfer.effectAllowed = 'move';
  }, []);

  const renderItem = (item: PaletteItem) => (
    <div
      key={item.type}
      draggable
      onDragStart={(e) => onDragStart(e, item)}
      className="flex cursor-grab items-center gap-2.5 rounded-lg border border-border bg-panel px-3 py-2 text-sm text-slate-700 transition-all hover:bg-surface hover:shadow-sm active:scale-[0.98]"
    >
      <span className={item.iconClass}>{item.icon}</span>
      {item.label}
    </div>
  );

  return (
    <aside className="flex w-52 shrink-0 flex-col overflow-y-auto border-r border-border bg-white/90 shadow-[1px_0_0_rgba(255,255,255,0.7)]">
      <div className="border-b border-border px-4 py-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">节点面板</h3>
        <p className="mt-1 text-xs text-slate-400">拖拽节点到画布</p>
      </div>

      <div className="flex-1 p-3">
        <SectionLabel>工作流</SectionLabel>
        <div className="space-y-1">
          {workflowItems.map(renderItem)}
        </div>

        <SectionLabel>AI Agent</SectionLabel>
        <div className="space-y-1">
          {agentItems.map(renderItem)}
        </div>
      </div>

      <div className="border-t border-border px-4 py-3 text-[11px] text-slate-400">
        将节点拖入工作区
      </div>
    </aside>
  );
}
