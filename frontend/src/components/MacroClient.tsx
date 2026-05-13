"use client";

import React from "react";
import PageHeader from "@/src/components/PageHeader";
import Badge from "@/src/components/Badge";
import SkeletonRect from "@/src/components/SkeletonRect";
import CompositeScoreBar from "@/src/components/CompositeScoreBar";
import { MacroDataEnriched, MacroIndicatorValue } from "@/src/types/api";

interface Props {
  initialData: MacroDataEnriched | null;
}

const SERIES_ORDER = [
  "T10Y2Y",
  "SAHMREALTIME",
  "USALOLITONOSTSAM",
  "MANEMP",
  "HYG_LQD_SPREAD",
  "JPY_AUD",
];

const SERIES_META: Record<string, { label: string; format: (v: number) => string }> = {
  T10Y2Y: {
    label: "Yield Curve (10Y-2Y)",
    format: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`,
  },
  SAHMREALTIME: {
    label: "Sahm Rule Indicator",
    format: (v) => v.toFixed(2),
  },
  USALOLITONOSTSAM: {
    label: "Leading Econ Index",
    format: (v) => `${v.toFixed(1)}%`,
  },
  MANEMP: {
    label: "ISM Manufacturing PMI",
    format: (v) => v.toFixed(1),
  },
  HYG_LQD_SPREAD: {
    label: "HY Credit Spread",
    format: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`,
  },
  JPY_AUD: {
    label: "JPY/AUD Carry Rate",
    format: (v) => v.toFixed(4),
  },
};

type Signal = "RISK_ON" | "NEUTRAL" | "RISK_OFF";

function signalLabel(signal: Signal): string {
  if (signal === "RISK_ON") return "RISK-ON";
  if (signal === "RISK_OFF") return "RISK-OFF";
  return "NEUTRAL";
}

function signalVariant(signal: Signal): "positive" | "muted" | "negative" {
  if (signal === "RISK_ON") return "positive";
  if (signal === "RISK_OFF") return "negative";
  return "muted";
}

function orderedIndicators(
  indicators: MacroIndicatorValue[]
): (MacroIndicatorValue | null)[] {
  const byId = new Map(indicators.map((ind) => [ind.series_id, ind]));
  return SERIES_ORDER.map((id) => byId.get(id) ?? null);
}

export default function MacroClient({ initialData }: Props) {
  const data = initialData;

  const gateOpen =
    data?.gate_status === "OPEN" ||
    (data?.gate_status as unknown as { macro_gate_open?: boolean })?.macro_gate_open === true;

  const gateLabel = data
    ? gateOpen
      ? "OPEN"
      : "GATED"
    : null;

  const compositeScore = data?.composite_score ?? 0;
  const sizingMultiplier = data?.sizing_multiplier ?? 1;
  const asOf = data?.as_of ?? null;

  const indicators = data ? orderedIndicators(data.indicators) : Array(6).fill(null);

  return (
    <div>
      <PageHeader title="Macro Monitor" />

      <div style={{ padding: "32px" }}>
        {/* Gate Status Banner */}
        {data === null ? (
          <SkeletonRect height={56} />
        ) : (
          <div
            style={{
              borderRadius: "8px",
              padding: "16px 24px",
              marginBottom: "24px",
              backgroundColor: gateOpen
                ? "rgba(39,174,96,0.15)"
                : "rgba(230,126,34,0.15)",
              border: gateOpen ? "1px solid #27AE60" : "1px solid #E67E22",
              color: gateOpen ? "#27AE60" : "#E67E22",
            }}
          >
            <div style={{ fontWeight: 600, fontSize: "15px", fontFamily: "Inter, system-ui, sans-serif" }}>
              Macro Gate: {gateLabel} &mdash;{" "}
              {gateOpen ? "Full position sizing active" : "Position sizing reduced"}
            </div>
            <div
              style={{
                fontSize: "13px",
                marginTop: "4px",
                fontFamily: "Inter, system-ui, sans-serif",
              }}
            >
              Composite Score: {compositeScore} / -6 | Sizing Multiplier: {sizingMultiplier}x
            </div>
          </div>
        )}

        {/* Macro Grid */}
        {data === null ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "24px",
              marginBottom: "32px",
            }}
          >
            {Array(6)
              .fill(null)
              .map((_, i) => (
                <SkeletonRect key={i} height={120} borderRadius={8} />
              ))}
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "24px",
              marginBottom: "32px",
            }}
          >
            {indicators.map((ind, idx) => {
              const seriesId = SERIES_ORDER[idx];
              const meta = SERIES_META[seriesId];

              if (!ind) {
                return (
                  <div
                    key={seriesId}
                    style={{
                      backgroundColor: "#0F2040",
                      border: "1px solid #1A3050",
                      borderRadius: "8px",
                      padding: "24px",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "12px",
                        color: "#6B8EAD",
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                        fontFamily: "Inter, system-ui, sans-serif",
                        marginBottom: "8px",
                      }}
                    >
                      {meta?.label ?? seriesId}
                    </div>
                    <div className="mono" style={{ fontSize: "20px", fontWeight: 600, color: "white" }}>
                      --
                    </div>
                  </div>
                );
              }

              const signal: Signal = ind.signal ?? "NEUTRAL";

              return (
                <div
                  key={ind.series_id}
                  style={{
                    backgroundColor: "#0F2040",
                    border: "1px solid #1A3050",
                    borderRadius: "8px",
                    padding: "24px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "12px",
                      color: "#6B8EAD",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                      fontFamily: "Inter, system-ui, sans-serif",
                      marginBottom: "8px",
                    }}
                  >
                    {meta?.label ?? ind.series_id}
                  </div>
                  <div
                    className="mono"
                    style={{
                      fontSize: "20px",
                      fontWeight: 600,
                      color: "white",
                      marginBottom: "8px",
                    }}
                  >
                    {ind.value != null ? meta?.format(ind.value) ?? String(ind.value) : "--"}
                  </div>
                  <Badge variant={signalVariant(signal)}>{signalLabel(signal)}</Badge>
                  {ind.vintage_date && (
                    <div
                      style={{
                        fontSize: "11px",
                        color: "#6B8EAD",
                        marginTop: "4px",
                        fontFamily: "Inter, system-ui, sans-serif",
                      }}
                    >
                      as of {ind.vintage_date}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Empty state when no data at all */}
        {data !== null && data.indicators.length === 0 && (
          <div
            style={{
              fontSize: "14px",
              color: "#6B8EAD",
              fontFamily: "Inter, system-ui, sans-serif",
              padding: "24px 0",
            }}
          >
            No macro data available yet.
          </div>
        )}

        {/* CompositeScoreBar */}
        {data !== null && (
          <CompositeScoreBar score={compositeScore} />
        )}

        {/* As-of timestamp */}
        {asOf && (
          <div
            style={{
              fontSize: "12px",
              color: "#6B8EAD",
              marginTop: "16px",
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            Data as of {new Date(asOf).toISOString().slice(0, 10)}
          </div>
        )}
      </div>
    </div>
  );
}
