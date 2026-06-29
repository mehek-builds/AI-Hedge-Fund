"use client";
import { useQuery, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, BacktestRun, BacktestTrade } from "@/lib/api";
import { SectionHeader } from "@/components/ui/section-header";
import { fmtPct, fmtNum, fmtCurrency, fmtDate, signClass } from "@/lib/format";

const qc = new QueryClient();
export default function BacktestDetailPage() {
  return <QueryClientProvider client={qc}><BacktestDetail /></QueryClientProvider>;
}

function BacktestDetail() {
  const { id } = useParams<{ id: string }>();
  const run = useQuery({ queryKey: ["backtest-run", id], queryFn: () => api.backtestRun(id) });
  const trades = useQuery({ queryKey: ["backtest-trades", id], queryFn: () => api.backtestTrades(id) });

  const r = run.data;
  const ts = trades.data ?? [];

  // Monthly returns heatmap from trades
  const monthlyMap: Record<string, number> = {};
  ts.forEach(t => {
    if (!t.exit_date || t.realized_pnl == null) return;
    const key = t.exit_date.slice(0, 7); // YYYY-MM
    monthlyMap[key] = (monthlyMap[key] ?? 0) + t.realized_pnl;
  });
  const months = Object.keys(monthlyMap).sort();

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 12px", borderBottom: "1px solid var(--color-border)" }}>
        <Link href="/dashboard/backtests" style={{ fontSize: 10, color: "var(--color-text-muted)", textDecoration: "none" }}>← Runs</Link>
        <span style={{ color: "var(--color-border-strong)" }}>/</span>
        <span style={{ fontSize: 11, color: "var(--color-text-primary)" }}>{r?.label ?? id?.slice(0, 8)}</span>
        <span style={{
          marginLeft: "auto", fontSize: 9, fontWeight: 500, textTransform: "uppercase",
          letterSpacing: "0.06em", padding: "2px 7px", borderRadius: 3,
          color: r?.status === "completed" ? "var(--color-positive)" : "var(--color-warning)",
          background: r?.status === "completed" ? "color-mix(in srgb, var(--color-positive) 12%, transparent)" : "color-mix(in srgb, var(--color-warning) 12%, transparent)",
        }}>{r?.status}</span>
      </div>

      {/* KPI row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", borderBottom: "1px solid var(--color-border)" }}>
        <KpiCell label="Total return" value={fmtPct(r?.total_return != null ? r.total_return * 100 : null)} cls={r?.total_return != null ? signClass(r.total_return) : ""} />
        <KpiCell label="Sharpe" value={fmtNum(r?.sharpe_ratio)} />
        <KpiCell label="Max drawdown" value={fmtPct(r?.max_drawdown != null ? r.max_drawdown * 100 : null)} cls="neg" />
        <KpiCell label="Win rate" value={fmtPct(r?.win_rate != null ? r.win_rate * 100 : null, 1)} />
        <KpiCell label="IR vs naive" value={fmtNum(r?.ir_vs_naive)} />
        <KpiCell label="Total trades" value={String(r?.total_trades ?? "--")} />
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Monthly heatmap */}
        <div style={{ width: 280, borderRight: "1px solid var(--color-border)", display: "flex", flexDirection: "column" }}>
          <SectionHeader title="Monthly P&L" right={`${months.length} months`} />
          <div style={{ flex: 1, overflowY: "auto", padding: 8 }}>
            {months.length === 0 && <div style={{ padding: 8, fontSize: 11, color: "var(--color-text-muted)" }}>No completed trades.</div>}
            {months.map(m => {
              const pnl = monthlyMap[m];
              const maxAbs = Math.max(...Object.values(monthlyMap).map(Math.abs), 1);
              const intensity = Math.min(Math.abs(pnl) / maxAbs, 1);
              const bg = pnl >= 0
                ? `color-mix(in srgb, var(--color-positive) ${Math.round(intensity * 35 + 5)}%, var(--color-bg-card))`
                : `color-mix(in srgb, var(--color-negative) ${Math.round(intensity * 35 + 5)}%, var(--color-bg-card))`;
              return (
                <div key={m} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "5px 8px", marginBottom: 2, borderRadius: 3, background: bg,
                }}>
                  <span className="num" style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{m}</span>
                  <span className={`num ${pnl >= 0 ? "pos" : "neg"}`} style={{ fontSize: 11, fontWeight: 500 }}>
                    {fmtCurrency(pnl, 0)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Trade log */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <SectionHeader title="Trade log" right={`${ts.length} trades`} />
          <div style={{ display: "grid", gridTemplateColumns: "52px 60px 80px 70px 70px 70px 60px 1fr", padding: "3px 12px", borderBottom: "1px solid var(--color-border)" }}>
            {["Ticker","Dir","Entry","Exit","P&L","FF5α","Days","Exit reason"].map((h, i) => (
              <span key={h} style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", textAlign: i > 1 && i < 7 ? "right" : "left" }}>{h}</span>
            ))}
          </div>
          <div style={{ flex: 1, overflowY: "auto" }}>
            {trades.isLoading && <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>Loading...</div>}
            {ts.map(t => (
              <div key={t.id} style={{ display: "grid", gridTemplateColumns: "52px 60px 80px 70px 70px 70px 60px 1fr", padding: "4px 12px", borderBottom: "1px solid var(--color-border)", alignItems: "center" }}>
                <span className="num" style={{ fontWeight: 600, fontSize: 11 }}>{t.ticker}</span>
                <span style={{ fontSize: 9, color: t.direction === "long" ? "var(--color-positive)" : "var(--color-negative)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{t.direction}</span>
                <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>{fmtDate(t.entry_date)}</span>
                <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>{fmtDate(t.exit_date)}</span>
                <span className={`num ${signClass(t.realized_pnl)}`} style={{ fontSize: 10, textAlign: "right" }}>{fmtCurrency(t.realized_pnl, 0)}</span>
                <span className={`num ${signClass(t.ff5_alpha)}`} style={{ fontSize: 10, textAlign: "right" }}>{fmtNum(t.ff5_alpha, 3)}</span>
                <span className="num muted" style={{ fontSize: 10, textAlign: "right" }}>{t.hold_days ?? "--"}</span>
                <span style={{ fontSize: 10, color: "var(--color-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.exit_reason ?? "--"}</span>
              </div>
            ))}
            {!trades.isLoading && ts.length === 0 && <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>No trades.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function KpiCell({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div style={{ padding: "8px 12px", borderRight: "1px solid var(--color-border)" }}>
      <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--color-text-muted)", marginBottom: 2 }}>{label}</div>
      <div className={`num ${cls ?? ""}`} style={{ fontSize: 15, fontWeight: 500 }}>{value}</div>
    </div>
  );
}
