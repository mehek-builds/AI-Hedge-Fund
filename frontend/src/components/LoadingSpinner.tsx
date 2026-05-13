import React from "react";

export default function LoadingSpinner() {
  return (
    <span
      aria-label="Loading"
      style={{
        display: "inline-block",
        width: "16px",
        height: "16px",
        border: "2px solid #1A3050",
        borderTopColor: "var(--color-accent)",
        borderRadius: "50%",
        animation: "spin 0.7s linear infinite",
      }}
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </span>
  );
}
