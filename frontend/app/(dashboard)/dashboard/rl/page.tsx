"use client";
import { useQuery, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api, RLEpisode, RLMetrics } from "@/lib/api";
import { SectionHeader } from "@/components/ui/section-header";
import { fmtNum, fmtDatetime } from "@/lib/format";
import {
  LineChart, Line, XAxis, YAxis, ResponsiveContainer,
  Tooltip, ReferenceLine, CartesianGrid,
} from "recharts";

const qc = new QueryClient();
export default function RLPage() {
  return <QueryClientProvider client={qc}><RLConsole /></QueryClientProvider>;
}

function RLConsole() {
  const episodes = useQuery({ queryKey: ["rl-episodes"], queryFn: api.rlEpisodes, refetchInterval: 60_000 });
  const metrics = useQuery({ queryKey: ["rl-metrics"], queryFn: api.rlFactors, refetchInterval: 60_000 });

  const eps = episodes.data ?? [];
  const m = metrics.data;

  // Batch rewards into 20-episode rolling average for the chart
  const chartData = eps.map((e, i) => {
    const window = eps.slice(Math.max(0, i - 19), i + 1);
    const avg = window.reduce((s, ep) => s + ep.reward, 0) / window.length;
    return { episode: i + 1, reward: e.reward, avg };
  });

  const factorBetas = m?.factor_betas ?? {};

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <SectionHeader title="RL console" right={m ? `${m.episode_count} episodes` : ""} />

      {/* Summary stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", borderBottom: "1px solid var(--color-border)" }}>
        <StatCell label="Episodes" value={String(m?.episode_count ?? "--")} />
        <StatCell label="Mean reward (20)" value={fmtNum(m?.mean_reward_20)} valueClass={m?.mean_reward_20 != null && m.mean_reward_20 >= 0 ? "pos" : "neg"} />
        <StatCell label="Last trained" value={m?.last_trained_at ? fmtDatetime(m.last_trained_at) : "--"} />
        <StatCell label="FF5 betas" value={Object.keys(factorBetas).length > 0 ? "loaded" : "n/a"} />
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Reward curve */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", borderRight: "1px solid var(--color-border)" }}>
          <SectionHeader title="Reward curve (20-ep rolling avg)" />
          <div style={{ flex: 1, padding: "10px 8px 8px" }}>
            {chartData.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                  <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                  <XAxis dataKey="episode" tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} tickLine={false} axisLine={false} />
                  <ReferenceLine y={0} stroke="var(--color-border-strong)" />
                  <Tooltip
                    contentStyle={{ background: "var(--color-bg-panel)", border: "1px solid var(--color-border)", borderRadius: 4, fontSize: 11 }}
                    labelStyle={{ color: "var(--color-text-secondary)" }}
                  />
                  <Line type="monotone" dataKey="reward" stroke="var(--color-text-muted)" strokeWidth={1} dot={false} name="Reward" />
                  <Line type="monotone" dataKey="avg" stroke="var(--color-accent)" strokeWidth={1.5} dot={false} name="20-ep avg" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--color-text-muted)", fontSize: 11 }}>
                {episodes.isLoading ? "Loading..." : "No episode data yet."}
              </div>
            )}
          </div>
        </div>

        {/* Factor betas */}
        <div style={{ width: 220, display: "flex", flexDirection: "column" }}>
          <SectionHeader title="FF5 factor betas" />
          {Object.entries(factorBetas).map(([factor, beta]) => (
            <div key={factor} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 12px", borderBottom: "1px solid var(--color-border)" }}>
              <span style={{ fontSize: 11, color: "var(--color-text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{factor}</span>
              <span className={`num ${Math.abs(beta) > 0.1 ? (beta > 0 ? "pos" : "neg") : "muted"}`} style={{ fontSize: 11, fontWeight: 500 }}>
                {beta > 0 ? "+" : ""}{beta.toFixed(3)}
              </span>
            </div>
          ))}
          {Object.keys(factorBetas).length === 0 && (
            <div style={{ padding: 12, fontSize: 11, color: "var(--color-text-muted)" }}>No checkpoint loaded.</div>
          )}

          <SectionHeader title="Recent episodes" right="last 10" />
          <div style={{ flex: 1, overflowY: "auto" }}>
            {eps.slice(-10).reverse().map((e, i) => (
              <div key={e.id} style={{ display: "flex", justifyContent: "space-between", padding: "4px 12px", borderBottom: "1px solid var(--color-border)" }}>
                <span className="num muted" style={{ fontSize: 10 }}>ep {eps.length - i}</span>
                <span className={`num ${e.reward >= 0 ? "pos" : "neg"}`} style={{ fontSize: 10, fontWeight: 500 }}>
                  {e.reward >= 0 ? "+" : ""}{e.reward.toFixed(3)}
                </span>
              </div>
            ))}
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
      <div className={`num ${valueClass ?? ""}`} style={{ fontSize: 14, fontWeight: 500 }}>{value}</div>
    </div>
  );
}
