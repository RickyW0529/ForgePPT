import { useEffect } from 'react';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import { useUIStore } from '@/stores/useUIStore';

export function useWorkflowSSE() {
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const setNodeStatus = useWorkflowStore((s) => s.setNodeStatus);
  const setExportPath = useWorkflowStore((s) => s.setExportPath);
  const setExecuting = useWorkflowStore((s) => s.setExecuting);
  const addToast = useUIStore((s) => s.addToast);

  useEffect(() => {
    if (!workflowId) return;

    const ctrl = new AbortController();

    let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;

    const connect = async () => {
      try {
        const resp = await fetch(`/api/v1/workflows/${workflowId}/events`, {
          signal: ctrl.signal,
          headers: { Accept: 'text/event-stream' },
        });

        if (!resp.ok || !resp.body) {
          throw new Error(`SSE connection failed: ${resp.status}`);
        }

        reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          if (ctrl.signal.aborted) break;
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const normalized = buffer.replace(/\r\n/g, '\n');
          const messages = normalized.split('\n\n');
          buffer = messages.pop() || '';

          for (const message of messages) {
            if (ctrl.signal.aborted) break;
            const dataLines = message
              .split('\n')
              .filter((l) => l.startsWith('data:'))
              .map((l) => l.slice(5).trim());
            if (dataLines.length === 0) continue;

            const jsonStr = dataLines.join('\n');
            try {
              const event = JSON.parse(jsonStr);
              if (event.node_id) {
                setNodeStatus(event.node_id, event.status);
                if (event.status === 'error') {
                  addToast({ type: 'error', message: `节点 ${event.node_id} 执行失败` });
                }
              }
              if (event.export_path) {
                setExportPath(event.export_path);
                setExecuting(false);
                addToast({ type: 'success', message: '工作流执行完成' });
              }
            } catch {
              // Ignore malformed SSE data
            }
          }
        }
      } catch (err) {
        if (!(err instanceof Error) || err.name !== 'AbortError') {
          console.error('SSE error:', err);
          addToast({ type: 'error', message: 'SSE 连接断开' });
          setExecuting(false);
        }
      }
    };

    connect();

    return () => {
      ctrl.abort();
      reader?.cancel().catch(() => {});
    };
  }, [workflowId, setNodeStatus, setExportPath, setExecuting, addToast]);
}
