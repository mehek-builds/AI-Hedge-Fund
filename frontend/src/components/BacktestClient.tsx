"use client";

import React, { useState, useEffect } from "react";
import { BacktestRunSummary, BacktestRunDetail } from "@/src/types/api";
import PageHeader from "@/src/components/PageHeader";
import KPICard from "@/src/components/KPICard";
import LoadingSkeleton from "@/src/components/LoadingSkeleton";
import LoadingSpinner from "@/src/components/LoadingSpinner";
import MonthlyReturnsHeatmap from "@/src/components/MonthlyReturnsHeatmap";

interface Props {
  initialRuns: BacktestRunSummary[];
}

function gateColor(status: string): string {
  const s = status.toLowerCase();
  if (s === "pass") return "#27AE60";
  if (s === "fail") return "#E74C3C";
  return "#6B8EAD";
}

function sharpeColor(v: number | null): string {
  if (v === null) return "white";
  if (v >= 1.0) return "#27AE60";
  if (v >= 0.5) return "#E67E22";
  return "#E74C3C";
}

function irColor(v: number | null): string {
  if (v === null) return "white";
  return v > 0 ? "#27AE60" : "#E74C3C";
}

export default function BacktestClient({ initialRuns }: Props) {
  const [runs] = useState<BacktestRunSummary[]>(initialRuns);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<BacktestRunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [configExpanded, setConfigExpanded] = useState(false);

  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null);
      return;
    }

    let cancelled = false;
    setLoading(true);

    fetch(`/api/v1/backtest/runs/${selectedRunId}`)
      .then((r) => r.json())
      .then((data: BacktestRunDetail) => {
        if (!cancelled) {
          setSelectedRun(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedRunId]);

  const selectStyle: React.CSSProperties = {
    backgroundColor: "#0F2040",
    border: "1px solid #2471A3",
    color: "white",
    fontFamily: "Inter, system-ui, sans-serif",
    fontSize: "14px",
    borderRadius: "6px",
    padding: "8px 12px",
    width: "100%",
    cursor: "pointer",
    appearance: "none",
    WebkitAppearance: "none",
    outline: "none",
  };

  return (
    <div>
      <PageHeader title="Backtest Explorer" />
      <div style={{ padding: "24px 32px" }}>
        {runs.length === 0 ? (
          <p
            style={{
              color: "#6B8EAD",
              fontSize: "14px",
              padding: "48px",
              textAlign: "center",
              margin: 0,
            }}
          >
            No backtest runs found. Run the Phase 6 backtest engine to
            populate this view.
          </p>
        ) : (
          <>
            {/* Run Selector */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                marginBottom: "24px",
              }}
            >
              <div style={{ flex: 1, position: "relative" }}>
                <select
                  value={selectedRunId ?? ""}
                  onChange={(e) =>
                    setSelectedRunId(e.target.value || null)
                  }
                  disabled={loading}
                  style={{
                    ...selectStyle,
                    opacity: loading ? 0.6 : 1,
                  }}
                >
                  <option value="" disabled>
                    Select a backtest run...
                  </option>
                  {runs.map((run) => (
                    <option key={run.id} value={run.id}>
                      {run.start_date} - {run.end_date} ({run.slice_type}){" "}
                      &mdash; Gate: {run.gate_status}
                    </option>
                  ))}
                </select>
              </div>
              {loading && <LoadingSpinner />}
            </div>

            {/* Gate Status */}
            {selectedRun && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  marginBottom: "24px",
                }}
              >
                <span style={{ color: "#6B8EAD", fontSize: "13px" }}>
                  Gate Status:
                </span>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    padding: "2px 10px",
                    borderRadius: "4px",
                    fontSize: "11px",
                    fontWeight: 600,
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    backgroundColor: `${gateColor(selectedRun.gate_status)}22`,
                    color: gateColor(selectedRun.gate_status),
                    border: `1px solid ${gateColor(selectedRun.gate_status)}55`,
                    fontFamily: "JetBrains Mono, monospace",
                  }}
                >
                  {selectedRun.gate_status.toUpperCase()}
                </span>
                {selectedRun.gate_reason && (
                  <span style={{ color: "#6B8EAD", fontSize: "12px" }}>
                    — {selectedRun.gate_reason}
                  </span>
                )}
              </div>
            )}

            {/* Stats Grid (2x2) */}
            {(selectedRun || loading) && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "24px",
                  marginBottom: "0",
                }}
              >
                {loading ? (
                  <>
                    <LoadingSkeleton width="100%" height="120px" borderRadius="8px" />
                    <LoadingSkeleton width="100%" height="120px" borderRadius="8px" />
                    <LoadingSkeleton width="100%" height="120px" borderRadius="8px" />
                    <LoadingSkeleton width="100%" height="120px" borderRadius="8px" />
                  </>
                ) : selectedRun ? (
                  <>
                    <KPICard
                      label="Sharpe Ratio"
                      value={selectedRun.sharpe?.toFixed(4) ?? "-"}
                      positive={
                        selectedRun.sharpe !== null &&
                        selectedRun.sharpe >= 1.0
                      }
                      negative={
                        selectedRun.sharpe !== null &&
                        selectedRun.sharpe < 0.5
                      }
                    />
                    <KPICard
                      label="Max Drawdown"
                      value={
                        selectedRun.max_drawdown != null
                          ? `${(selectedRun.max_drawdown * 100).toFixed(2)}%`
                          : "-"
                      }
                      negative
                    />
                    <KPICard
                      label="IR vs Baseline"
                      value={selectedRun.ir_vs_baseline?.toFixed(4) ?? "-"}
                      positive={
                        selectedRun.ir_vs_baseline !== null &&
                        selectedRun.ir_vs_baseline > 0
                      }
                      negative={
                        selectedRun.ir_vs_baseline !== null &&
                        selectedRun.ir_vs_baseline <= 0
                      }
                    />
                    <KPICard
                      label="Calmar Ratio"
                      value={selectedRun.calmar?.toFixed(4) ?? "-"}
                      positive={
                        selectedRun.calmar !== null &&
                        selectedRun.calmar >= 1.0
                      }
                      negative={
                        selectedRun.calmar !== null &&
                        selectedRun.calmar < 0.5
                      }
                    />
                  </>
                ) : null}
              </div>
            )}

            {/* Monthly Returns Heatmap */}
            {selectedRun && !loading && (
              <MonthlyReturnsHeatmap
                monthlyReturns={selectedRun.monthly_returns}
              />
            )}

            {/* Config Snapshot (collapsible) */}
            {selectedRun && !loading && (
              <div
                style={{
                  backgroundColor: "#0F2040",
                  border: "1px solid #1A3050",
                  borderRadius: "8px",
                  padding: "16px 20px",
                  marginTop: "24px",
                }}
              >
                <button
                  onClick={() => setConfigExpanded((v) => !v)}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    color: "#6B8EAD",
                    fontSize: "14px",
                    fontWeight: 500,
                    padding: 0,
                    width: "100%",
                    textAlign: "left",
                  }}
                >
                  <span
                    style={{
                      transform: configExpanded ? "rotate(90deg)" : "rotate(0deg)",
                      display: "inline-block",
                      transition: "transform 0.15s",
                      fontSize: "12px",
                    }}
                  >
                    {"▶"}
                  </span>
                  Config Snapshot
                </button>

                {configExpanded && (
                  <pre
                    style={{
                      fontFamily: "JetBrains Mono, monospace",
                      fontSize: "12px",
                      backgroundColor: "#060E1A",
                      border: "1px solid #1A3050",
                      borderRadius: "6px",
                      padding: "16px",
                      overflow: "auto",
                      color: "#6B8EAD",
                      marginTop: "12px",
                      marginBottom: 0,
                    }}
                  >
                    {JSON.stringify(selectedRun?.config_snapshot, null, 2)}
                  </pre>
                )}
              </div>
            )}

            {/* No run selected — prompt */}
            {!selectedRunId && runs.length > 0 && (
              <p
                style={{
                  color: "#6B8EAD",
                  fontSize: "14px",
                  textAlign: "center",
                  padding: "48px",
                  margin: 0,
                }}
              >
                Select a run above to view stats and monthly returns.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// Suppress unused import warning for irColor — it drives the logic
void irColor;
void sharpeColor;
