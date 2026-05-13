"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export type SSEEventName = "signals" | "positions" | "rl_state" | "alerts";

export interface SSEData {
  signals: unknown;
  positions: unknown;
  rl_state: unknown;
  alerts: unknown;
}

export interface UseSSEResult {
  data: Partial<SSEData>;
  isConnected: boolean;
  lastEvent: { name: SSEEventName; payload: unknown; receivedAt: string } | null;
}

const SSE_URL = "/api/v1/events";
const CHANNELS: SSEEventName[] = ["signals", "positions", "rl_state", "alerts"];
const MAX_BACKOFF_MS = 30_000;

export function useSSE(): UseSSEResult {
  const [data, setData] = useState<Partial<SSEData>>({});
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<UseSSEResult["lastEvent"]>(null);

  const esRef = useRef<EventSource | null>(null);
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptRef = useRef(0);
  const unmountedRef = useRef(false);

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    const es = new EventSource(SSE_URL);
    esRef.current = es;

    es.onopen = () => {
      if (unmountedRef.current) return;
      setIsConnected(true);
      attemptRef.current = 0;
    };

    CHANNELS.forEach((channel) => {
      es.addEventListener(channel, (event: MessageEvent) => {
        if (unmountedRef.current) return;
        let payload: unknown = event.data;
        try {
          payload = JSON.parse(event.data as string);
        } catch {
          // leave as raw string if not valid JSON
        }
        setData((prev) => ({ ...prev, [channel]: payload }));
        setLastEvent({
          name: channel,
          payload,
          receivedAt: new Date().toISOString(),
        });
      });
    });

    es.onerror = () => {
      if (unmountedRef.current) return;
      setIsConnected(false);
      es.close();
      esRef.current = null;

      // Exponential backoff: 1s, 2s, 4s, 8s, ... capped at 30s
      const delay = Math.min(1_000 * 2 ** attemptRef.current, MAX_BACKOFF_MS);
      attemptRef.current += 1;
      retryTimeoutRef.current = setTimeout(connect, delay);
    };
  }, []);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      if (retryTimeoutRef.current !== null) {
        clearTimeout(retryTimeoutRef.current);
      }
      esRef.current?.close();
    };
  }, [connect]);

  return { data, isConnected, lastEvent };
}
