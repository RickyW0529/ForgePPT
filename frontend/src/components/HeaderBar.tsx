import { useTaskStore } from '@/stores/useTaskStore';

export default function HeaderBar() {
  const overallStatus = useTaskStore((s) => s.overallStatus);

  const statusLabel = {
    idle: '等待上传',
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    error: '执行失败',
  }[overallStatus];

  const statusColor = {
    idle: 'bg-gray-200 text-gray-700',
    pending: 'bg-blue-100 text-blue-700',
    processing: 'bg-blue-200 text-blue-800',
    completed: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
  }[overallStatus];

  return (
    <header className="h-12 bg-deepblue-800 text-white flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-lg">PPT Agent</span>
        <span className="w-2 h-2 rounded-full bg-green-400" />
      </div>
      <div className={`px-3 py-1 rounded-full text-xs font-medium ${statusColor}`}>
        {statusLabel}
      </div>
    </header>
  );
}
