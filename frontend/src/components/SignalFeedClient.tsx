"use client";

import React, { useState, useEffect } from "react";
import PageHeader from "./PageHeader";
import Badge from "./Badge";
import { useSSE } from "@/src/hooks/useSSE";
import type { SignalRow, SSESignalPayload } from "@/src/types/api";

interface SignalFeedClientProps {
  initialSignals: SignalRow[];
}

type BadgeVariant = "default" | "positive" | "negative" | "warning" | "info" | "muted";

function directionVariant(dir: string | null): BadgeVariant {
  if (dir === "long") return "positive";
  if (dir === "short") return "negative";
  return "muted";
}

export default function SignalFeedClient({ initialSignals }: SignalFeedClientProps) {
  const [signals, setSignals] = useState<SignalRow[]>(initialSignals);
  const { lastEvent } = useSSE();

  useEffect(() => {
    if (!lastEvent || lastEvent.name !== "signals") return;
    const event = lastEvent.payload as SSESignalPayload;
    if (!event || typeof event !== "object" || !event.signal_id) return;

    const newRow: SignalRow = {
      signal_id: event.signal_id,
      created_at: event.created_at ?? new Date().toISOString(),
      symbol: event.symbol ?? null,
      earnings_event_id: null,
      eps_gap: null,
      quality_score: event.quality_score ?? null,
      three_axis_composite: event.three_axis_composite ?? null,
      naive_position_size: null,
      direction: event.direction ?? null,
      status: null,
    };

    setSignals((prev) => [newRow, ...prev].slice(0, 20));
  }, [lastEvent]);

  const formatTs = (iso: string | null): string => {
    if (!iso) return "-";
    return new Date(iso).toISOString().replace("T", " ").slice(0, 19);
  };

  const ROW_BG_ODD = "#0A1628";
  const ROW_BG_EVEN = "#0C1D35";
  const ROW_BG_HOVER = "#132035";

  return (
    <div style={{ padding: "32px 32px" }}>
      <PageHeader title="Signal Feed" />

      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            tableLayout: "fixed",
            borderCollapse: "collapse",
          }}
        >
          <colgroup>
            <col style={{ width: "160px" }} />
            <col style={{ width: "80px" }} />
            <col style={{ width: "80px" }} />
            <col style={{ width: "96px" }} />
            <col style={{ width: "96px" }} />
            <col style={{ width: "120px" }} />
            <col style={{ width: "96px" }} />
            <col style={{ width: "80px" }} />
          </colgroup>
          <thead>
            <tr
              style={{
                backgroundColor: "#0F2040",
                height: "40px",
              }}
            >
              {[
                "TIMESTAMP",
                "SYMBOL",
                "DIRECTION",
                "EPS GAP",
                "QUALITY",
                "3-AXIS",
                "SIZE",
                "STATUS",
              ].map((col) => (
                <th
                  key={col}
                  style={{
                    padding: "0 12px",
                    fontSize: "12px",
                    fontWeight: 500,
                    color: "#6B8EAD",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    textAlign: "left",
                    fontFamily: "Inter, system-ui, sans-serif",
                  }}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {signals.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  style={{
                    padding: "48px",
                    textAlign: "center",
                    fontSize: "14px",
                    color: "#6B8EAD",
                    fontFamily: "Inter, system-ui, sans-serif",
                  }}
                >
                  No signals recorded. Earnings events will appear here once the
                  signal engine processes data.
                </td>
              </tr>
            ) : (
              signals.map((signal, idx) => {
                const epsGap = signal.eps_gap ?? 0;
                return (
                  <tr
                    key={signal.signal_id}
                    style={{
                      backgroundColor: idx % 2 === 0 ? ROW_BG_ODD : ROW_BG_EVEN,
                      height: "48px",
                      cursor: "default",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLTableRowElement).style.backgroundColor =
                        ROW_BG_HOVER;
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLTableRowElement).style.backgroundColor =
                        idx % 2 === 0 ? ROW_BG_ODD : ROW_BG_EVEN;
                    }}
                  >
                    <td
                      className="mono"
                      style={{ padding: "0 12px", fontSize: "13px", color: "#6B8EAD" }}
                    >
                      {formatTs(signal.created_at)}
                    </td>
                    <td
                      style={{
                        padding: "0 12px",
                        fontSize: "14px",
                        fontWeight: 600,
                        color: "white",
                        textTransform: "uppercase",
                        fontFamily: "Inter, system-ui, sans-serif",
                      }}
                    >
                      {signal.symbol ?? "-"}
                    </td>
                    <td style={{ padding: "0 12px" }}>
                      <Badge variant={directionVariant(signal.direction)}>
                        {signal.direction ?? "-"}
                      </Badge>
                    </td>
                    <td
                      className="mono"
                      style={{
                        padding: "0 12px",
                        fontSize: "13px",
                        color:
                          signal.eps_gap === null
                            ? "#6B8EAD"
                            : epsGap >= 0
                              ? "#27AE60"
                              : "#E74C3C",
                      }}
                    >
                      {signal.eps_gap === null
                        ? "-"
                        : `${epsGap >= 0 ? "+" : ""}${epsGap.toFixed(4)}`}
                    </td>
                    <td
                      className="mono"
                      style={{ padding: "0 12px", fontSize: "13px", color: "white" }}
                    >
                      {signal.quality_score === null
                        ? "-"
                        : signal.quality_score.toFixed(2)}
                    </td>
                    <td
                      className="mono"
                      style={{ padding: "0 12px", fontSize: "13px", color: "white" }}
                    >
                      {signal.three_axis_composite === null
                        ? "-"
                        : signal.three_axis_composite.toFixed(4)}
                    </td>
                    <td
                      className="mono"
                      style={{ padding: "0 12px", fontSize: "13px", color: "#6B8EAD" }}
                    >
                      {signal.naive_position_size === null
                        ? "-"
                        : `${(signal.naive_position_size * 100).toFixed(2)}%`}
                    </td>
                    <td
                      style={{
                        padding: "0 12px",
                        fontSize: "12px",
                        color: "#6B8EAD",
                        fontFamily: "Inter, system-ui, sans-serif",
                      }}
                    >
                      {signal.status ?? "-"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
