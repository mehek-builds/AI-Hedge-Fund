"use client";

import React, { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useSSE } from "@/src/hooks/useSSE";
import {
  RLStateData,
  SSERLStateUpdatePayload,
} from "@/src/types/api";
import PageHeader from "@/src/components/PageHeader";
import LoadingSkeleton from "@/src/components/LoadingSkeleton";

const AGENT_COLORS = ["#2471A3", "#27AE60", "#E67E22", "#9B59B6", "#1ABC9C"];
const MAX_HISTORY = 500;

interface Props {
  initialData: RLStateData | null;
}

interface StepPoint {
  step: number;
  [key: string]: number;
}

function buildChartData(agents: RLStateData["agents"]): StepPoint[] {
  const map = new Map<number, StepPoint>();

  agents.forEach((agent) => {
    agent.reward_history.forEach(({ step, reward }) => {
      if (!map.has(step)) {
        map.set(step, { step });
      }
      const point = map.get(step)!;
      point[`agent_${agent.agent_id}`] = reward;
    });
  });

  return Array.from(map.values()).sort((a, b) => a.step - b.step);
}

export default function RLConsoleClient({ initialData }: Props) {
  const [data, setData] = useState<RLStateData | null>(initialData);
  const { lastEvent } = useSSE();

  useEffect(() => {
    if (!lastEvent || lastEvent.name !== "rl_state") return;

    const event = lastEvent.payload as SSERLStateUpdatePayload;
    if (!event || event.event !== "rl_state_update") return;

    setData((prev) => {
      if (!prev) return prev;

      const updatedAgents = [...prev.agents];
      const agentIdx = updatedAgents.findIndex(
        (a) => a.agent_id === event.agent_id
      );

      if (agentIdx >= 0) {
        const agent = { ...updatedAgents[agentIdx] };
        const history = [
          ...agent.reward_history,
          { step: event.step, reward: event.reward },
        ];
        agent.reward_history =
          history.length > MAX_HISTORY
            ? history.slice(history.length - MAX_HISTORY)
            : history;
        agent.latest_reward = event.reward;
        updatedAgents[agentIdx] = agent;
      } else {
        updatedAgents.push({
          agent_id: event.agent_id,
          reward_history: [{ step: event.step, reward: event.reward }],
          latest_reward: event.reward,
        });
      }

      return {
        ...prev,
        agents: updatedAgents,
        regime_weights: event.regime_weights,
      };
    });
  }, [lastEvent]);

  const isEmpty = !data || data.agents.length === 0;
  const chartData = isEmpty ? [] : buildChartData(data.agents);

  const regimeData = [
    {
      regime: "Expansion",
      weight: data?.regime_weights.expansion ?? 0,
      color: "#27AE60",
    },
    {
      regime: "Caution",
      weight: data?.regime_weights.caution ?? 0,
      color: "#E67E22",
    },
    {
      regime: "Crisis",
      weight: data?.regime_weights.crisis ?? 0,
      color: "#E74C3C",
    },
  ];

  const cardStyle: React.CSSProperties = {
    backgroundColor: "#0F2040",
    borderRadius: "8px",
    padding: "24px",
    border: "1px solid #1A3050",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: "14px",
    fontWeight: 500,
    color: "#6B8EAD",
    marginBottom: "16px",
    display: "block",
  };

  return (
    <div>
      <PageHeader title="RL Console" subtitle="SAC ensemble training monitor" />
      <div style={{ padding: "24px 32px" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "65fr 35fr",
            gap: "24px",
          }}
        >
          {/* Left panel: Reward Curves */}
          <div style={cardStyle}>
            <span style={labelStyle}>Agent Reward Curves</span>
            {isEmpty ? (
              <div>
                <LoadingSkeleton width="100%" height="320px" />
                <p
                  style={{
                    color: "#6B8EAD",
                    fontSize: "14px",
                    padding: "16px 0 0",
                    margin: 0,
                  }}
                >
                  No training data. Reward curves appear after the SAC ensemble
                  completes at least one training epoch.
                </p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                <LineChart
                  data={chartData}
                  margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1A3050" />
                  <XAxis
                    dataKey="step"
                    tick={{ fill: "#6B8EAD", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={(v: number) => v.toFixed(2)}
                    tick={{ fill: "#6B8EAD", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0F2040",
                      border: "1px solid #2471A3",
                    }}
                    labelStyle={{ color: "#6B8EAD", fontSize: 12 }}
                    itemStyle={{
                      fontFamily: "JetBrains Mono",
                      fontSize: 12,
                    }}
                  />
                  <Legend
                    wrapperStyle={{ color: "#6B8EAD", fontSize: 12 }}
                  />
                  {AGENT_COLORS.map((color, idx) => (
                    <Line
                      key={idx}
                      type="monotone"
                      dataKey={`agent_${idx}`}
                      stroke={color}
                      strokeWidth={2}
                      dot={false}
                      name={`Agent ${idx}`}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Right panel: Regime Weights */}
          <div style={cardStyle}>
            <span style={labelStyle}>MoE Regime Weights</span>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                layout="vertical"
                data={regimeData}
                margin={{ top: 5, right: 20, bottom: 5, left: 70 }}
              >
                <XAxis
                  type="number"
                  domain={[0, 1]}
                  tick={{ fill: "#6B8EAD", fontSize: 11 }}
                  tickFormatter={(v: number) =>
                    `${(v * 100).toFixed(0)}%`
                  }
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="regime"
                  tick={{
                    fill: "#6B8EAD",
                    fontSize: 12,
                  }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  formatter={(value: number) =>
                    `${(value * 100).toFixed(1)}%`
                  }
                  contentStyle={{
                    backgroundColor: "#0F2040",
                    border: "1px solid #2471A3",
                  }}
                />
                <Bar dataKey="weight" radius={[0, 4, 4, 0]}>
                  {regimeData.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            {/* Weight values */}
            <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "8px" }}>
              {regimeData.map((r) => (
                <div
                  key={r.regime}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span style={{ color: "#6B8EAD", fontSize: "13px" }}>
                    {r.regime}
                  </span>
                  <span
                    className="mono"
                    style={{ color: r.color, fontSize: "13px" }}
                  >
                    {(r.weight * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>

            {data && (
              <p
                style={{
                  color: "#6B8EAD",
                  fontSize: "11px",
                  marginTop: "16px",
                  marginBottom: 0,
                }}
              >
                Checkpoint step:{" "}
                <span className="mono">{data.last_checkpoint_step}</span>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
