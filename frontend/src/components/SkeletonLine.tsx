import React from "react";

interface SkeletonLineProps {
  width?: string;
}

export default function SkeletonLine({ width = "100%" }: SkeletonLineProps) {
  return (
    <div
      style={{
        width,
        height: "16px",
        borderRadius: "4px",
        backgroundColor: "#1A3050",
        animation: "skeleton-pulse 1.5s ease-in-out infinite",
      }}
    />
  );
}
