import React from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
}

export default function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <div style={{ marginBottom: "32px" }}>
      <h1
        style={{
          fontSize: "24px",
          fontWeight: 700,
          color: "white",
          margin: 0,
          lineHeight: 1.2,
        }}
      >
        {title}
      </h1>
      {subtitle && (
        <p
          style={{
            fontSize: "14px",
            color: "var(--color-muted)",
            marginTop: "4px",
            marginBottom: 0,
          }}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}
