import { getSession } from 'next-auth/react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function getToken(): Promise<string> {
  const session = await getSession()
  return (session as { accessToken?: string } | null)?.accessToken ?? ''
}

export async function fetcher<T>(url: string): Promise<T> {
  const token = await getToken()
  const fullUrl = url.startsWith('http') ? url : `${API_URL}${url}`
  const res = await fetch(fullUrl, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  })

  if (!res.ok) {
    const error = new Error(`API error: ${res.status} ${res.statusText}`) as Error & { status: number }
    error.status = res.status
    throw error
  }

  return res.json() as Promise<T>
}

export async function poster<T>(url: string, body?: unknown): Promise<T> {
  const token = await getToken()
  const fullUrl = url.startsWith('http') ? url : `${API_URL}${url}`
  const res = await fetch(fullUrl, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const error = new Error(`API error: ${res.status} ${res.statusText}`) as Error & { status: number }
    error.status = res.status
    throw error
  }

  return res.json() as Promise<T>
}

export async function putter<T>(url: string, body?: unknown): Promise<T> {
  const token = await getToken()
  const fullUrl = url.startsWith('http') ? url : `${API_URL}${url}`
  const res = await fetch(fullUrl, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const error = new Error(`API error: ${res.status} ${res.statusText}`) as Error & { status: number }
    error.status = res.status
    throw error
  }

  return res.json() as Promise<T>
}

// Typed API client
export const api = {
  getPortfolioSummary: () => fetcher<PortfolioSummary>('/api/v1/portfolio/summary'),
  getPortfolioArchitecture: () => fetcher<PortfolioArchitecture>('/api/v1/portfolio/architecture'),
  getPositions: () => fetcher<Position[]>('/api/v1/positions'),
  getClosedPositions: () => fetcher<ClosedPosition[]>('/api/v1/positions/closed'),
  getSignals: () => fetcher<Signal[]>('/api/v1/signals'),
  getSignalHistory: () => fetcher<SignalHistoryItem[]>('/api/v1/signals/history'),
  getEarningsCalendar: () => fetcher<EarningsEvent[]>('/api/v1/signals/earnings-calendar'),
  getMacroRegime: () => fetcher<MacroRegime>('/api/v1/macro/regime'),
  getMacroHistory: (days: number) => fetcher<MacroHistory[]>(`/api/v1/macro/history?days=${days}`),
  getRLEpisodes: () => fetcher<RLEpisode[]>('/api/v1/rl/episodes'),
  getRLFactors: () => fetcher<RLFactors>('/api/v1/rl/factors'),
  getRLAgentStats: () => fetcher<RLAgentStats>('/api/v1/rl/agent-stats'),
  triggerTraining: () => poster<{ message: string; job_id: string }>('/api/v1/rl/train'),
  getYieldCurve: () => fetcher<YieldCurve>('/api/v1/market/yield-curve'),
  getInflation: () => fetcher<InflationData>('/api/v1/market/inflation'),
  getCreditRisk: () => fetcher<CreditRiskData>('/api/v1/market/credit-risk'),
  getGDPData: () => fetcher<GDPPoint[]>('/api/v1/market/gdp'),
  getCarryOverlay: () => fetcher<CarryData>('/api/v1/market/carry'),
  getERPMonitor: () => fetcher<ERPData>('/api/v1/market/erp'),
  getGrowthValue: () => fetcher<GrowthValueData>('/api/v1/market/growth-value'),
  getOrders: () => fetcher<Order[]>('/api/v1/orders'),
  getEquityCurve: () => fetcher<EquityCurvePoint[]>('/api/v1/portfolio/equity-curve'),
  getActivityFeed: () => fetcher<ActivityEvent[]>('/api/v1/portfolio/activity'),
  getSectorBreakdown: () => fetcher<SectorBreakdown[]>('/api/v1/portfolio/sector-breakdown'),
  getPerformanceStats: () => fetcher<PerformanceStats>('/api/v1/portfolio/performance'),
  getSettings: () => fetcher<Settings>('/api/v1/settings'),
  updateSettings: (settings: Partial<Settings>) => putter<Settings>('/api/v1/settings', settings),
  getDataSources: () => fetcher<DataSource[]>('/api/v1/data-sources'),
  // Backtest
  getBacktestRuns: () => fetcher<BacktestRun[]>('/api/v1/backtest/runs'),
  getBacktestRun: (id: string) => fetcher<BacktestRunDetail>(`/api/v1/backtest/runs/${id}`),
  triggerBacktest: (config: BacktestConfig) => poster<{ run_id: string }>('/api/v1/backtest/run', config),
  // Alerts
  getAlerts: (limit = 100) => fetcher<AlertEvent[]>(`/api/v1/alerts?limit=${limit}`),
  sendTestAlert: () => poster<{ status: string }>('/api/v1/alerts/test'),
  getAlertRules: () => fetcher<AlertRules>('/api/v1/alerts/rules'),
  updateAlertRules: (rules: AlertRules) => poster<AlertRules>('/api/v1/alerts/rules', rules),
}

