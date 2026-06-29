"use client";
import { useQuery } from "@tanstack/react-query";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { useState, useCallback } from "react";
import { api, DashboardSummary, Signal, Position, RecentAlert } from "@/lib/api";
import { useSSE } from "@/lib/sse";
import { SectionHeader } from "@/components/ui/section-header";
import { ThesisBadge } from "@/components/ui/thesis-badge";
import { GateBadge } from "@/components/ui/gate-badge";
import { fmtCurrency, fmtPct, fmtSigned, fmtNum, fmtDatetime, signClass } from "@/lib/format";
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } });

export default function DashboardPage() {
  return (
    <QueryClientProvider client={qc}>
      <Dashboard />
    </QueryClientProvider>
  );
}

function Dashboard() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.dashboardSummary, refetchInterval: 15_000 });
  const signals = useQuery({ queryKey: ["signals"], queryFn: api.signals, refetchInterval: 30_000 });
  const positions = useQuery({ queryKey: ["positions"], queryFn: api.positions, refetchInterval: 15_000 });
  const recentAlerts = useQuery({ queryKey: ["recent-alerts"], queryFn: api.recentAlerts, refetchInterval: 15_000 });
  const macro = useQuery({ queryKey: ["macro"], queryFn: api.macroRegime, refetchInterval: 60_000 });
  const macroHistory = useQuery({ queryKey: ["macro-history"], queryFn: () => api.macroHistory(30), refetchInterval: 300_000 });

  // SSE live updates
  const handleSSE = useCallback(() => {
    summary.refetch();
    signals.refetch();
    positions.refetch();
  }, [summary, signals, positions]);
  useSSE("/stream", { onMessage: handleSSE });

  const s = summary.data;
  const sigs = signals.data ?? [];
  const pos = positions.data ?? [];
  const alerts = recentAlerts.data ?? [];
  const macroData = macro.data;
  const navChart = (macroHistory.data ?? []).map(p => ({
    date: p.time.slice(5, 10),
    score: p.composite_score,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Stat row */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(5, 1fr)",
        borderBottom: "1px solid var(--color-border)",
        flexShrink: 0,
      }}>
        <StatCell label="NAV" value={fmtCurrency(s?.nav)} sub="Alpaca paper" />
        <StatCell label="Daily P&L" value={fmtPct(s?.daily_pnl_pct)} valueClass={signClass(s?.daily_pnl_pct)} sub={s?.daily_pnl != null ? fmtCurrency(s.daily_pnl) : "--"} />
        <StatCell label="Open positions" value={String(s?.open_positions ?? "--")} sub="active" />
        <StatCell
          label="Macro gate"
          value={s?.macro_regime ?? "--"}
          sub={`${s?.size_multiplier != null ? s.size_multiplier.toFixed(1) : "--"}× · ERP ${s?.erp_compressed ? "compressed" : "clear"}`}
          valueEl={s?.macro_regime ? <GateBadge regime={s.macro_regime} /> : undefined}
        />
        <StatCell label="Alpha t-stat" value={fmtNum(s?.alpha_tstat)} sub="24-mo rolling" valueClass={s?.alpha_tstat != null && s.alpha_tstat >= 2 ? "pos" : "warn"} />
      </div>

      {/* 3-column body */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden", minHeight: 0 }}>

        {/* Left — Signal feed */}
        <div style={{ width: 180, borderRight: "1px solid var(--color-border)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <SectionHeader title="Signal feed" right={`${sigs.length} recent`} />
          <div style={{ fontSize: 9, display: "flex", gap: 0, padding: "3px 10px", borderBottom: "1px solid var(--color-border)" }}>
            <span style={{ color: "var(--color-amber)", fontWeight: 500 }}>All</span>
            <span style={{ color: "var(--color-text-muted)", marginLeft: 8 }}>High</span>
            <span style={{ color: "var(--color-text-muted)", marginLeft: 8 }}>New</span>
          </div>
          <div style={{ flex: 1, overflowY: "auto" }}>
            {sigs.slice(0, 15).map(sig => (
              <SignalTile key={sig.id} sig={sig} />
            ))}
            {sigs.length === 0 && <Empty label="No signals" />}
          </div>
        </div>

        {/* Center — NAV chart + positions */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
          <SectionHeader title="NAV performance" right="30d" />
          <div style={{ padding: "10px 12px 4px", flexShrink: 0, height: 120 }}>
            {navChart.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={navChart} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                  <defs>
                    <linearGradient id="navGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22C55E" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="#22C55E" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ background: "var(--color-bg-panel)", border: "1px solid var(--color-border)", borderRadius: 4, fontSize: 11 }}
                    labelStyle={{ color: "var(--color-text-secondary)" }}
                    itemStyle={{ color: "var(--color-positive)" }}
                  />
                  <Area type="monotone" dataKey="score" stroke="#22C55E" strokeWidth={1.5} fill="url(#navGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Empty label="No history yet" />
              </div>
            )}
          </div>

          <SectionHeader title="Open positions" right={`${pos.length} active`} />
          <div style={{ display: "grid", gridTemplateColumns: "48px 1fr 60px 56px 52px", gap: 0, padding: "3px 10px", borderBottom: "1px solid var(--color-border)" }}>
            {["Ticker","Thesis","P&L","Size","Days"].map(h => (
              <span key={h} style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", textAlign: h !== "Ticker" && h !== "Thesis" ? "right" : "left" }}>{h}</span>
            ))}
          </div>
          <div style={{ flex: 1, overflowY: "auto" }}>
            {pos.map(p => <PositionRow key={p.id} pos={p} />)}
            {pos.length === 0 && <Empty label="No open positions" />}
          </div>
        </div>

        {/* Right — Macro + alerts */}
        <div style={{ width: 180, borderLeft: "1px solid var(--color-border)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <SectionHeader title="Macro state" />
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 1fr",
            borderBottom: "1px solid var(--color-border)",
          }}>
            <KpiMini label="Score" value={String(macroData?.composite_score ?? "--")} />
            <KpiMini label="Mult" value={macroData?.size_multiplier != null ? `${macroData.size_multiplier.toFixed(1)}×` : "--"} valueClass={macroData?.size_multiplier === 1.0 ? "pos" : "warn"} borderRight={false} />
            <KpiMini label="ERP" value={macroData?.components?.erp_spread != null ? fmtSigned(macroData.components.erp_spread as number) : "--"} borderTop />
            <KpiMini label="Halted" value={macroData?.is_halted ? "YES" : "NO"} valueClass={macroData?.is_halted ? "neg" : "pos"} borderRight={false} borderTop />
          </div>

          {macroData && Object.entries(macroData.components).slice(0, 6).map(([k, v]) => (
            <MacroRow key={k} label={fmtMacroKey(k)} value={String(v ?? "--")} />
          ))}

          <SectionHeader title="Recent alerts" right="last 5" />
          <div style={{ flex: 1, overflowY: "auto" }}>
            {alerts.map(a => <AlertRow key={a.id} alert={a} />)}
            {alerts.length === 0 && <Empty label="No alerts" />}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

function StatCell({ label, value, sub, valueClass, valueEl }: {
  label: string; value: string; sub?: string; valueClass?: string; valueEl?: React.ReactNode;
}) {
  return (
    <div style={{ padding: "7px 12px", borderRight: "1px solid var(--color-border)" }}>
      <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--color-text-muted)", marginBottom: 2 }}>{label}</div>
      {valueEl ?? (
        <div className={`num ${valueClass ?? ""}`} style={{ fontSize: 15, fontWeight: 500 }}>{value}</div>
      )}
      {sub && <div className="num" style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 1 }}>{sub}</div>}
    </div>
  );
}

