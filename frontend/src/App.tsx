import { ReactFlowProvider } from '@xyflow/react';
import FlowCanvas from './components/FlowCanvas';
import HeaderBar from './components/HeaderBar';
import SidebarPanel from './components/SidebarPanel';
import ToastContainer from './components/ToastContainer';
import NodePalette from './components/NodePalette';
import { useSSE } from './hooks/useSSE';

function SSEConnector() {
  useSSE();
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
