"use client";

import React from "react";

interface CompositeScoreBarProps {
  score: number;
}

export default function CompositeScoreBar({ score }: CompositeScoreBarProps) {
  // Clamp score to [-6, 0]
  const clamped = Math.max(-6, Math.min(0, score));
  // 0 = 0% fill, -6 = 100% fill
  const fillPct = ((clamped * -1) / 6) * 100;

  const markerStyle = (offsetFraction: number): React.CSSProperties => ({
    position: "absolute",
    top: "-8px",
    left: `${offsetFraction * 100}%`,
    width: "1px",
    height: "28px",
    borderLeft: "1px dashed #6B8EAD",
  });

  const pointerLeft = `${fillPct}%`;

  return (
    <div style={{ width: "100%", paddingTop: "16px" }}>
      {/* Scale labels */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "8px",
        }}
      >
        <span style={{ fontSize: "11px", color: "#6B8EAD", fontFamily: "Inter, system-ui, sans-serif" }}>
          0
        </span>
        <span style={{ fontSize: "11px", color: "#6B8EAD", fontFamily: "Inter, system-ui, sans-serif" }}>
          -6
        </span>
      </div>

      {/* Bar track */}
      <div
        style={{
          height: "12px",
          borderRadius: "6px",
          backgroundColor: "#1A3050",
          position: "relative",
        }}
      >
        {/* Fill */}
        <div
          style={{
            height: "100%",
            borderRadius: "6px",
            width: `${fillPct}%`,
            background: "linear-gradient(to right, #27AE60, #E74C3C)",
          }}
        />

        {/* Threshold marker at -1 (1/6 of range) */}
        <div style={markerStyle(1 / 6)} />

        {/* Threshold marker at -3 (3/6 of range) */}
        <div style={markerStyle(3 / 6)} />

        {/* Pointer triangle at current score position */}
        <div
          style={{
            position: "absolute",
            top: "-6px",
            left: pointerLeft,
            transform: "translateX(-50%)",
            width: 0,
            height: 0,
            borderLeft: "6px solid transparent",
            borderRight: "6px solid transparent",
            borderBottom: "8px solid #FFFFFF",
          }}
        />
      </div>

      {/* Legend */}
      <div
        style={{
          marginTop: "12px",
          display: "flex",
          gap: "16px",
          fontSize: "11px",
          color: "#6B8EAD",
          fontFamily: "Inter, system-ui, sans-serif",
          flexWrap: "wrap",
        }}
      >
        <span>Full sizing (0 to -1)</span>
        <span>Reduced (-2 to -3)</span>
        <span>Minimal (-4 to -6)</span>
      </div>
    </div>
  );
}