function SignalTile({ sig }: { sig: Signal }) {
  const composite = sig.signal_composite ?? 0;
  const cls = composite >= 0.8 ? "pos" : composite >= 0.5 ? "warn" : "muted";
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "42px 1fr auto",
      alignItems: "center", gap: 6, padding: "5px 10px",
      borderBottom: "1px solid var(--color-border)",
      cursor: "pointer",
    }}>
      <span className="num" style={{ fontSize: 11, fontWeight: 500, color: "var(--color-text-primary)" }}>{sig.ticker}</span>
      <div>
        <div className="num muted" style={{ fontSize: 9 }}>
          gap {sig.eps_gap_sigma != null ? fmtSigned(sig.eps_gap_sigma) : "--"}σ
        </div>
        <div className="num muted" style={{ fontSize: 9 }}>
          qual {fmtNum(sig.quality_score)}
        </div>
      </div>
      <span className={`num ${cls}`} style={{ fontSize: 11, fontWeight: 500 }}>
        {fmtNum(composite)}
      </span>
    </div>
  );
}

function PositionRow({ pos }: { pos: Position }) {
  const pnlPct = pos.entry_price && pos.current_price
    ? ((pos.current_price - pos.entry_price) / pos.entry_price) * 100
    : null;
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "48px 1fr 60px 56px 52px",
      alignItems: "center", gap: 0, padding: "4px 10px",
      borderBottom: "1px solid var(--color-border)",
    }}>
      <span className="num" style={{ fontSize: 10, fontWeight: 500 }}>{pos.ticker}</span>
      <ThesisBadge status={pos.thesis_status} />
      <span className={`num ${signClass(pnlPct)}`} style={{ fontSize: 10, textAlign: "right" }}>
        {fmtPct(pnlPct)}
      </span>
      <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>
        {pos.nav_weight != null ? fmtPct(pos.nav_weight * 100, 1) : "--"}
      </span>
      <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>
        {pos.days_held ?? "--"}d
      </span>
    </div>
  );
}

