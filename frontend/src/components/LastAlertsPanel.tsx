"use client";

import React from "react";
import Badge from "./Badge";
import type { AlertRecord } from "@/src/types/api";

interface LastAlertsPanelProps {
  alerts: AlertRecord[];
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  signal_generated: "#2471A3",
  order_submitted: "#9B59B6",
  order_filled: "#27AE60",
  stop_triggered: "#E74C3C",
  thesis_broken: "#E74C3C",
  macro_regime_change: "#E67E22",
  backtest_gate_pass: "#27AE60",
  backtest_gate_fail: "#E74C3C",
  rl_diversity_alert: "#E67E22",
};

function eventTypeColor(eventType: string | null): string {
  if (!eventType) return "#6B8EAD";
  return EVENT_TYPE_COLORS[eventType] ?? "#6B8EAD";
}

function formatRelative(iso: string | null): string {
  if (!iso) return "-";
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export default function LastAlertsPanel({ alerts }: LastAlertsPanelProps) {
  return (
    <div>
      <div
        style={{
          fontSize: "14px",
          fontWeight: 500,
          color: "#6B8EAD",
          marginBottom: "8px",
        }}
      >
        Recent Alerts
      </div>
      <div
        style={{
          backgroundColor: "#0F2040",
          borderRadius: "8px",
          border: "1px solid #1A3050",
          overflow: "hidden",
        }}
      >
        {alerts.length === 0 ? (
          <div
            style={{
              padding: "16px",
              fontSize: "14px",
              color: "#6B8EAD",
            }}
          >
            No recent alerts.
          </div>
        ) : (
          alerts.map((alert, idx) => (
            <div
              key={alert.alert_id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                height: "44px",
                padding: "0 16px",
                borderBottom:
                  idx < alerts.length - 1 ? "1px solid #1A3050" : "none",
              }}
            >
              <Badge variant="default">
                <span
                  style={{
                    color: eventTypeColor(alert.category),
                  }}
                >
                  {alert.category ?? alert.level ?? "alert"}
                </span>
              </Badge>
              <span
                style={{
                  flex: 1,
                  fontSize: "14px",
                  color: "white",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {alert.message}
              </span>
              <span
                className="mono"
                style={{
                  fontSize: "12px",
                  color: "#6B8EAD",
                  whiteSpace: "nowrap",
                }}
              >
                {formatRelative(alert.created_at)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
