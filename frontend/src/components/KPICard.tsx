import React from "react";

interface KPICardProps {
  label: string;
  value: string | number | null | undefined;
  unit?: string;
  positive?: boolean;
  negative?: boolean;
}

export default function KPICard({ label, value, unit, positive, negative }: KPICardProps) {
  let valueColor = "white";
  if (positive) valueColor = "var(--color-positive)";
  if (negative) valueColor = "var(--color-danger)";

  return (
    <div
      style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid #1A3050",
        borderRadius: "8px",
        padding: "20px 24px",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
    >
      <span
        style={{
          fontSize: "12px",
          color: "var(--color-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        {label}
      </span>
      <span
        className="mono"
        style={{
          fontSize: "28px",
          fontWeight: 600,
          color: valueColor,
          lineHeight: 1,
        }}
      >
        {value !== null && value !== undefined ? value : "-"}
        {unit && (
          <span style={{ fontSize: "14px", fontWeight: 400, marginLeft: "4px", color: "var(--color-muted)" }}>
            {unit}
          </span>
        )}
      </span>
    </div>
  );
}
