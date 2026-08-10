'use client';

import { useEffect, useRef, useCallback } from 'react';
import { WSEvent } from '@/types';

interface UseWebSocketOptions {
  onEvent: (event: WSEvent) => void;
  enabled?: boolean;
}

export function useWebSocket({ onEvent, enabled = true }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onEventRef = useRef(onEvent);

  // Keep callback ref fresh without triggering reconnect
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const connect = useCallback(() => {
    const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WS] Connected');
        reconnectAttemptRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data: WSEvent = JSON.parse(event.data);
          onEventRef.current(data);
        } catch (err) {
          console.error('[WS] Failed to parse message:', err);
        }
      };

      ws.onclose = (event) => {
        console.log('[WS] Disconnected:', event.code, event.reason);
        wsRef.current = null;
        scheduleReconnect();
      };

      ws.onerror = (error) => {
        console.error('[WS] Error:', error);
        ws.close();
      };
    } catch (err) {
      console.error('[WS] Connection failed:', err);
      scheduleReconnect();
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    const attempt = reconnectAttemptRef.current;
    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
    const delay = Math.min(1000 * Math.pow(2, attempt), 30000);
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${attempt + 1})`);

    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectAttemptRef.current += 1;
      connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    if (!enabled) return;

    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [enabled, connect]);
}
