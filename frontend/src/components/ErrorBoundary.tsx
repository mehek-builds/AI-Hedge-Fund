"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div
          style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-danger)",
            borderRadius: "8px",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          <span style={{ color: "var(--color-danger)", fontWeight: 600 }}>
            Something went wrong
          </span>
          <span style={{ color: "var(--color-muted)", fontSize: "13px" }}>
            {this.state.error?.message ?? "An unexpected error occurred."}
          </span>
          <button
            onClick={this.handleRetry}
            style={{
              alignSelf: "flex-start",
              padding: "8px 16px",
              backgroundColor: "var(--color-accent)",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
              fontSize: "13px",
            }}
          >
            Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
