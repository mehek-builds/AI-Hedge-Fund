"use client";

import React, { useState, useEffect } from "react";
import KPICard from "./KPICard";
import PageHeader from "./PageHeader";
import LastAlertsPanel from "./LastAlertsPanel";
import { useSSE } from "@/src/hooks/useSSE";
import { fetcher } from "@/src/lib/fetcher";
import type {
  DashboardData,
  AlertRecord,
  SSEAlertPayload,
  SSEPositionPayload,
} from "@/src/types/api";

interface DashboardClientProps {
  initialData: DashboardData | null;
}

export default function DashboardClient({ initialData }: DashboardClientProps) {
  const [data, setData] = useState<DashboardData | null>(initialData);
  const { lastEvent } = useSSE();

  // Refresh dashboard data every 30 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const refreshed = await fetcher<DashboardData>("/api/v1/dashboard");
        setData(refreshed);
      } catch {
        // silently ignore refresh errors
      }
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  // Handle SSE events
  useEffect(() => {
    if (!lastEvent) return;

    if (lastEvent.name === "alerts") {
      const event = lastEvent.payload as SSEAlertPayload;
      if (!event || typeof event !== "object") return;
      const newAlert: AlertRecord = {
        alert_id: event.alert_id ?? String(Date.now()),
        created_at: event.created_at ?? new Date().toISOString(),
        level: event.level ?? null,
        category: event.category ?? null,
        symbol: event.symbol ?? null,
        message: event.message ?? "",
      };
      setData((prev) => {
        if (!prev) return prev;
        const updated = [newAlert, ...prev.recent_alerts].slice(0, 5);
        return { ...prev, recent_alerts: updated };
      });
    }

    if (lastEvent.name === "positions") {
      const event = lastEvent.payload as SSEPositionPayload;
      if (!event || typeof event !== "object") return;
      setData((prev) => {
        if (!prev) return prev;
        const isClose = event.status === "closed";
        const newCount = isClose
          ? Math.max(0, prev.position_count - 1)
          : prev.position_count + 1;
        return { ...prev, position_count: newCount };
      });
    }
  }, [lastEvent]);

  if (data === null) {
    return (
      <div style={{ padding: "32px 32px" }}>
        <PageHeader title="Dashboard" />
        <div
          style={{
            textAlign: "center",
            paddingTop: "64px",
          }}
        >
          <h2
            style={{
              fontSize: "16px",
              color: "white",
              fontWeight: 500,
              marginBottom: "8px",
            }}
          >
            No live data yet
          </h2>
          <p style={{ fontSize: "14px", color: "#6B8EAD" }}>
            Waiting for signals and positions from the backend. Ensure the
            FastAPI service is running.
          </p>
        </div>
      </div>
    );
  }

  const pnl = data.total_unrealized_pnl ?? 0;
  const pnlFormatted = `${pnl >= 0 ? "+" : ""}$${Math.abs(pnl).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const macroOpen = data.macro_gate_open;

  return (
    <div style={{ padding: "32px 32px" }}>
      <PageHeader title="Dashboard" />

      {/* KPI Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr 1fr",
          gap: "24px",
          marginBottom: "32px",
        }}
      >
        {/* Portfolio NAV — no nav field in API, show total unrealized P&L as primary */}
        <KPICard
          label="Unrealized P&L"
          value={pnlFormatted}
          positive={pnl >= 0}
          negative={pnl < 0}
        />

        {/* Open Positions */}
        <KPICard
          label="Open Positions"
          value={String(data.position_count ?? 0)}
        />

        {/* Macro Gate — uses Inter font, render a custom card */}
        <div
          style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid #1A3050",
            borderRadius: "8px",
            padding: "20px 24px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <span
            style={{
              fontSize: "12px",
              color: "var(--color-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            Macro Gate
          </span>
          <span
            style={{
              fontSize: "20px",
              fontWeight: 600,
              color:
                macroOpen === null
                  ? "#6B8EAD"
                  : macroOpen
                    ? "#27AE60"
                    : "#E67E22",
              lineHeight: 1,
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            {macroOpen === null ? "UNKNOWN" : macroOpen ? "OPEN" : "GATED"}
          </span>
        </div>

        {/* Macro Score placeholder until API exposes it */}
        <div
          style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid #1A3050",
            borderRadius: "8px",
            padding: "20px 24px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <span
            style={{
              fontSize: "12px",
              color: "var(--color-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            System Status
          </span>
          <span
            style={{
              fontSize: "20px",
              fontWeight: 600,
              color: "#27AE60",
              lineHeight: 1,
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            LIVE
          </span>
        </div>
      </div>

      {/* Recent Alerts */}
      <LastAlertsPanel alerts={data.recent_alerts ?? []} />
    </div>
  );
}
