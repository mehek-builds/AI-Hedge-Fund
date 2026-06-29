"use client";
import { useEffect, useRef, useCallback } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("pead_token");
}

interface UseSSEOptions {
  onMessage: (data: unknown) => void;
  onError?: (e: Event) => void;
  enabled?: boolean;
}

/** Auto-reconnecting SSE hook with exponential backoff. */
export function useSSE(path: string, { onMessage, onError, enabled = true }: UseSSEOptions) {
  const esRef = useRef<EventSource | null>(null);
  const retryRef = useRef(1000);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (!enabled) return;
    const token = getToken();
    const url = `${BASE}${path}${token ? `?token=${token}` : ""}`;
    const es = new EventSource(url, { withCredentials: true });
    esRef.current = es;

    es.onmessage = (e) => {
      retryRef.current = 1000; // reset backoff on success
      try {
        onMessageRef.current(JSON.parse(e.data));
      } catch {
        onMessageRef.current(e.data);
      }
    };

    es.onerror = (e) => {
      onError?.(e);
      es.close();
      esRef.current = null;
      // Exponential backoff: 1s → 2s → 4s → … → 30s max
      const delay = Math.min(retryRef.current, 30_000);
      retryRef.current = Math.min(retryRef.current * 2, 30_000);
      timerRef.current = setTimeout(connect, delay);
    };
  }, [path, enabled, onError]);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [connect]);
}
