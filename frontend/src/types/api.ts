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
  stop_loss_price: number | null;
  take_profit_price: number | null;
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