// Type definitions
export interface PortfolioSummary {
  total_nav: number
  daily_pnl: number
  daily_pnl_pct: number
  open_positions_count: number
  cash_balance: number
  total_return: number
  total_return_pct: number
}

export interface Position {
  ticker: string
  entry_date: string
  entry_price: number
  current_price: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  days_held: number
  stop_level: number
  quantity: number
  signal_score: number
  sector: string
  intangible_tier: string
  pct_to_stop: number
}

export interface ClosedPosition {
  ticker: string
  entry_date: string
  exit_date: string
  entry_price: number
  exit_price: number
  pnl: number
  pnl_pct: number
  holding_period: number
  ff5_alpha: number
  exit_reason: 'STOP' | 'EXPIRY' | 'REVERSAL' | 'MANUAL'
  sector: string
}

export interface MacroSignal {
  name: string
  current_value: number
  threshold: number
  status: 'normal' | 'adverse'
  label: string
}

export interface MacroRegime {
  composite_score: number
  halted: boolean
  sizing_multiplier: number
  signals: MacroSignal[]
  last_updated: string
}

export interface MacroHistory {
  date: string
  composite_score: number
  halted: boolean
}

export interface Signal {
  ticker: string
  date: string
  surprise_score: number
  direction: 'LONG' | 'SHORT' | 'NO_TRADE'
  intangible_multiplier: number
  roic_multiplier: number
  rl_action_size: number
  proposed_position_size_pct: number
  sector: string
  consensus_eps: number
  actual_eps: number
  report_time: 'BMO' | 'AMC'
}

export interface EarningsEvent {
  ticker: string
  date: string
  sector: string
  consensus_eps: number
  implied_eps: number
  report_time: 'BMO' | 'AMC'
  signal_breakdown?: {
    surprise_score: number
    intangible_score: number
    roic_score: number
    momentum_score: number
  }
}

export interface SignalHistoryItem {
  ticker: string
  date: string
  surprise_score: number
  direction: 'LONG' | 'SHORT' | 'NO_TRADE'
  rl_action: number
  entered: boolean
  exit_pnl: number | null
  ff5_alpha: number | null
  sector: string
}

export interface RLEpisode {
  episode: number
  step: number
  reward: number
  smoothed_reward: number
  timestamp: string
}

export interface RLFactors {
  mkt_rf: number
  smb: number
  hml: number
  rmw: number
  cma: number
  last_updated: string
}

export interface RLAgentStats {
  last_trained: string
  model_path: string
  episode_buffer_size: number
  total_episodes: number
  action_distribution: { bin: string; count: number }[]
  sector_rewards: SectorReward[]
}

export interface SectorReward {
  sector: string
  avg_reward: number
  n_trades: number
  win_rate: number
}

export interface YieldCurve {
  date: string
  nominal: { maturity: string; yield: number }[]
  real: { maturity: string; yield: number }[]
  spread_10y_2y: number
  spread_history: { date: string; spread: number }[]
}

export interface InflationData {
  core_pce: { date: string; value: number }[]
  cpi: { date: string; value: number }[]
  current_core_pce: number
  current_cpi: number
}

export interface CreditRiskData {
  hy_oas: { date: string; value: number }[]
  vix: { date: string; value: number }[]
  current_hy_oas: number
  current_vix: number
}

export interface GDPPoint {
  quarter: string
  real_gdp_qoq: number
}

export interface CarryData {
  jpy_aud: { date: string; value: number }[]
  current_rate_of_change: number
  threshold: number
  triggered: boolean
}

export interface Order {
  id: string
  ticker: string
  side: 'buy' | 'sell'
  quantity: number
  price: number
  status: 'filled' | 'pending' | 'cancelled'
  timestamp: string
}

export interface EquityCurvePoint {
  date: string
  portfolio_return: number
  sp500_return: number
  ff5_alpha: number
}

