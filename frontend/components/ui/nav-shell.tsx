"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";

const VIEWS = [
  { label: "Dashboard",    href: "/dashboard" },
  { label: "Signals",      href: "/dashboard/signals" },
  { label: "Positions",    href: "/dashboard/positions" },
  { label: "Paper Trade",  href: "/dashboard/paper-trading" },
  { label: "RL Console",   href: "/dashboard/rl" },
  { label: "Macro",        href: "/dashboard/macro" },
  { label: "Backtest",     href: "/dashboard/backtests" },
  { label: "Alerts",       href: "/dashboard/alerts" },
  { label: "Settings",     href: "/dashboard/settings" },
];

export function NavShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [time, setTime] = useState("");
  const [sseOk, setSseOk] = useState(true);

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setTime(
        now.toLocaleDateString("en-US", { day: "2-digit", month: "short", year: "2-digit" }).toUpperCase() +
        " · " +
        now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) +
        " ET"
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  function handleLogout() {
    localStorage.removeItem("pead_token");
    router.push("/login");
  }

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(href);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      {/* Top bar */}
      <header style={{
        display: "flex",
        alignItems: "center",
        height: 36,
        background: "var(--color-bg-panel)",
        borderBottom: "1px solid var(--color-border)",
        padding: "0 12px",
        flexShrink: 0,
        gap: 0,
      }}>
        {/* Wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: 7, marginRight: 16, flexShrink: 0 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--color-positive)" }} />
          <span style={{
            fontSize: 11, fontWeight: 600,
            letterSpacing: "0.1em", textTransform: "uppercase",
            color: "var(--color-text-primary)",
          }}>
            PEAD
          </span>
        </div>

        {/* Nav tabs */}
        <nav style={{ display: "flex", alignItems: "stretch", height: "100%", flex: 1, overflow: "hidden" }}>
          {VIEWS.map(v => (
            <Link key={v.href} href={v.href} style={{ textDecoration: "none" }}>
              <div style={{
                display: "flex",
                alignItems: "center",
                height: "100%",
                padding: "0 10px",
                fontSize: 10,
                fontWeight: 500,
                letterSpacing: "0.07em",
                textTransform: "uppercase",
                color: isActive(v.href) ? "var(--color-amber)" : "var(--color-text-muted)",
                borderBottom: isActive(v.href) ? "2px solid var(--color-amber)" : "2px solid transparent",
                whiteSpace: "nowrap",
                cursor: "pointer",
                transition: "color 0.1s",
              }}>
                {v.label}
              </div>
            </Link>
          ))}
        </nav>

        {/* Right meta */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginLeft: "auto", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{
              width: 5, height: 5, borderRadius: "50%",
              background: sseOk ? "var(--color-positive)" : "var(--color-negative)",
            }} />
            <span style={{ fontSize: 10, fontWeight: 500, color: sseOk ? "var(--color-positive)" : "var(--color-negative)" }}>
              {sseOk ? "LIVE" : "DISCONNECTED"}
            </span>
          </div>
          <span style={{ fontSize: 10, fontFamily: "var(--font-family-mono)", color: "var(--color-text-muted)" }}>
            {time}
          </span>
          <button
            onClick={handleLogout}
            style={{
              fontSize: 10, fontWeight: 500, letterSpacing: "0.06em",
              textTransform: "uppercase",
              color: "var(--color-text-muted)",
              background: "none", border: "none", cursor: "pointer", padding: "2px 6px",
            }}
          >
            OUT
          </button>
        </div>
      </header>

      {/* Page content */}
      <main style={{ flex: 1, overflow: "auto" }}>
        {children}
      </main>

      {/* Status bar */}
      <footer style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        height: 22,
        padding: "0 10px",
        background: "var(--color-bg-panel)",
        borderTop: "1px solid var(--color-border)",
        flexShrink: 0,
      }}>
        <StatusChip color="var(--color-positive)" label="READY" />
        <StatusChip label="SSE connected" />
        <StatusChip label="Redis pub/sub OK" />
        <StatusChip label="Alpaca paper" />
        <div style={{ marginLeft: "auto" }}>
          <StatusChip label="Phase 8 · v0.1.0" />
        </div>
      </footer>
    </div>
  );
}

function StatusChip({ label, color }: { label: string; color?: string }) {
  return (
    <span style={{
      fontSize: 9,
      fontFamily: "var(--font-family-mono)",
      letterSpacing: "0.04em",
      color: color ?? "var(--color-text-muted)",
    }}>
      {label}
    </span>
  );
}
