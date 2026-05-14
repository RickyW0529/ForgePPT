# 05 - SSE Connection Hook

**Files:**
- Create: `frontend/src/hooks/useSSE.ts`
- Modify: `frontend/src/main.tsx`

---

- [ ] **Step 1: Write the hook**

```typescript
// frontend/src/hooks/useSSE.ts
import { useEffect, useRef } from 'react';
import { useSSEStore } from '@/stores/useSSEStore';
import { useTaskStore } from '@/stores/useTaskStore';

const SSE_URL = '/api/v1/events';
const MAX_RETRIES = 10;

export function useSSE() {
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const retryDelayRef = useRef(1000);

  const setConnected = useSSEStore((s) => s.setConnected);
  const pushMessage = useSSEStore((s) => s.pushMessage);
  const setNodeStatus = useTaskStore((s) => s.setNodeStatus);
  const setOverallStatus = useTaskStore((s) => s.setOverallStatus);

  useEffect(() => {
    function connect() {
      if (eventSourceRef.current?.readyState === EventSource.OPEN) {
        return;
      }

      const es = new EventSource(SSE_URL);
      eventSourceRef.current = es;

      es.onopen = () => {
        setConnected(true);
        retryCountRef.current = 0;
        retryDelayRef.current = 1000;
      };

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          pushMessage({ type: data.event ?? 'message', payload: data });

          if (data.node && data.status) {
            setNodeStatus(data.node, data.status);
          }
          if (data.overall_status) {
            setOverallStatus(data.overall_status);
          }
        } catch {
          pushMessage({ type: 'raw', payload: event.data });
        }
      };

      es.onerror = () => {
        setConnected(false);
        es.close();

        if (retryCountRef.current < MAX_RETRIES) {
          retryCountRef.current += 1;
          setTimeout(connect, retryDelayRef.current);
          retryDelayRef.current = Math.min(retryDelayRef.current * 2, 30000);
        }
      };
    }

    connect();

    return () => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };
  }, [setConnected, pushMessage, setNodeStatus, setOverallStatus]);
}
```

- [ ] **Step 2: Integrate into App**

```tsx
// frontend/src/App.tsx
import { ReactFlowProvider } from '@xyflow/react';
import FlowCanvas from './components/FlowCanvas';
import HeaderBar from './components/HeaderBar';
import SidebarPanel from './components/SidebarPanel';
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
          <FlowCanvas />
        </ReactFlowProvider>
        <SidebarPanel />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useSSE.ts frontend/src/App.tsx
git commit -m "feat: add SSE connection hook with auto-reconnect"
```
