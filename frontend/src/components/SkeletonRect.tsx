import React from "react";

interface SkeletonRectProps {
  width?: string;
  height: number;
  borderRadius?: number;
}

export default function SkeletonRect({
  width = "100%",
  height,
  borderRadius = 4,
}: SkeletonRectProps) {
  return (
    <div
      style={{
        width,
        height: `${height}px`,
        borderRadius: `${borderRadius}px`,
        backgroundColor: "#1A3050",
        animation: "skeleton-pulse 1.5s ease-in-out infinite",
      }}
    />
  );
}