export interface ActivityEvent {
  id: string
  type: 'ENTRY' | 'EXIT' | 'STOP' | 'MACRO_CHANGE'
  ticker?: string
  message: string
  timestamp: string
  details?: string
}

export interface Settings {
  brokerage: {
    alpaca_api_key: string
    alpaca_secret_key: string
    paper_trading: boolean
    last_sync: string
    connection_status: 'connected' | 'disconnected' | 'error'
  }
  risk: {
    hard_stop_pct: number
    max_position_size_pct: number
    max_sector_concentration_pct: number
    macro_halt_threshold: number
  }
  signal: {
    min_signal_threshold: number
    intangible_tier_multipliers: { tier1: number; tier2: number; tier3: number }
    roic_multiplier: number
  }
  notifications: {
    trade_executed: boolean
    stop_triggered: boolean
    macro_regime_change: boolean
    rl_training_complete: boolean
    webhook_url: string
  }
}

export interface DataSource {
  name: string
  status: 'fresh' | 'stale' | 'error'
  last_fetched: string
  api_key_configured: boolean
}

export interface SectorBreakdown {
  sector: string
  n_trades: number
  win_rate: number
  avg_pnl: number
  total_pnl: number
}

export interface PerformanceStats {
  win_rate: number
  avg_hold_days: number
  avg_ff5_alpha: number
  best_sector: string
  total_trades: number
  total_pnl: number
}

// v3 additions

export interface PortfolioArchitecture {
  erp_compressed: boolean
  erp_spread: number
  earnings_yield: number
  real_10y_yield: number
  growth_value_ratio: number
  gv_stretched: boolean
  mag7_utilization_pct: number
  mag7_names_active: string[]
  global_size_cap: number
  completion_portfolio_drift: number
  recommended_etf: string
  sleeve_pct_nav: number
}

export interface ERPData {
  history: { date: string; erp_spread: number; earnings_yield: number; real_10y_yield: number }[]
  current_erp_spread: number
  current_earnings_yield: number
  current_real_yield: number
  compressed: boolean
}

export interface GrowthValueData {
  history: { date: string; ratio: number }[]
  current_ratio: number
  stretched: boolean
  vug_pe: number
  vtv_pe: number
}

export interface BacktestConfig {
  start_date: string
  end_date: string
  signal_threshold: number
  macro_halt_threshold: number
  enable_portfolio_arch: boolean
  enable_short_side: boolean
  slippage_bps: number
  initial_nav: number
  max_position_pct: number
  hard_stop_pct: number
  rl_checkpoint_id?: string
}

export interface BacktestRun {
  id: string
  config: BacktestConfig
  total_return: number
  ann_return: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
  avg_ff5_alpha: number
  total_trades: number
  ir_vs_baseline: number
  run_at: string
  status: 'pending' | 'running' | 'complete' | 'failed'
}

export interface BacktestTrade {
  ticker: string
  entry_date: string
  exit_date: string
  entry_price: number
  exit_price: number
  pnl: number
  pnl_pct: number
  signal_score: number
  quality_score: number
  macro_regime: string
  sector: string
  exit_reason: string
  ff5_alpha: number
}

export interface BacktestRunDetail extends BacktestRun {
  equity_curve: { date: string; nav: number; sp500: number; naive: number }[]
  trade_log: BacktestTrade[]
  trades_by_regime: { regime: string; n_trades: number; win_rate: number; avg_alpha: number }[]
  trades_by_sector: { sector: string; n_trades: number; win_rate: number; avg_alpha: number }[]
}

export interface AlertEvent {
  id: string
  alert_type: 'trade_entry' | 'stop_triggered' | 'signal_skip' | 'macro_regime_change' | 'erp_alert' | 'carry_crash' | 'rl_retrain_complete' | 'backtest_complete' | 'ir_degradation'
  message: string
  payload: Record<string, unknown>
  channel: 'email' | 'slack' | 'both'
  delivered: boolean
  fired_at: string
}

export interface AlertRuleConfig {
  enabled: boolean
  channel: 'email' | 'slack' | 'both'
}

export interface AlertRules {
  trade_entry: AlertRuleConfig
  stop_triggered: AlertRuleConfig
  signal_skip: AlertRuleConfig
  macro_regime_change: AlertRuleConfig
  erp_alert: AlertRuleConfig
  carry_crash: AlertRuleConfig
  rl_retrain_complete: AlertRuleConfig
  backtest_complete: AlertRuleConfig
  ir_degradation: AlertRuleConfig
}
