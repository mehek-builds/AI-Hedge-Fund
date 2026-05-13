"use client";

import React from "react";

interface Props {
  monthlyReturns: Record<string, number> | null;
}

const MONTH_LABELS = [
  "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
];

function returnColor(r: number | null): { background: string; color: string } {
  if (r === null) return { background: "#1A3050", color: "#6B8EAD" };
  if (r >= 0.03) return { background: "#1E8449", color: "#FFFFFF" };
  if (r >= 0.01) return { background: "#27AE60", color: "#FFFFFF" };
  if (r >= 0) return { background: "rgba(46,204,113,0.6)", color: "#FFFFFF" };
  if (r >= -0.0099) return { background: "rgba(230,126,34,0.6)", color: "#FFFFFF" };
  if (r >= -0.03) return { background: "#E74C3C", color: "#FFFFFF" };
  return { background: "#922B21", color: "#FFFFFF" };
}

function formatReturn(r: number | null): string {
  if (r === null) return "--";
  const sign = r >= 0 ? "+" : "";
  return `${sign}${(r * 100).toFixed(1)}%`;
}

export default function MonthlyReturnsHeatmap({ monthlyReturns }: Props) {
  if (monthlyReturns === null) {
    return (
      <p style={{ color: "#6B8EAD", fontSize: "14px", margin: "16px 0 0" }}>
        No monthly returns data for this run.
      </p>
    );
  }

  const keys = Object.keys(monthlyReturns);
  if (keys.length === 0) {
    return (
      <p style={{ color: "#6B8EAD", fontSize: "14px", margin: "16px 0 0" }}>
        No monthly returns data for this run.
      </p>
    );
  }

  const years = Array.from(
    new Set(keys.map((k) => k.split("-")[0]))
  ).sort();

  return (
    <div
      style={{
        backgroundColor: "#0F2040",
        border: "1px solid #1A3050",
        borderRadius: "8px",
        padding: "20px 24px",
        marginTop: "24px",
      }}
    >
      <span
        style={{
          display: "block",
          fontSize: "14px",
          fontWeight: 500,
          color: "#6B8EAD",
          marginBottom: "16px",
        }}
      >
        Monthly Returns
      </span>
      <div style={{ overflowX: "auto" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "60px repeat(12, 56px)",
            gap: "2px",
            minWidth: "740px",
          }}
        >
          {/* Header row */}
          <div style={{ height: "24px" }} />
          {MONTH_LABELS.map((m) => (
            <div
              key={m}
              style={{
                height: "24px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "11px",
                color: "#6B8EAD",
                fontFamily: "Inter, system-ui, sans-serif",
              }}
            >
              {m}
            </div>
          ))}

          {/* Data rows — one per year */}
          {years.map((year) => (
            <React.Fragment key={year}>
              {/* Year label */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "flex-end",
                  paddingRight: "8px",
                  fontSize: "12px",
                  color: "#6B8EAD",
                  fontFamily: "Inter, system-ui, sans-serif",
                  height: "36px",
                }}
              >
                {year}
              </div>

              {/* 12 month cells */}
              {Array.from({ length: 12 }, (_, i) => {
                const month = String(i + 1).padStart(2, "0");
                const key = `${year}-${month}`;
                const value = monthlyReturns[key] ?? null;
                const { background, color } = returnColor(value);
                return (
                  <div
                    key={key}
                    title={`${key}: ${formatReturn(value)}`}
                    style={{
                      width: "56px",
                      height: "36px",
                      borderRadius: "4px",
                      backgroundColor: background,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <span
                      className="mono"
                      style={{
                        fontSize: "11px",
                        color,
                        lineHeight: 1,
                      }}
                    >
                      {formatReturn(value)}
                    </span>
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}
