"use client";
import { useQuery, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { api, AlertRow as AlertData } from "@/lib/api";
import { useSSE } from "@/lib/sse";
import { SectionHeader } from "@/components/ui/section-header";
import { fmtDatetime } from "@/lib/format";

const qc = new QueryClient();
export default function AlertsPage() {
  return <QueryClientProvider client={qc}><Alerts /></QueryClientProvider>;
}

const EVENT_TYPES = ["", "SIGNAL_HIGH", "ORDER_FILL", "THESIS_CHANGE", "SLEEVE_REBAL", "ALPHA_GATE", "BACKTEST_GATE_FAIL", "MACRO_SHIFT"];

function Alerts() {
  const [eventType, setEventType] = useState("");
  const [limit, setLimit] = useState(100);

  const { data = [], isLoading, refetch } = useQuery({
    queryKey: ["alerts", eventType, limit],
    queryFn: () => api.alerts({ event_type: eventType || undefined, limit }),
    refetchInterval: 15_000,
  });
  useSSE("/stream/alerts", { onMessage: () => refetch() });

  const priorityColor = (p: string) =>
    p === "high" ? "var(--color-negative)" :
    p === "medium" ? "var(--color-warning)" : "var(--color-positive)";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <SectionHeader title="Alert log" right={`${data.length} events`} />

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, padding: "5px 10px", borderBottom: "1px solid var(--color-border)", alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Event type:</span>
        {EVENT_TYPES.map(et => (
          <button key={et} onClick={() => setEventType(et)} style={{
            padding: "2px 7px", borderRadius: 2,
            border: `1px solid ${eventType === et ? "var(--color-border-strong)" : "var(--color-border)"}`,
            background: eventType === et ? "var(--color-bg-card)" : "none",
            color: eventType === et ? "var(--color-text-primary)" : "var(--color-text-muted)",
            fontSize: 9, textTransform: "uppercase", letterSpacing: "0.05em", cursor: "pointer",
          }}>{et || "All"}</button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 9, color: "var(--color-text-muted)" }}>Limit:</span>
          <select value={limit} onChange={e => setLimit(Number(e.target.value))} style={{
            padding: "2px 6px", background: "var(--color-bg-panel)", border: "1px solid var(--color-border)",
            borderRadius: 3, color: "var(--color-text-primary)", fontSize: 10, fontFamily: "var(--font-family-mono)",
          }}>
            {[50, 100, 200].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      </div>

      {/* Table header */}
      <div style={{ display: "grid", gridTemplateColumns: "140px 80px 90px 60px 1fr 70px", padding: "3px 12px", borderBottom: "1px solid var(--color-border)" }}>
        {["Timestamp","Event type","Ticker","Priority","Title","Delivered"].map((h, i) => (
          <span key={h} style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", textAlign: i === 5 ? "right" : "left" }}>{h}</span>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {isLoading && <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>Loading...</div>}
        {data.map(a => (
          <div key={a.id} style={{ display: "grid", gridTemplateColumns: "140px 80px 90px 60px 1fr 70px", padding: "5px 12px", borderBottom: "1px solid var(--color-border)", alignItems: "center" }}>
            <span className="num muted" style={{ fontSize: 9 }}>{fmtDatetime(a.created_at)}</span>
            <span style={{ fontSize: 9, color: "var(--color-accent)", fontFamily: "var(--font-family-mono)", letterSpacing: "0.04em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.event_type}</span>
            <span className="num" style={{ fontSize: 10 }}>{a.ticker ?? "--"}</span>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: priorityColor(a.priority), flexShrink: 0 }} />
              <span style={{ fontSize: 9, color: priorityColor(a.priority), textTransform: "uppercase", letterSpacing: "0.04em" }}>{a.priority}</span>
            </div>
            <span style={{ fontSize: 10, color: "var(--color-text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.title}</span>
            <span style={{ fontSize: 10, textAlign: "right", color: a.delivered ? "var(--color-positive)" : "var(--color-text-muted)" }}>{a.delivered ? "Yes" : "No"}</span>
          </div>
        ))}
        {!isLoading && data.length === 0 && <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>No alerts match this filter.</div>}
      </div>
    </div>
  );
}
