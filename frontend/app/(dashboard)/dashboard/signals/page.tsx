"use client";
import { useQuery, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { api, Signal } from "@/lib/api";
import { useSSE } from "@/lib/sse";
import { SectionHeader } from "@/components/ui/section-header";
import { fmtSigned, fmtNum, fmtDatetime, signClass } from "@/lib/format";

const qc = new QueryClient();
export default function SignalsPage() {
  return <QueryClientProvider client={qc}><Signals /></QueryClientProvider>;
}

function Signals() {
  const [filter, setFilter] = useState<"all" | "high" | "new">("all");
  const { data, refetch, isLoading } = useQuery({
    queryKey: ["signals-full"],
    queryFn: api.signals,
    refetchInterval: 30_000,
  });
  useSSE("/stream/signals", { onMessage: () => refetch() });

  const rows = (data ?? []).filter(s => {
    if (filter === "high") return (s.signal_composite ?? 0) >= 0.75;
    if (filter === "new") {
      const ts = new Date(s.announcement_ts).getTime();
      return Date.now() - ts < 4 * 60 * 60 * 1000;
    }
    return true;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <SectionHeader title="Signal feed" right={`${rows.length} events`} />

      {/* Sub-nav */}
      <div style={{ display: "flex", gap: 0, padding: "0 10px", borderBottom: "1px solid var(--color-border)" }}>
        {(["all","high","new"] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: "4px 8px", background: "none", border: "none", cursor: "pointer",
            fontSize: 9, letterSpacing: "0.06em", textTransform: "uppercase",
            color: filter === f ? "var(--color-text-primary)" : "var(--color-text-muted)",
            borderBottom: filter === f ? "1.5px solid var(--color-amber)" : "1.5px solid transparent",
            marginBottom: -1,
          }}>{f}</button>
        ))}
      </div>

      {/* Table header */}
      <div style={{ display: "grid", gridTemplateColumns: "60px 90px 80px 80px 80px 80px 1fr", gap: 0, padding: "4px 12px", borderBottom: "1px solid var(--color-border)" }}>
        {["Ticker","Sector","EPS Actual","EPS Implied","Gap (σ)","Quality","Composite"].map((h, i) => (
          <span key={h} style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", textAlign: i > 1 ? "right" : "left" }}>{h}</span>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {isLoading && <Loading />}
        {rows.map(sig => <SignalRow key={sig.id} sig={sig} />)}
        {!isLoading && rows.length === 0 && <Empty />}
      </div>
    </div>
  );
}

function SignalRow({ sig }: { sig: Signal }) {
  const composite = sig.signal_composite ?? 0;
  const cls = composite >= 0.8 ? "pos" : composite >= 0.5 ? "warn" : "muted";
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "60px 90px 80px 80px 80px 80px 1fr",
      padding: "5px 12px", borderBottom: "1px solid var(--color-border)",
      alignItems: "center",
    }}>
      <span className="num" style={{ fontWeight: 600, fontSize: 11 }}>{sig.ticker}</span>
      <span style={{ fontSize: 10, color: "var(--color-text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sig.gics_sector ?? "--"}</span>
      <span className="num" style={{ fontSize: 10, textAlign: "right" }}>{fmtNum(sig.eps_actual, 2)}</span>
      <span className="num" style={{ fontSize: 10, textAlign: "right" }}>{fmtNum(sig.eps_implied, 2)}</span>
      <span className={`num ${signClass(sig.eps_gap_sigma)}`} style={{ fontSize: 10, textAlign: "right" }}>{fmtSigned(sig.eps_gap_sigma)}</span>
      <span className="num" style={{ fontSize: 10, textAlign: "right" }}>{fmtNum(sig.quality_score)}</span>
      <span className={`num ${cls}`} style={{ fontSize: 11, fontWeight: 600, textAlign: "right" }}>{fmtNum(composite)}</span>
    </div>
  );
}

function Loading() { return <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>Loading...</div>; }
function Empty() { return <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>No signals match this filter.</div>; }
