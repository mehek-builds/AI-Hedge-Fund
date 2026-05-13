// ---------------------------------------------------------------------------
// REST response shapes
// ---------------------------------------------------------------------------

export interface AlertRecord {
  alert_id: string;
  created_at: string | null;
  level: string | null;
  category: string | null;
  symbol: string | null;
  message: string;
}

export interface AlertSummary {
  total: number;
  limit: number;
  offset: number;
  items: AlertRecord[];
}

export interface DashboardData {
  position_count: number;
  total_unrealized_pnl: number;
  macro_gate_open: boolean | null;
  recent_alerts: AlertRecord[];
}

export interface Position {
  snapshot_at: string | null;
  symbol: string;
  qty: number | null;
  avg_entry_price: number | null;
  current_price: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  stop_loss_price: number | null;
  take_profit_price: number | null;
  thesis_status: "INTACT" | "MONITOR" | "BROKEN" | null;
  status: string | null;
}

export interface SignalRow {
  created_at: string | null;
  signal_id: string;
  symbol: string | null;
  earnings_event_id: number | null;
  eps_gap: number | null;
  quality_score: number | null;
  three_axis_composite: number | null;
  naive_position_size: number | null;
  direction: string | null;
  status: string | null;
}

export interface BacktestRun {
  run_id: string;
  created_at: string | null;
  name: string | null;
  status: string | null;
  macro_gate_open: boolean | null;
  sharpe_ratio: number | null;
  total_return: number | null;
  max_drawdown: number | null;
  params: Record<string, unknown> | null;
  results: Record<string, unknown> | null;
}

export interface Settings {
  ENABLE_SHORT_SIDE: boolean;
  STOP_LOSS_PCT: number;
  TAKE_PROFIT_PCT: number;
}

export interface SettingsPatch {
  ENABLE_SHORT_SIDE?: boolean;
  STOP_LOSS_PCT?: number;
  TAKE_PROFIT_PCT?: number;
}

// Plan 08-04: extended settings with runtime alert threshold
export interface SettingsData {
  ENABLE_SHORT_SIDE: boolean;
  STOP_LOSS_PCT: number;
  TAKE_PROFIT_PCT: number;
  max_alerts_per_hour: number;
}

export interface SettingsDataPatch {
  ENABLE_SHORT_SIDE?: boolean;
  STOP_LOSS_PCT?: number;
  TAKE_PROFIT_PCT?: number;
  max_alerts_per_hour?: number;
}

export interface MacroIndicator {
  date: string | null;
  series_id: string;
  value: number | null;
  vintage_date: string | null;
  source: string | null;
}

export interface MacroGateStatus {
  macro_gate_open: boolean | null;
  last_evaluated_at: string | null;
}

export interface MacroData {
  indicators: MacroIndicator[];
  gate_status: MacroGateStatus;
}

// Plan 08-04: enriched macro types for Macro Monitor view
export interface MacroIndicatorValue {
  series_id: string;
  value: number;
  date: string;
  vintage_date: string;
  signal: "RISK_ON" | "NEUTRAL" | "RISK_OFF";
}

export interface MacroDataEnriched {
  indicators: MacroIndicatorValue[];
  composite_score: number;
  gate_status: "OPEN" | "GATED";
  sizing_multiplier: number;
  as_of: string;
}

export interface RLAgent {
  agent_id: number;
  regime: string;
  weight: number;
}

export interface RLState {
  agents: RLAgent[];
  regime_weights: Record<string, number>;
  note?: string;
}

// ---------------------------------------------------------------------------
// SSE event payload shapes (data field parsed from JSON)
// ---------------------------------------------------------------------------

export interface SSESignalPayload {
  signal_id: string;
  symbol: string | null;
  direction: string | null;
  quality_score: number | null;
  three_axis_composite: number | null;
  created_at: string;
}

export interface SSEPositionPayload {
  symbol: string;
  qty: number | null;
  current_price: number | null;
  unrealized_pnl: number | null;
  status: string | null;
  snapshot_at: string;
}

export interface SSEAlertPayload {
  alert_id: string;
  level: string | null;
  category: string | null;
  symbol: string | null;
  message: string;
  created_at: string;
}

export interface SSERLStatePayload {
  agents: RLAgent[];
  regime_weights: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Plan 08-03 extended types
// ---------------------------------------------------------------------------

export interface AgentRewardSeries {
  agent_id: number;
  reward_history: { step: number; reward: number }[];
  latest_reward: number;
}

export interface RLStateData {
  agents: AgentRewardSeries[];
  regime_weights: {
    expansion: number;
    caution: number;
    crisis: number;
  };
  last_checkpoint_step: number;
  last_updated: string;
}

export interface SSERLStateUpdatePayload {
  event: "rl_state_update";
  agent_id: number;
  step: number;
  reward: number;
  regime_weights: {
    expansion: number;
    caution: number;
    crisis: number;
  };
  checkpoint_step: number;
}

/** Rich backtest run with monthly returns and config snapshot */
export interface BacktestRunDetail {
  id: string;
  start_date: string;
  end_date: string;
  slice_type: string;
  sharpe: number | null;
  max_drawdown: number | null;
  ir_vs_baseline: number | null;
  calmar: number | null;
  monthly_returns: Record<string, number> | null;
  gate_status: string;
  gate_reason: string | null;
  total_trades: number | null;
  config_snapshot: Record<string, unknown> | null;
  created_at: string;
}

/** Lightweight summary for the run selector list */
export interface BacktestRunSummary {
  id: string;
  start_date: string;
  end_date: string;
  slice_type: string;
  gate_status: string;
  sharpe: number | null;
  created_at: string;
}

/** Paginated alerts response (new schema) */
export interface AlertItem {
  id: string;
  event_type: string;
  payload: Record<string, unknown> | null;
  created_at: string;
  delivered_sendgrid: boolean;
  delivered_slack: boolean;
  rate_limited: boolean;
}

export interface AlertsPage {
  items: AlertItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface SSEAlertDispatchedPayload {
  event: "alert_dispatched";
  id: string;
  event_type: string;
  payload: Record<string, unknown> | null;
  created_at: string;
  delivered_sendgrid: boolean;
  delivered_slack: boolean;
  rate_limited: boolean;
}
