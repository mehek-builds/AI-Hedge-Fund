"use client";
import { useQuery, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api, MacroRegime, MacroHistoryPoint } from "@/lib/api";
import { SectionHeader } from "@/components/ui/section-header";
import { GateBadge } from "@/components/ui/gate-badge";
import { fmtNum, fmtDatetime } from "@/lib/format";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, CartesianGrid, Tooltip, ReferenceLine } from "recharts";

const qc = new QueryClient();
export default function MacroPage() {
  return <QueryClientProvider client={qc}><MacroState /></QueryClientProvider>;
}

function MacroState() {
  const regime = useQuery({ queryKey: ["macro-regime"], queryFn: api.macroRegime, refetchInterval: 60_000 });
  const history = useQuery({ queryKey: ["macro-history-90"], queryFn: () => api.macroHistory(90), refetchInterval: 300_000 });

  const r = regime.data;
  const regimeLabel = r
    ? (r.composite_score >= -1 ? "Expansion" : r.composite_score >= -3 ? "Caution" : "Crisis")
    : null;

  const chartData = (history.data ?? []).map(p => ({
    date: p.time.slice(5, 10),
    score: p.composite_score,
    mult: p.size_multiplier,
  }));

  const components: Array<{ key: string; label: string; description: string }> = [
    { key: "t10y2y", label: "Yield curve (10Y-2Y)", description: "Inverted = caution" },
    { key: "core_pce_yoy", label: "Core PCE YoY", description: "Inflation pressure" },
    { key: "gdp_qoq_ann", label: "GDP QoQ (ann.)", description: "Growth momentum" },
    { key: "hy_oas", label: "HY OAS", description: "Credit spreads" },
    { key: "vix", label: "VIX", description: "Volatility regime" },
    { key: "sahm_rule", label: "Sahm Rule", description: ">0.5 = recession signal" },
    { key: "carry_crash_flag", label: "Carry crash flag", description: "JPY/AUD carry unwind" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <SectionHeader title="Macro state" right={r ? fmtDatetime(r.time) : ""} />

      {/* Regime summary */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", borderBottom: "1px solid var(--color-border)" }}>
        <div style={{ padding: "8px 12px", borderRight: "1px solid var(--color-border)" }}>
          <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--color-text-muted)", marginBottom: 4 }}>Regime</div>
          {regimeLabel && <GateBadge regime={regimeLabel} />}
        </div>
        <StatCell label="Composite score" value={String(r?.composite_score ?? "--")} />
        <StatCell label="Size multiplier" value={r?.size_multiplier != null ? `${r.size_multiplier.toFixed(1)}×` : "--"} valueClass={r?.size_multiplier === 1.0 ? "pos" : r?.size_multiplier === 0 ? "neg" : "warn"} />
        <StatCell label="Trading halted" value={r?.is_halted ? "YES" : "NO"} valueClass={r?.is_halted ? "neg" : "pos"} />
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left: component details */}
        <div style={{ width: 280, borderRight: "1px solid var(--color-border)", overflowY: "auto" }}>
          <SectionHeader title="Components" />
          {components.map(c => {
            const val = r?.components?.[c.key];
            return (
              <div key={c.key} style={{ padding: "8px 12px", borderBottom: "1px solid var(--color-border)" }}>
                <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 11, color: "var(--color-text-primary)" }}>{c.label}</span>
                  <span className="num" style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-primary)" }}>
                    {val === true ? "YES" : val === false ? "NO" : val != null ? fmtNum(val as number, 3) : "--"}
                  </span>
                </div>
                <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 1 }}>{c.description}</div>
              </div>
            );
          })}
        </div>

        {/* Right: composite score history + size multiplier */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <SectionHeader title="Composite score — 90d" />
          <div style={{ height: 200, padding: "10px 8px 8px", borderBottom: "1px solid var(--color-border)" }}>
            {chartData.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                  <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} domain={[-6, 0]} />
                  <ReferenceLine y={-1} stroke="var(--color-warning)" strokeDasharray="4 2" label={{ value: "Caution", fill: "var(--color-warning)", fontSize: 9, position: "right" }} />
                  <ReferenceLine y={-3} stroke="var(--color-negative)" strokeDasharray="4 2" label={{ value: "Crisis", fill: "var(--color-negative)", fontSize: 9, position: "right" }} />
                  <Tooltip contentStyle={{ background: "var(--color-bg-panel)", border: "1px solid var(--color-border)", borderRadius: 4, fontSize: 11 }} />
                  <Line type="monotone" dataKey="score" stroke="var(--color-accent)" strokeWidth={1.5} dot={false} name="Score" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--color-text-muted)", fontSize: 11 }}>
                {history.isLoading ? "Loading..." : "No history yet."}
              </div>
            )}
          </div>

          <SectionHeader title="Size multiplier — 90d" />
          <div style={{ flex: 1, padding: "10px 8px 8px" }}>
            {chartData.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                  <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} domain={[0, 1.1]} />
                  <Tooltip contentStyle={{ background: "var(--color-bg-panel)", border: "1px solid var(--color-border)", borderRadius: 4, fontSize: 11 }} />
                  <Line type="monotone" dataKey="mult" stroke="var(--color-positive)" strokeWidth={1.5} dot={false} name="Multiplier" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--color-text-muted)", fontSize: 11 }}>No data.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCell({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div style={{ padding: "8px 12px", borderRight: "1px solid var(--color-border)" }}>
      <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--color-text-muted)", marginBottom: 2 }}>{label}</div>
      <div className={`num ${valueClass ?? ""}`} style={{ fontSize: 15, fontWeight: 500 }}>{value}</div>
    </div>
  );
}
