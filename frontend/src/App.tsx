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
    <div className="h-screen w-screen overflow-hidden bg-surface p-4 text-slate-900">
      <SSEConnector />
      <div className="flex h-full flex-col overflow-hidden rounded-[1.5rem] border border-border bg-panel shadow-soft">
        <HeaderBar />
        <main className="flex min-h-0 flex-1 overflow-hidden bg-surface/70">
          <ReactFlowProvider>
            <NodePalette />
            <FlowCanvas />
          </ReactFlowProvider>
          <SidebarPanel />
        </main>
      </div>
      <ToastContainer />
    </div>
  );
}
