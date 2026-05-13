import React from "react";

interface LoadingSkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  className?: string;
}

export default function LoadingSkeleton({
  width = "100%",
  height = "20px",
  borderRadius = "4px",
  className,
}: LoadingSkeletonProps) {
  return (
    <div
      className={className}
      style={{
        width,
        height,
        borderRadius,
        backgroundColor: "#1A3050",
        animation: "skeleton-pulse 1.5s ease-in-out infinite",
      }}
    />
  );
}

// Inline keyframes injected once via a style tag in a server component or globals.css.
// Add to globals.css if not already present:
// @keyframes skeleton-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
