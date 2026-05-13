"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  TrendingUp,
  BarChart2,
  Bell,
  FlaskConical,
  Settings,
  LineChart,
  Brain,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", icon: <LayoutDashboard size={18} /> },
  { href: "/positions", label: "Positions", icon: <TrendingUp size={18} /> },
  { href: "/signals", label: "Signals", icon: <BarChart2 size={18} /> },
  { href: "/alerts", label: "Alerts", icon: <Bell size={18} /> },
  { href: "/backtest", label: "Backtest", icon: <FlaskConical size={18} /> },
  { href: "/macro", label: "Macro", icon: <LineChart size={18} /> },
  { href: "/rl", label: "RL State", icon: <Brain size={18} /> },
  { href: "/settings", label: "Settings", icon: <Settings size={18} /> },
];

export default function NavSidebar() {
  const pathname = usePathname();

  return (
    <nav
      style={{
        width: "240px",
        minHeight: "100vh",
        backgroundColor: "var(--color-surface)",
        borderRight: "1px solid #1A3050",
        display: "flex",
        flexDirection: "column",
        padding: "24px 0",
        flexShrink: 0,
      }}
    >
      <div
        style={{
          padding: "0 20px 24px",
          borderBottom: "1px solid #1A3050",
          marginBottom: "8px",
        }}
      >
        <span
          className="mono"
          style={{
            fontSize: "14px",
            fontWeight: 600,
            color: "var(--color-accent)",
            letterSpacing: "0.05em",
          }}
        >
          PEAD TRADING
        </span>
      </div>

      {NAV_ITEMS.map((item) => {
        const isActive = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              padding: "10px 20px",
              color: isActive ? "white" : "var(--color-muted)",
              backgroundColor: isActive ? "rgba(36,113,163,0.2)" : "transparent",
              borderLeft: isActive ? "3px solid var(--color-accent)" : "3px solid transparent",
              textDecoration: "none",
              fontSize: "14px",
              fontWeight: isActive ? 500 : 400,
              transition: "background-color 0.15s, color 0.15s",
            }}
          >
            {item.icon}
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
