/** Typed fetch wrapper. All API calls go through here. Handles auth redirect on 401. */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("pead_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),

  // Auth
  login: (username: string, password: string) =>
    request<{ access_token: string }>("/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username, password }).toString(),
    }),

  // Dashboard
  dashboardSummary: () => request<DashboardSummary>("/dashboard/summary"),
  recentAlerts: () => request<RecentAlert[]>("/dashboard/alerts/recent"),

  // Signals
  signals: () => request<Signal[]>("/signals?limit=20"),

  // Positions
  positions: () => request<Position[]>("/positions"),

  // RL
  rlEpisodes: () => request<RLEpisode[]>("/rl/episodes"),
  rlFactors: () => request<RLMetrics>("/rl/factors"),

  // Macro
  macroRegime: () => request<MacroRegime>("/macro/regime"),
  macroHistory: (days = 30) => request<MacroHistoryPoint[]>(`/macro/history?days=${days}`),

  // Backtest
  backtestRuns: () => request<BacktestRun[]>("/backtest/runs"),
  backtestRun: (id: string) => request<BacktestRun>(`/backtest/runs/${id}`),
  backtestTrades: (id: string) => request<BacktestTrade[]>(`/backtest/runs/${id}/trades`),
  triggerBacktest: (cfg: BacktestConfig) => request<BacktestRun>("/backtest/runs", { method: "POST", body: JSON.stringify(cfg) }),

  // Alerts
  alerts: (params?: { event_type?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.event_type) q.set("event_type", params.event_type);
    if (params?.limit) q.set("limit", String(params.limit));
    return request<AlertRow[]>(`/alerts/?${q}`);
  },

  // Settings
  settings: () => request<Setting[]>("/settings"),
  updateSetting: (key: string, value: string) =>
    request<Setting>("/settings", { method: "POST", body: JSON.stringify({ key, value }) }),
};

// ── Types ──────────────────────────────────────────────────────────────────

export interface DashboardSummary {
  nav: number | null;
  daily_pnl: number | null;
  daily_pnl_pct: number | null;
  open_positions: number;
  macro_regime: string;
  macro_score: number;
  size_multiplier: number;
  erp_compressed: boolean;
  alpha_tstat: number | null;
  last_updated: string;
}

export interface RecentAlert {
  id: string;
  event_type: string;
  ticker: string | null;
  title: string;
  priority: string;
  created_at: string;
}

export interface Signal {
  id: string;
  ticker: string;
  gics_sector: string | null;
  eps_actual: number | null;
  eps_implied: number | null;
  eps_gap_sigma: number | null;
  quality_score: number | null;
  signal_composite: number | null;
  announcement_ts: string;
}

export interface Position {
  id: string;
  ticker: string;
  direction: string;
  shares: number;
  entry_price: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  stop_price: number | null;
  target_price: number | null;
  thesis_status: string | null;
  days_held: number | null;
  entry_ts: string;
  nav_weight: number | null;
}

export interface RLEpisode {
  id: string;
  action: number;
  reward: number;
  done: boolean;
  created_at: string;
}

export interface RLMetrics {
  episode_count: number;
  mean_reward_20: number | null;
  last_trained_at: string | null;
  factor_betas: Record<string, number> | null;
}

export interface MacroRegime {
  time: string;
  composite_score: number;
  size_multiplier: number;
  is_halted: boolean;
  components: Record<string, number | boolean | null>;
}

export interface MacroHistoryPoint {
  time: string;
  composite_score: number;
  size_multiplier: number;
}

export interface BacktestRun {
  id: string;
  label: string | null;
  start_date: string;
  end_date: string;
  status: string;
  created_at: string;
  total_return: number | null;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  win_rate: number | null;
  ir_vs_naive: number | null;
  total_trades: number | null;
  config: Record<string, unknown> | null;
}

export interface BacktestTrade {
  id: string;
  ticker: string;
  direction: string;
  entry_date: string;
  exit_date: string | null;
  entry_price: number;
  exit_price: number | null;
  realized_pnl: number | null;
  ff5_alpha: number | null;
  hold_days: number | null;
  exit_reason: string | null;
}

export interface BacktestConfig {
  start_date: string;
  end_date: string;
  initial_nav?: number;
  min_signal_threshold?: number;
  min_quality_score?: number;
  slippage_bps?: number;
  enable_shorts?: boolean;
  run_label?: string;
}

export interface AlertRow {
  id: string;
  event_type: string;
  ticker: string | null;
  title: string;
  body: string;
  priority: string;
  delivered: boolean;
  created_at: string;
}

export interface Setting {
  key: string;
  value: string;
  updated_at: string;
}
