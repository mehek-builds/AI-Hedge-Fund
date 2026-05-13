"use client";

import React, { useState, useEffect } from "react";
import PageHeader from "./PageHeader";
import Badge from "./Badge";
import { useSSE } from "@/src/hooks/useSSE";
import type { Position, SSEPositionPayload } from "@/src/types/api";

interface PositionsClientProps {
  initialPositions: Position[];
}

type BadgeVariant = "default" | "positive" | "negative" | "warning" | "info" | "muted";

function thesisVariant(status: string | null): BadgeVariant {
  if (status === "INTACT") return "positive";
  if (status === "MONITOR") return "warning";
  if (status === "BROKEN") return "negative";
  return "muted";
}

export default function PositionsClient({ initialPositions }: PositionsClientProps) {
  const [positions, setPositions] = useState<Position[]>(initialPositions);
  const { lastEvent } = useSSE();

  useEffect(() => {
    if (!lastEvent || lastEvent.name !== "positions") return;
    const event = lastEvent.payload as SSEPositionPayload;
    if (!event || typeof event !== "object" || !event.symbol) return;

    setPositions((prev) => {
      if (event.status === "closed") {
        return prev.filter((p) => p.symbol !== event.symbol);
      }
      const exists = prev.findIndex((p) => p.symbol === event.symbol);
      const updated: Position = {
        symbol: event.symbol,
        qty: event.qty ?? null,
        avg_entry_price: null,
        current_price: event.current_price ?? null,
        unrealized_pnl: event.unrealized_pnl ?? null,
        unrealized_pnl_pct: null,
        stop_loss_price: null,
        take_profit_price: null,
        thesis_status: null,
        snapshot_at: event.snapshot_at ?? new Date().toISOString(),
        status: event.status ?? null,
      };
      if (exists >= 0) {
        const next = [...prev];
        next[exists] = { ...prev[exists], ...updated };
        return next;
      }
      return [...prev, updated];
    });
  }, [lastEvent]);

  const ROW_BG_ODD = "#0A1628";
  const ROW_BG_EVEN = "#0C1D35";
  const ROW_BG_HOVER = "#132035";

  return (
    <div style={{ padding: "32px 32px" }}>
      <PageHeader title="Position Manager" />

      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            tableLayout: "fixed",
            borderCollapse: "collapse",
          }}
        >
          <colgroup>
            <col style={{ width: "80px" }} />
            <col style={{ width: "72px" }} />
            <col style={{ width: "96px" }} />
            <col style={{ width: "96px" }} />
            <col style={{ width: "96px" }} />
            <col style={{ width: "96px" }} />
            <col style={{ width: "120px" }} />
            <col style={{ width: "96px" }} />
            <col style={{ width: "140px" }} />
          </colgroup>
          <thead>
            <tr style={{ backgroundColor: "#0F2040", height: "40px" }}>
              {[
                "SYMBOL",
                "QTY",
                "ENTRY",
                "STOP",
                "TARGET",
                "CURRENT",
                "UNREAL. P&L",
                "THESIS",
                "UPDATED",
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
            {positions.length === 0 ? (
              <tr>
                <td
                  colSpan={9}
                  style={{
                    padding: "48px",
                    textAlign: "center",
                    fontSize: "14px",
                    color: "#6B8EAD",
                    fontFamily: "Inter, system-ui, sans-serif",
                  }}
                >
                  No open positions. Active bracket orders will appear here once
                  paper trading begins.
                </td>
              </tr>
            ) : (
              positions.map((pos, idx) => {
                const pnl = pos.unrealized_pnl ?? 0;
                const pnlPct = pos.unrealized_pnl_pct ?? 0;
                const pnlFormatted = `${pnl >= 0 ? "+" : ""}$${Math.abs(pnl).toFixed(2)} (${pnlPct >= 0 ? "+" : ""}${(pnlPct * 100).toFixed(1)}%)`;
                const pnlColor = pnl >= 0 ? "#27AE60" : "#E74C3C";

                return (
                  <tr
                    key={pos.symbol}
                    style={{
                      backgroundColor: idx % 2 === 0 ? ROW_BG_ODD : ROW_BG_EVEN,
                      height: "52px",
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
                      style={{
                        padding: "0 12px",
                        fontSize: "14px",
                        fontWeight: 600,
                        color: "white",
                        fontFamily: "Inter, system-ui, sans-serif",
                      }}
                    >
                      {pos.symbol}
                    </td>
                    <td
                      className="mono"
                      style={{ padding: "0 12px", fontSize: "13px", color: "#6B8EAD" }}
                    >
                      {pos.qty === null ? "-" : pos.qty.toFixed(4)}
                    </td>
                    <td
                      className="mono"
                      style={{ padding: "0 12px", fontSize: "13px", color: "white" }}
                    >
                      {pos.avg_entry_price === null
                        ? "-"
                        : `$${pos.avg_entry_price.toFixed(4)}`}
                    </td>
                    <td
                      className="mono"
                      style={{ padding: "0 12px", fontSize: "13px", color: "#E74C3C" }}
                    >
                      {pos.stop_loss_price === null
                        ? "-"
                        : `$${pos.stop_loss_price.toFixed(2)}`}
                    </td>
                    <td
                      className="mono"
                      style={{ padding: "0 12px", fontSize: "13px", color: "#27AE60" }}
                    >
                      {pos.take_profit_price === null
                        ? "-"
                        : `$${pos.take_profit_price.toFixed(2)}`}
                    </td>
                    <td
                      className="mono"
                      style={{ padding: "0 12px", fontSize: "13px", color: "white" }}
                    >
                      {pos.current_price === null
                        ? "-"
                        : `$${pos.current_price.toFixed(2)}`}
                    </td>
                    <td
                      className="mono"
                      style={{
                        padding: "0 12px",
                        fontSize: "16px",
                        fontWeight: 500,
                        color: pnlColor,
                      }}
                    >
                      {pos.unrealized_pnl === null ? "-" : pnlFormatted}
                    </td>
                    <td style={{ padding: "0 12px" }}>
                      <Badge variant={thesisVariant(pos.thesis_status)}>
                        {pos.thesis_status ?? "-"}
                      </Badge>
                    </td>
                    <td
                      className="mono"
                      style={{ padding: "0 12px", fontSize: "13px", color: "#6B8EAD" }}
                    >
                      {pos.snapshot_at === null
                        ? "-"
                        : new Date(pos.snapshot_at).toTimeString().slice(0, 8)}
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
