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
