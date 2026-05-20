import { useCallback } from 'react';
import { Bot, GitBranch, Merge, Upload, Download, Type, Palette, LayoutGrid, Image } from 'lucide-react';
import type { NodeType } from '@/types/workflow';

interface PaletteItem {
  type: NodeType | 'agent:text_refiner' | 'agent:color_optimizer' | 'agent:layout_designer' | 'agent:svg_generator' | 'agent:theme_designer';
  label: string;
  icon: React.ReactNode;
  color: string;
}

const items: PaletteItem[] = [
  { type: 'upload', label: '上传', icon: <Upload size={16} />, color: 'bg-gray-100 text-gray-700' },
  { type: 'page_allocator', label: '页面分配', icon: <GitBranch size={16} />, color: 'bg-purple-100 text-purple-700' },
  { type: 'merge', label: '合并', icon: <Merge size={16} />, color: 'bg-orange-100 text-orange-700' },
  { type: 'export', label: '导出', icon: <Download size={16} />, color: 'bg-green-100 text-green-700' },
  { type: 'agent:text_refiner', label: '文本润色', icon: <Type size={16} />, color: 'bg-blue-100 text-blue-700' },
  { type: 'agent:color_optimizer', label: '颜色优化', icon: <Palette size={16} />, color: 'bg-blue-100 text-blue-700' },
  { type: 'agent:layout_designer', label: '布局设计', icon: <LayoutGrid size={16} />, color: 'bg-blue-100 text-blue-700' },
  { type: 'agent:svg_generator', label: 'SVG生成', icon: <Image size={16} />, color: 'bg-blue-100 text-blue-700' },
  { type: 'agent:theme_designer', label: '主题设计', icon: <Bot size={16} />, color: 'bg-blue-100 text-blue-700' },
];

export default function NodePalette() {
  const onDragStart = useCallback((event: React.DragEvent, item: PaletteItem) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(item));
    event.dataTransfer.effectAllowed = 'move';
  }, []);

  return (
    <div className="w-48 bg-white border-r border-gray-200 flex flex-col shrink-0 overflow-y-auto">
      <div className="px-3 py-3 border-b border-gray-200">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">节点面板</h3>
      </div>
      <div className="p-2 space-y-1">
        {items.map((item) => (
          <div
            key={item.type}
            draggable
            onDragStart={(e) => onDragStart(e, item)}
            className={`flex items-center gap-2 px-3 py-2 rounded cursor-grab hover:shadow-sm transition-shadow text-xs font-medium ${item.color}`}
          >
            {item.icon}
            {item.label}
          </div>
        ))}
      </div>
      <div className="mt-auto p-3 text-[10px] text-gray-400 border-t border-gray-200">
        拖拽节点到画布
      </div>
    </div>
  );
}
