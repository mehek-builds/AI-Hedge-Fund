"use client";
import { useQuery, useMutation, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import Link from "next/link";
import { api, BacktestRun } from "@/lib/api";
import { SectionHeader } from "@/components/ui/section-header";
import { fmtPct, fmtNum, fmtDatetime } from "@/lib/format";

const qc = new QueryClient();
export default function BacktestsPage() {
  return <QueryClientProvider client={qc}><BacktestExplorer /></QueryClientProvider>;
}

function BacktestExplorer() {
  const [showTrigger, setShowTrigger] = useState(false);
  const { data = [], isLoading, refetch } = useQuery({
    queryKey: ["backtest-runs"],
    queryFn: api.backtestRuns,
    refetchInterval: 30_000,
  });

  const [cfg, setCfg] = useState({
    start_date: "2023-01-01",
    end_date: "2024-12-31",
    initial_nav: 1_000_000,
    min_signal_threshold: 1.0,
    min_quality_score: 0.65,
    slippage_bps: 12.5,
    enable_shorts: false,
    run_label: "",
  });

  const trigger = useMutation({
    mutationFn: () => api.triggerBacktest(cfg),
    onSuccess: () => { setShowTrigger(false); refetch(); },
  });

  const statusColor = (s: string) =>
    s === "completed" ? "var(--color-positive)" :
    s === "running"   ? "var(--color-warning)"  :
    s === "failed"    ? "var(--color-negative)"  : "var(--color-text-muted)";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <SectionHeader title="Backtest explorer" right={`${data.length} runs`} />

      {/* Actions */}
      <div style={{ display: "flex", gap: 8, padding: "6px 10px", borderBottom: "1px solid var(--color-border)", alignItems: "center" }}>
        <button onClick={() => setShowTrigger(!showTrigger)} style={{
          padding: "3px 10px", borderRadius: 3, border: "1px solid var(--color-accent)",
          background: "none", color: "var(--color-accent)", fontSize: 10,
          letterSpacing: "0.06em", textTransform: "uppercase", cursor: "pointer", fontWeight: 500,
        }}>+ New run</button>
        <button onClick={() => refetch()} style={{
          padding: "3px 10px", borderRadius: 3, border: "1px solid var(--color-border)",
          background: "none", color: "var(--color-text-muted)", fontSize: 10,
          letterSpacing: "0.06em", textTransform: "uppercase", cursor: "pointer",
        }}>Refresh</button>
      </div>

      {/* Trigger form */}
      {showTrigger && (
        <div style={{ padding: "12px 12px", borderBottom: "1px solid var(--color-border)", background: "var(--color-bg-card)", display: "flex", flexWrap: "wrap", gap: 12 }}>
          {[
            { key: "start_date", label: "Start date", type: "text" },
            { key: "end_date", label: "End date", type: "text" },
            { key: "initial_nav", label: "Initial NAV", type: "number" },
            { key: "min_signal_threshold", label: "Min signal σ", type: "number" },
            { key: "min_quality_score", label: "Min quality", type: "number" },
            { key: "slippage_bps", label: "Slippage bps", type: "number" },
            { key: "run_label", label: "Label", type: "text" },
          ].map(f => (
            <div key={f.key}>
              <label style={{ display: "block", fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3 }}>{f.label}</label>
              <input
                type={f.type}
                value={String((cfg as any)[f.key])}
                onChange={e => setCfg(prev => ({ ...prev, [f.key]: f.type === "number" ? Number(e.target.value) : e.target.value }))}
                style={{ padding: "4px 8px", background: "var(--color-bg-panel)", border: "1px solid var(--color-border)", borderRadius: 3, color: "var(--color-text-primary)", fontSize: 11, fontFamily: "var(--font-family-mono)", width: 120 }}
              />
            </div>
          ))}
          <div style={{ display: "flex", alignItems: "flex-end", gap: 6 }}>
            <button onClick={() => trigger.mutate()} disabled={trigger.isPending} style={{
              padding: "4px 14px", borderRadius: 3, border: "none",
              background: "var(--color-accent)", color: "#fff", fontSize: 10,
              fontWeight: 500, letterSpacing: "0.06em", textTransform: "uppercase", cursor: "pointer",
            }}>{trigger.isPending ? "Queuing..." : "Queue run"}</button>
            <button onClick={() => setShowTrigger(false)} style={{ padding: "4px 10px", borderRadius: 3, border: "1px solid var(--color-border)", background: "none", color: "var(--color-text-muted)", fontSize: 10, cursor: "pointer" }}>Cancel</button>
          </div>
        </div>
      )}

      {/* Table header */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 90px 90px 70px 70px 70px 70px 80px", padding: "4px 12px", borderBottom: "1px solid var(--color-border)" }}>
        {["Label","Start","End","Return","Sharpe","MaxDD","WinRate","Status"].map((h, i) => (
          <span key={h} style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", textAlign: i > 1 ? "right" : "left" }}>{h}</span>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {isLoading && <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>Loading...</div>}
        {data.map(run => (
          <Link key={run.id} href={`/dashboard/backtests/${run.id}`} style={{ textDecoration: "none" }}>
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 90px 90px 70px 70px 70px 70px 80px",
              padding: "5px 12px", borderBottom: "1px solid var(--color-border)",
              alignItems: "center", cursor: "pointer",
            }}
              onMouseEnter={e => (e.currentTarget as HTMLDivElement).style.background = "var(--color-bg-card)"}
              onMouseLeave={e => (e.currentTarget as HTMLDivElement).style.background = ""}
            >
              <span style={{ fontSize: 11, color: "var(--color-text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{run.label ?? run.id.slice(0, 8)}</span>
              <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>{run.start_date}</span>
              <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>{run.end_date}</span>
              <span className={`num ${run.total_return != null && run.total_return >= 0 ? "pos" : "neg"}`} style={{ fontSize: 10, textAlign: "right" }}>{fmtPct(run.total_return ? run.total_return * 100 : null)}</span>
              <span className="num" style={{ fontSize: 10, textAlign: "right" }}>{fmtNum(run.sharpe_ratio)}</span>
              <span className="num neg" style={{ fontSize: 10, textAlign: "right" }}>{fmtPct(run.max_drawdown ? run.max_drawdown * 100 : null)}</span>
              <span className="num" style={{ fontSize: 10, textAlign: "right" }}>{fmtPct(run.win_rate ? run.win_rate * 100 : null, 1)}</span>
              <span style={{ fontSize: 9, textAlign: "right", fontWeight: 500, color: statusColor(run.status), textTransform: "uppercase", letterSpacing: "0.06em" }}>{run.status}</span>
            </div>
          </Link>
        ))}
        {!isLoading && data.length === 0 && <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>No runs yet. Queue one above.</div>}
      </div>
    </div>
  );
}