function KpiMini({ label, value, valueClass, borderRight = true, borderTop = false }: {
  label: string; value: string; valueClass?: string; borderRight?: boolean; borderTop?: boolean;
}) {
  return (
    <div style={{
      padding: "7px 10px",
      borderRight: borderRight ? "1px solid var(--color-border)" : "none",
      borderTop: borderTop ? "1px solid var(--color-border)" : "none",
    }}>
      <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-text-muted)" }}>{label}</div>
      <div className={`num ${valueClass ?? ""}`} style={{ fontSize: 13, fontWeight: 500 }}>{value}</div>
    </div>
  );
}

function MacroRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "4px 10px", borderBottom: "1px solid var(--color-border)",
    }}>
      <span style={{ fontSize: 10, color: "var(--color-text-secondary)" }}>{label}</span>
      <span className="num" style={{ fontSize: 10, color: "var(--color-text-primary)" }}>{value}</span>
    </div>
  );
}

function AlertRow({ alert }: { alert: RecentAlert }) {
  const dot =
    alert.priority === "high" ? "var(--color-negative)" :
    alert.priority === "medium" ? "var(--color-warning)" : "var(--color-positive)";
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 6, padding: "5px 10px", borderBottom: "1px solid var(--color-border)" }}>
      <div style={{ width: 5, height: 5, borderRadius: "50%", background: dot, flexShrink: 0, marginTop: 3 }} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 10, color: "var(--color-text-secondary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {alert.title}
        </div>
        <div className="num muted" style={{ fontSize: 9 }}>{fmtDatetime(alert.created_at)} · {alert.event_type}</div>
      </div>
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div style={{ padding: "12px 10px", fontSize: 11, color: "var(--color-text-muted)", textAlign: "center" }}>
      {label}
    </div>
  );
}

function fmtMacroKey(k: string) {
  return k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}
