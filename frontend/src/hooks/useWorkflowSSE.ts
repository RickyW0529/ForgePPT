import { useEffect, useRef } from 'react';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import { useUIStore } from '@/stores/useUIStore';

const MAX_RECONNECT = 5;
const RECONNECT_BASE_MS = 1000;

export function useWorkflowSSE() {
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const setNodeStatus = useWorkflowStore((s) => s.setNodeStatus);
  const setExportPath = useWorkflowStore((s) => s.setExportPath);
  const setExecuting = useWorkflowStore((s) => s.setExecuting);
  const addToast = useUIStore((s) => s.addToast);

  const completedRef = useRef(false);

  useEffect(() => {
    if (!workflowId) return;
    completedRef.current = false;

    let retryCount = 0;
    let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let active = true;

    const connect = async () => {
      if (!active || completedRef.current) return;

      const ctrl = new AbortController();
      reader = null;

      try {
        const resp = await fetch(`/api/v1/workflows/${workflowId}/events`, {
          signal: ctrl.signal,
          headers: { Accept: 'text/event-stream' },
        });

        if (!resp.ok || !resp.body) {
          throw new Error(`SSE connection failed: ${resp.status}`);
        }

        retryCount = 0;
        reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (active) {
          if (ctrl.signal.aborted) break;
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const normalized = buffer.replace(/\r\n/g, '\n');
          const messages = normalized.split('\n\n');
          buffer = messages.pop() || '';

          for (const message of messages) {
            if (ctrl.signal.aborted || !active) break;
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
                completedRef.current = true;
                addToast({ type: 'success', message: '工作流执行完成' });
              }
            } catch {
              // Ignore malformed SSE data
            }
          }
        }
      } catch (err) {
        if (!active) return;
        if (err instanceof Error && err.name === 'AbortError') return;

        retryCount += 1;
        if (retryCount > MAX_RECONNECT) {
          console.error('SSE error:', err);
          addToast({ type: 'error', message: 'SSE 连接断开，已达最大重试次数' });
          setExecuting(false);
          return;
        }

        const delay = RECONNECT_BASE_MS * Math.pow(2, retryCount - 1);
        timeoutId = setTimeout(connect, delay);
        return;
      }
    };

    connect();

    return () => {
      active = false;
      if (timeoutId) clearTimeout(timeoutId);
      reader?.cancel().catch(() => {});
    };
  }, [workflowId, setNodeStatus, setExportPath, setExecuting, addToast]);
}
