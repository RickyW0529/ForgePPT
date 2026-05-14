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
