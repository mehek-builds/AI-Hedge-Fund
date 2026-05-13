import React from "react";

type BadgeVariant =
  | "default"
  | "positive"
  | "negative"
  | "warning"
  | "info"
  | "muted";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
}

const VARIANT_STYLES: Record<BadgeVariant, React.CSSProperties> = {
  default: {
    backgroundColor: "rgba(36,113,163,0.2)",
    color: "#2471A3",
    border: "1px solid rgba(36,113,163,0.4)",
  },
  positive: {
    backgroundColor: "rgba(39,174,96,0.15)",
    color: "#27AE60",
    border: "1px solid rgba(39,174,96,0.35)",
  },
  negative: {
    backgroundColor: "rgba(231,76,60,0.15)",
    color: "#E74C3C",
    border: "1px solid rgba(231,76,60,0.35)",
  },
  warning: {
    backgroundColor: "rgba(230,126,34,0.15)",
    color: "#E67E22",
    border: "1px solid rgba(230,126,34,0.35)",
  },
  info: {
    backgroundColor: "rgba(107,142,173,0.15)",
    color: "#6B8EAD",
    border: "1px solid rgba(107,142,173,0.35)",
  },
  muted: {
    backgroundColor: "rgba(107,142,173,0.08)",
    color: "var(--color-muted)",
    border: "1px solid rgba(107,142,173,0.2)",
  },
};

export default function Badge({ children, variant = "default" }: BadgeProps) {
  return (
    <span
      className="mono"
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 8px",
        borderRadius: "4px",
        fontSize: "11px",
        fontWeight: 500,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        whiteSpace: "nowrap",
        ...VARIANT_STYLES[variant],
      }}
    >
      {children}
    </span>
  );
}
