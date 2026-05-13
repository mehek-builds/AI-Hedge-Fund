"use client";

import React, { useState, useEffect, useCallback } from "react";
import { CheckCircle2, Minus, AlertTriangle } from "lucide-react";
import { useSSE } from "@/src/hooks/useSSE";
import { AlertsPage, AlertItem, SSEAlertDispatchedPayload } from "@/src/types/api";
import PageHeader from "@/src/components/PageHeader";
import LoadingSpinner from "@/src/components/LoadingSpinner";

// ---------------------------------------------------------------------------
// Event type color map
// ---------------------------------------------------------------------------
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

const ALL_EVENT_TYPES = Object.keys(EVENT_TYPE_COLORS);

function eventTypeColor(type: string): string {
  return EVENT_TYPE_COLORS[type] ?? "#6B8EAD";
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface Props {
  initialPage: AlertsPage | null;
}

const PAGE_SIZE = 50;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function AlertsClient({ initialPage }: Props) {
  const [items, setItems] = useState<AlertItem[]>(
    initialPage?.items ?? []
  );
  const [total, setTotal] = useState<number>(initialPage?.total ?? 0);
  const [page, setPage] = useState(1);
  const [activeEventTypes, setActiveEventTypes] = useState<string[]>([]);
  const [showRateLimitedOnly, setShowRateLimitedOnly] = useState(false);
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { lastEvent } = useSSE();

  // ---------------------------------------------------------------------------
  // Fetch page
  // ---------------------------------------------------------------------------
  const fetchPage = useCallback(async () => {
    setLoading(true);
    try {
      const typeParam =
        activeEventTypes.length === 1
          ? `&event_type=${activeEventTypes[0]}`
          : "";
      const res = await fetch(
        `/api/v1/alerts?page=${page}&page_size=${PAGE_SIZE}${typeParam}`
      );
      if (!res.ok) return;
      const data: AlertsPage = await res.json();
      setItems(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, activeEventTypes]);

  useEffect(() => {
    // Skip the very first render if we already have initial data
    fetchPage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, activeEventTypes, showRateLimitedOnly]);

  // ---------------------------------------------------------------------------
  // SSE: prepend new alerts
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!lastEvent || lastEvent.name !== "alerts") return;
    if (page !== 1 || activeEventTypes.length > 0 || showRateLimitedOnly) return;

    const event = lastEvent.payload as SSEAlertDispatchedPayload;
    if (!event || event.event !== "alert_dispatched") return;

    const newItem: AlertItem = {
      id: event.id,
      event_type: event.event_type,
      payload: event.payload,
      created_at: event.created_at,
      delivered_sendgrid: event.delivered_sendgrid,
      delivered_slack: event.delivered_slack,
      rate_limited: event.rate_limited,
    };

    setItems((prev) => [newItem, ...prev].slice(0, PAGE_SIZE));
    setTotal((t) => t + 1);
  }, [lastEvent, page, activeEventTypes, showRateLimitedOnly]);

  // ---------------------------------------------------------------------------
  // Filter toggle
  // ---------------------------------------------------------------------------
  function toggleEventType(type: string) {
    setActiveEventTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
    setPage(1);
  }

  function handleRateLimitedToggle() {
    setShowRateLimitedOnly((v) => !v);
    setPage(1);
  }

  // ---------------------------------------------------------------------------
  // Client-side filtering (for multi-type and rate limited)
  // ---------------------------------------------------------------------------
  const displayedItems = items.filter((item) => {
    if (
      activeEventTypes.length > 1 &&
      !activeEventTypes.includes(item.event_type)
    ) {
      return false;
    }
    if (showRateLimitedOnly && !item.rate_limited) return false;
    return true;
  });

  // ---------------------------------------------------------------------------
  // Pagination
  // ---------------------------------------------------------------------------
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  function formatTimestamp(ts: string): string {
    try {
      return new Date(ts).toISOString().replace("T", " ").slice(0, 19);
    } catch {
      return ts;
    }
  }

  function payloadSummary(payload: Record<string, unknown> | null): string {
    if (payload === null) return "{}";
    const s = JSON.stringify(payload);
    return s.length > 120 ? s.slice(0, 117) + "..." : s;
  }

  // ---------------------------------------------------------------------------
  // Styles
  // ---------------------------------------------------------------------------
  const thStyle: React.CSSProperties = {
    backgroundColor: "#0F2040",
    color: "#6B8EAD",
    fontSize: "12px",
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    height: "40px",
    padding: "0 12px",
    textAlign: "left",
    whiteSpace: "nowrap",
    borderBottom: "1px solid #1A3050",
  };

  const tdStyle: React.CSSProperties = {
    padding: "10px 12px",
    verticalAlign: "middle",
    borderBottom: "1px solid #0F2040",
  };

  return (
    <div>
      <PageHeader title="Alerts" subtitle="System event log" />
      <div style={{ padding: "24px 32px" }}>
        {/* Filter Row */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "8px",
            marginBottom: "16px",
          }}
        >
          {ALL_EVENT_TYPES.map((type) => {
            const isActive = activeEventTypes.includes(type);
            const color = eventTypeColor(type);
            return (
              <button
                key={type}
                onClick={() => toggleEventType(type)}
                style={{
                  padding: "4px 12px",
                  borderRadius: "12px",
                  fontSize: "11px",
                  fontWeight: 500,
                  cursor: "pointer",
                  border: isActive
                    ? `1px solid ${color}`
                    : "1px solid #1A3050",
                  backgroundColor: isActive
                    ? `${color}33`
                    : "#0F2040",
                  color: isActive ? color : "#6B8EAD",
                  transition: "all 0.15s",
                  fontFamily: "Inter, system-ui, sans-serif",
                }}
              >
                {type}
              </button>
            );
          })}

          <div
            style={{
              width: "1px",
              height: "20px",
              backgroundColor: "#1A3050",
              margin: "0 4px",
            }}
          />

          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              cursor: "pointer",
              color: "#6B8EAD",
              fontSize: "13px",
              userSelect: "none",
            }}
          >
            <input
              type="checkbox"
              checked={showRateLimitedOnly}
              onChange={handleRateLimitedToggle}
              style={{ cursor: "pointer" }}
            />
            Rate-limited only
          </label>
        </div>

        {/* Table */}
        <div style={{ position: "relative" }}>
          {loading && (
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                backgroundColor: "rgba(10,22,40,0.6)",
                zIndex: 10,
                borderRadius: "8px",
              }}
            >
              <LoadingSpinner />
            </div>
          )}

          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              tableLayout: "fixed",
            }}
          >
            <colgroup>
              <col style={{ width: "180px" }} />
              <col style={{ width: "180px" }} />
              <col />
              <col style={{ width: "80px" }} />
              <col style={{ width: "80px" }} />
              <col style={{ width: "90px" }} />
            </colgroup>
            <thead>
              <tr>
                <th style={thStyle}>TIMESTAMP</th>
                <th style={thStyle}>EVENT TYPE</th>
                <th style={thStyle}>PAYLOAD</th>
                <th style={{ ...thStyle, textAlign: "center" }}>SENDGRID</th>
                <th style={{ ...thStyle, textAlign: "center" }}>SLACK</th>
                <th style={{ ...thStyle, textAlign: "center" }}>RATE LIMITED</th>
              </tr>
            </thead>
            <tbody>
              {displayedItems.length === 0 && !loading ? (
                <tr>
                  <td
                    colSpan={6}
                    style={{
                      padding: "48px",
                      textAlign: "center",
                      color: "#6B8EAD",
                      fontSize: "14px",
                    }}
                  >
                    No alerts yet. System events will appear here as they are
                    generated.
                  </td>
                </tr>
              ) : (
                displayedItems.map((alert, rowIdx) => {
                  const isExpanded = expandedRowId === alert.id;
                  const rowBg = rowIdx % 2 === 0 ? "#0A1628" : "#0C1D35";
                  const color = eventTypeColor(alert.event_type);

                  return (
                    <React.Fragment key={alert.id}>
                      <tr
                        onClick={() =>
                          setExpandedRowId(isExpanded ? null : alert.id)
                        }
                        style={{
                          backgroundColor: rowBg,
                          cursor: "pointer",
                        }}
                        onMouseEnter={(e) => {
                          (e.currentTarget as HTMLTableRowElement).style.backgroundColor =
                            "#132035";
                        }}
                        onMouseLeave={(e) => {
                          (e.currentTarget as HTMLTableRowElement).style.backgroundColor =
                            rowBg;
                        }}
                      >
                        {/* Timestamp */}
                        <td style={tdStyle}>
                          <span
                            className="mono"
                            style={{ fontSize: "13px", color: "#6B8EAD" }}
                          >
                            {formatTimestamp(alert.created_at)}
                          </span>
                        </td>

                        {/* Event Type */}
                        <td style={tdStyle}>
                          <span
                            className="mono"
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              padding: "2px 8px",
                              borderRadius: "4px",
                              fontSize: "11px",
                              fontWeight: 500,
                              letterSpacing: "0.04em",
                              textTransform: "uppercase",
                              whiteSpace: "nowrap",
                              backgroundColor: `${color}22`,
                              color: color,
                              border: `1px solid ${color}55`,
                            }}
                          >
                            {alert.event_type}
                          </span>
                        </td>

                        {/* Payload Summary */}
                        <td style={{ ...tdStyle, overflow: "hidden" }}>
                          <span
                            style={{
                              fontSize: "14px",
                              color: "white",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                              display: "block",
                            }}
                          >
                            {payloadSummary(alert.payload)}
                          </span>
                        </td>

                        {/* SendGrid */}
                        <td style={{ ...tdStyle, textAlign: "center" }}>
                          {alert.delivered_sendgrid ? (
                            <CheckCircle2 size={16} color="#27AE60" />
                          ) : (
                            <Minus size={16} color="#1A3050" />
                          )}
                        </td>

                        {/* Slack */}
                        <td style={{ ...tdStyle, textAlign: "center" }}>
                          {alert.delivered_slack ? (
                            <CheckCircle2 size={16} color="#27AE60" />
                          ) : (
                            <Minus size={16} color="#1A3050" />
                          )}
                        </td>

                        {/* Rate Limited */}
                        <td style={{ ...tdStyle, textAlign: "center" }}>
                          {alert.rate_limited ? (
                            <AlertTriangle size={16} color="#E67E22" />
                          ) : (
                            <Minus size={16} color="#1A3050" />
                          )}
                        </td>
                      </tr>

                      {/* Expanded row */}
                      {isExpanded && (
                        <tr
                          style={{ backgroundColor: "#060E1A" }}
                        >
                          <td
                            colSpan={6}
                            style={{ padding: "0 12px 12px" }}
                          >
                            <pre
                              style={{
                                fontFamily: "JetBrains Mono, monospace",
                                fontSize: "12px",
                                backgroundColor: "#060E1A",
                                border: "1px solid #1A3050",
                                borderRadius: "6px",
                                padding: "16px",
                                margin: 0,
                                color: "#6B8EAD",
                                overflow: "auto",
                                maxHeight: "300px",
                              }}
                            >
                              {JSON.stringify(alert.payload, null, 2)}
                            </pre>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: "16px",
            marginTop: "24px",
          }}
        >
          <button
            disabled={page === 1}
            onClick={() => setPage((p) => p - 1)}
            style={{
              padding: "8px 16px",
              backgroundColor: "#0F2040",
              border: "1px solid #2471A3",
              color: "white",
              borderRadius: "6px",
              fontSize: "13px",
              cursor: page === 1 ? "not-allowed" : "pointer",
              opacity: page === 1 ? 0.4 : 1,
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            Previous
          </button>

          <span style={{ color: "#6B8EAD", fontSize: "13px" }}>
            Page {page} of {totalPages}
          </span>

          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            style={{
              padding: "8px 16px",
              backgroundColor: "#0F2040",
              border: "1px solid #2471A3",
              color: "white",
              borderRadius: "6px",
              fontSize: "13px",
              cursor: page >= totalPages ? "not-allowed" : "pointer",
              opacity: page >= totalPages ? 0.4 : 1,
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
