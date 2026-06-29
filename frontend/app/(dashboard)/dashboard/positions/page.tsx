"use client";
import { useQuery, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { api, Position } from "@/lib/api";
import { SectionHeader } from "@/components/ui/section-header";
import { ThesisBadge } from "@/components/ui/thesis-badge";
import { fmtCurrency, fmtPct, fmtNum, fmtDatetime, signClass } from "@/lib/format";

const qc = new QueryClient();
export default function PositionsPage() {
  return <QueryClientProvider client={qc}><Positions /></QueryClientProvider>;
}

function Positions() {
  const [sort, setSort] = useState<"pnl" | "ticker" | "size">("pnl");
  const { data = [], isLoading, refetch } = useQuery({
    queryKey: ["positions-full"],
    queryFn: api.positions,
    refetchInterval: 15_000,
  });

  const sorted = [...data].sort((a, b) => {
    if (sort === "ticker") return a.ticker.localeCompare(b.ticker);
    if (sort === "size") return (b.nav_weight ?? 0) - (a.nav_weight ?? 0);
    const pa = a.current_price && a.entry_price ? (a.current_price - a.entry_price) / a.entry_price : 0;
    const pb = b.current_price && b.entry_price ? (b.current_price - b.entry_price) / b.entry_price : 0;
    return pb - pa;
  });

  const cols = [
    { key: "ticker", label: "Ticker", w: "60px" },
    { key: "thesis", label: "Thesis", w: "90px" },
    { key: "entry", label: "Entry", w: "70px", right: true },
    { key: "current", label: "Current", w: "70px", right: true },
    { key: "stop", label: "Stop", w: "70px", right: true },
    { key: "target", label: "Target", w: "70px", right: true },
    { key: "upnl", label: "Unr. P&L", w: "80px", right: true },
    { key: "pnlPct", label: "P&L %", w: "70px", right: true },
    { key: "size", label: "Size %", w: "60px", right: true },
    { key: "days", label: "Days", w: "50px", right: true },
  ];
  const gridCols = cols.map(c => c.w).join(" ");

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <SectionHeader title="Position manager" right={`${data.length} open`} />

      {/* Sort controls */}
      <div style={{ display: "flex", gap: 4, padding: "4px 10px", borderBottom: "1px solid var(--color-border)" }}>
        <span style={{ fontSize: 9, color: "var(--color-text-muted)", marginRight: 4, alignSelf: "center" }}>Sort:</span>
        {(["pnl","ticker","size"] as const).map(s => (
          <button key={s} onClick={() => setSort(s)} style={{
            padding: "2px 7px", borderRadius: 2, border: "1px solid",
            borderColor: sort === s ? "var(--color-border-strong)" : "var(--color-border)",
            background: sort === s ? "var(--color-bg-card)" : "none",
            color: sort === s ? "var(--color-text-primary)" : "var(--color-text-muted)",
            fontSize: 9, textTransform: "uppercase", letterSpacing: "0.06em", cursor: "pointer",
          }}>{s === "pnl" ? "P&L" : s}</button>
        ))}
        <button onClick={() => refetch()} style={{
          marginLeft: "auto", padding: "2px 7px", borderRadius: 2,
          border: "1px solid var(--color-border)", background: "none",
          color: "var(--color-text-muted)", fontSize: 9, cursor: "pointer",
        }}>Refresh</button>
      </div>

      {/* Table header */}
      <div style={{ display: "grid", gridTemplateColumns: gridCols, padding: "3px 12px", borderBottom: "1px solid var(--color-border)" }}>
        {cols.map(c => (
          <span key={c.key} style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", textAlign: (c as any).right ? "right" : "left" }}>{c.label}</span>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {isLoading && <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>Loading...</div>}
        {sorted.map(p => {
          const pnlPct = p.entry_price && p.current_price
            ? ((p.current_price - p.entry_price) / p.entry_price) * 100 : null;
          return (
            <div key={p.id} style={{ display: "grid", gridTemplateColumns: gridCols, padding: "5px 12px", borderBottom: "1px solid var(--color-border)", alignItems: "center" }}>
              <span className="num" style={{ fontWeight: 600, fontSize: 11 }}>{p.ticker}</span>
              <ThesisBadge status={p.thesis_status} />
              <span className="num" style={{ fontSize: 10, textAlign: "right" }}>{fmtCurrency(p.entry_price)}</span>
              <span className="num" style={{ fontSize: 10, textAlign: "right" }}>{fmtCurrency(p.current_price)}</span>
              <span className="num" style={{ fontSize: 10, textAlign: "right", color: "var(--color-negative)" }}>{fmtCurrency(p.stop_price)}</span>
              <span className="num" style={{ fontSize: 10, textAlign: "right", color: "var(--color-positive)" }}>{fmtCurrency(p.target_price)}</span>
              <span className={`num ${signClass(p.unrealized_pnl)}`} style={{ fontSize: 10, textAlign: "right" }}>{fmtCurrency(p.unrealized_pnl)}</span>
              <span className={`num ${signClass(pnlPct)}`} style={{ fontSize: 10, textAlign: "right" }}>{fmtPct(pnlPct)}</span>
              <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>{p.nav_weight != null ? fmtPct(p.nav_weight * 100, 1) : "--"}</span>
              <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>{p.days_held ?? "--"}</span>
            </div>
          );
        })}
        {!isLoading && sorted.length === 0 && <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>No open positions.</div>}
      </div>
    </div>
  );
}
