'use client'

import { useState } from 'react'
import useSWR from 'swr'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { api, BacktestRun, BacktestRunDetail, BacktestConfig } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'
import { StatCard } from '@/components/ui/StatCard'
import { LoadingSkeleton } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn, formatPct, formatDate, formatDateTime } from '@/lib/utils'

const DEFAULT_CONFIG: BacktestConfig = {
  start_date: '2018-01-01',
  end_date: '2023-12-31',
  signal_threshold: 1.0,
  macro_halt_threshold: -4,
  enable_portfolio_arch: true,
  enable_short_side: false,
  slippage_bps: 5,
  initial_nav: 100000,
  max_position_pct: 0.05,
  hard_stop_pct: 0.08,
}

interface TooltipPayload { value: number; name: string; color: string }
function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipPayload[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface border border-border rounded-lg p-3 shadow-xl">
      <p className="text-micro text-text-muted mb-1">{label}</p>
      {payload.map((e) => (
        <div key={e.name} className="flex items-center gap-2 text-micro">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: e.color }} />
          <span className="text-text-muted">{e.name}:</span>
          <span className="font-mono text-text-primary">{Number(e.value).toFixed(2)}%</span>
        </div>
      ))}
    </div>
  )
}

function RunConfigPanel({ onSubmit, loading }: { onSubmit: (cfg: BacktestConfig) => void; loading: boolean }) {
  const [cfg, setCfg] = useState<BacktestConfig>(DEFAULT_CONFIG)

  function field<K extends keyof BacktestConfig>(key: K, value: BacktestConfig[K]) {
    setCfg((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <div className="bg-surface border border-border rounded-lg p-4 space-y-4">
      <h2 className="text-card-title font-semibold text-text-primary">Run Configuration</h2>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-micro text-text-muted block mb-1">Start Date</label>
          <input
            type="date"
            value={cfg.start_date}
            onChange={(e) => field('start_date', e.target.value)}
            className="w-full bg-background border border-border rounded px-2 py-1.5 text-table text-text-primary font-mono"
          />
        </div>
        <div>
          <label className="text-micro text-text-muted block mb-1">End Date</label>
          <input
            type="date"
            value={cfg.end_date}
            onChange={(e) => field('end_date', e.target.value)}
            className="w-full bg-background border border-border rounded px-2 py-1.5 text-table text-text-primary font-mono"
          />
        </div>
        <div>
          <label className="text-micro text-text-muted block mb-1">Signal Threshold (SD)</label>
          <input
            type="number"
            step="0.1"
            value={cfg.signal_threshold}
            onChange={(e) => field('signal_threshold', parseFloat(e.target.value))}
            className="w-full bg-background border border-border rounded px-2 py-1.5 text-table text-text-primary font-mono"
          />
        </div>
        <div>
          <label className="text-micro text-text-muted block mb-1">Macro Halt Threshold</label>
          <input
            type="number"
            step="1"
            value={cfg.macro_halt_threshold}
            onChange={(e) => field('macro_halt_threshold', parseInt(e.target.value))}
            className="w-full bg-background border border-border rounded px-2 py-1.5 text-table text-text-primary font-mono"
          />
        </div>
        <div>
          <label className="text-micro text-text-muted block mb-1">Slippage (bps)</label>
          <input
            type="number"
            step="1"
            value={cfg.slippage_bps}
            onChange={(e) => field('slippage_bps', parseInt(e.target.value))}
            className="w-full bg-background border border-border rounded px-2 py-1.5 text-table text-text-primary font-mono"
          />
        </div>
        <div>
          <label className="text-micro text-text-muted block mb-1">Initial NAV ($)</label>
          <input
            type="number"
            step="10000"
            value={cfg.initial_nav}
            onChange={(e) => field('initial_nav', parseInt(e.target.value))}
            className="w-full bg-background border border-border rounded px-2 py-1.5 text-table text-text-primary font-mono"
          />
        </div>
      </div>

      <div className="flex gap-4">
        <label className="flex items-center gap-2 text-table text-text-muted cursor-pointer">
          <input
            type="checkbox"
            checked={cfg.enable_portfolio_arch}
            onChange={(e) => field('enable_portfolio_arch', e.target.checked)}
            className="accent-primary"
          />
          Portfolio Architecture Controls
        </label>
        <label className="flex items-center gap-2 text-table text-text-muted cursor-pointer">
          <input
            type="checkbox"
            checked={cfg.enable_short_side}
            onChange={(e) => field('enable_short_side', e.target.checked)}
            className="accent-primary"
          />
          Short Side (beta)
        </label>
      </div>

      <button
        onClick={() => onSubmit(cfg)}
        disabled={loading}
        className="w-full bg-primary hover:bg-primary/90 disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-md transition-colors text-table"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Running Backtest...
          </span>
        ) : 'Run Backtest'}
      </button>
    </div>
  )
}

function RunHistory({ runs, selected, onSelect }: { runs: BacktestRun[]; selected: string | null; onSelect: (id: string) => void }) {
  if (!runs.length) return <EmptyState title="No backtest runs yet" description="Configure and run your first backtest above" />

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-body font-semibold text-text-primary">Run History</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th>Date</th>
              <th className="text-right">Return</th>
              <th className="text-right">Sharpe</th>
              <th className="text-right">Max DD</th>
              <th className="text-right">Win Rate</th>
              <th className="text-right">IR vs Naive</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr
                key={run.id}
                onClick={() => onSelect(run.id)}
                className={cn('cursor-pointer', selected === run.id && 'bg-primary/10')}
              >
                <td className="text-text-muted text-micro">{formatDateTime(run.run_at)}</td>
                <td className={cn('text-right font-mono', run.total_return >= 0 ? 'text-positive' : 'text-negative')}>
                  {formatPct(run.total_return * 100)}
                </td>
                <td className={cn('text-right font-mono', run.sharpe_ratio >= 1 ? 'text-positive' : run.sharpe_ratio >= 0 ? 'text-warning' : 'text-negative')}>
                  {run.sharpe_ratio.toFixed(2)}
                </td>
                <td className="text-right font-mono text-negative">{formatPct(run.max_drawdown * 100)}</td>
                <td className={cn('text-right font-mono', run.win_rate >= 0.55 ? 'text-positive' : 'text-text-muted')}>
                  {formatPct(run.win_rate * 100, 1)}
                </td>
                <td className={cn('text-right font-mono', run.ir_vs_baseline > 0 ? 'text-positive' : 'text-negative')}>
                  {run.ir_vs_baseline.toFixed(2)}
                </td>
                <td>
                  <Badge variant={run.status === 'complete' ? 'positive' : run.status === 'failed' ? 'negative' : 'default'}>
                    {run.status.toUpperCase()}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RunResults({ runId }: { runId: string }) {
  const { data, isLoading } = useSWR<BacktestRunDetail>(
    `backtest-${runId}`,
    () => api.getBacktestRun(runId),
    { refreshInterval: runId ? 5000 : 0 }
  )

  if (isLoading) return <LoadingSkeleton className="h-96 w-full" />
  if (!data) return null
  if (data.status === 'pending' || data.status === 'running') {
    return (
      <div className="bg-surface border border-border rounded-lg p-8 flex items-center justify-center gap-3">
        <span className="w-5 h-5 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
        <span className="text-text-muted">Backtest running...</span>
      </div>
    )
  }

  const curveData = data.equity_curve?.map((p) => ({
    date: p.date.split('T')[0],
    Portfolio: ((p.nav / data.config.initial_nav) - 1) * 100,
    'S&P 500': p.sp500 * 100,
    'Naive Baseline': p.naive * 100,
  })) ?? []

  return (
    <div className="space-y-4">
      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <StatCard title="Total Return" value={formatPct(data.total_return * 100)} color={data.total_return >= 0 ? 'positive' : 'negative'} />
        <StatCard title="Ann. Return" value={formatPct(data.ann_return * 100)} color={data.ann_return >= 0 ? 'positive' : 'negative'} />
        <StatCard title="Sharpe" value={data.sharpe_ratio.toFixed(2)} color={data.sharpe_ratio >= 1 ? 'positive' : data.sharpe_ratio >= 0 ? 'warning' : 'negative'} />
        <StatCard title="Max Drawdown" value={formatPct(data.max_drawdown * 100)} color="negative" />
        <StatCard title="Win Rate" value={formatPct(data.win_rate * 100, 1)} color={data.win_rate >= 0.55 ? 'positive' : 'default'} />
        <StatCard title="Avg FF5 Alpha" value={formatPct(data.avg_ff5_alpha * 100)} color={data.avg_ff5_alpha >= 0 ? 'positive' : 'negative'} />
        <StatCard title="IR vs Naive" value={data.ir_vs_baseline.toFixed(2)} color={data.ir_vs_baseline > 0 ? 'positive' : 'negative'} subtitle="RL adds value if > 0" />
      </div>

      {/* Equity curve */}
      {curveData.length > 0 && (
        <div className="bg-surface border border-border rounded-lg p-4">
          <h3 className="text-body font-semibold text-text-primary mb-4">Equity Curve</h3>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={curveData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="btPortfolio" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontSize: '12px', color: '#6B7280' }} />
              <ReferenceLine y={0} stroke="#222222" />
              <Area type="monotone" dataKey="Portfolio" stroke="#3B82F6" strokeWidth={2} fill="url(#btPortfolio)" />
              <Area type="monotone" dataKey="S&P 500" stroke="#6B7280" strokeWidth={1.5} strokeDasharray="4 4" fill="none" />
              <Area type="monotone" dataKey="Naive Baseline" stroke="#F59E0B" strokeWidth={1.5} strokeDasharray="4 4" fill="none" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Regime + Sector breakdown */}
      {data.trades_by_regime && data.trades_by_sector && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-surface border border-border rounded-lg p-4">
            <h3 className="text-body font-semibold text-text-primary mb-3">Trades by Regime</h3>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={data.trades_by_regime} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
                <XAxis dataKey="regime" tick={{ fill: '#6B7280', fontSize: 11 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
                <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="win_rate" name="Win Rate %" fill="#3B82F6" radius={[2, 2, 0, 0]}
                  label={{ position: 'top', fill: '#6B7280', fontSize: 10, formatter: (v: number) => `${(v * 100).toFixed(0)}%` }}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-surface border border-border rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-border">
              <h3 className="text-body font-semibold text-text-primary">Trades by Sector</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th>Sector</th>
                    <th className="text-right">Trades</th>
                    <th className="text-right">Win %</th>
                    <th className="text-right">Avg α</th>
                  </tr>
                </thead>
                <tbody>
                  {data.trades_by_sector.map((s) => (
                    <tr key={s.sector}>
                      <td className="text-text-primary text-micro">{s.sector}</td>
                      <td className="text-right font-mono text-text-muted">{s.n_trades}</td>
                      <td className={cn('text-right font-mono', s.win_rate >= 0.55 ? 'text-positive' : 'text-text-muted')}>
                        {formatPct(s.win_rate * 100, 1)}
                      </td>
                      <td className={cn('text-right font-mono', s.avg_alpha >= 0 ? 'text-positive' : 'text-negative')}>
                        {formatPct(s.avg_alpha * 100)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Trade log */}
      {data.trade_log && data.trade_log.length > 0 && (
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <h3 className="text-body font-semibold text-text-primary">Trade Log</h3>
            <span className="text-micro text-text-muted">{data.trade_log.length} trades</span>
          </div>
          <div className="overflow-x-auto max-h-80">
            <table className="w-full">
              <thead className="sticky top-0 bg-surface">
                <tr>
                  <th>Ticker</th>
                  <th>Entry</th>
                  <th>Exit</th>
                  <th className="text-right">P&L</th>
                  <th className="text-right">Signal</th>
                  <th className="text-right">Quality</th>
                  <th className="text-right">FF5 α</th>
                  <th>Regime</th>
                  <th>Exit Reason</th>
                </tr>
              </thead>
              <tbody>
                {data.trade_log.map((t, i) => (
                  <tr key={i}>
                    <td className="font-mono text-text-primary">{t.ticker}</td>
                    <td className="text-text-muted text-micro">{formatDate(t.entry_date)}</td>
                    <td className="text-text-muted text-micro">{formatDate(t.exit_date)}</td>
                    <td className={cn('text-right font-mono', t.pnl >= 0 ? 'text-positive' : 'text-negative')}>
                      {formatPct(t.pnl_pct * 100)}
                    </td>
                    <td className="text-right font-mono text-text-muted">{t.signal_score.toFixed(2)}</td>
                    <td className="text-right font-mono text-text-muted">{t.quality_score.toFixed(2)}</td>
                    <td className={cn('text-right font-mono', t.ff5_alpha >= 0 ? 'text-positive' : 'text-negative')}>
                      {formatPct(t.ff5_alpha * 100)}
                    </td>
                    <td className="text-micro text-text-muted">{t.macro_regime}</td>
                    <td className="text-micro text-text-muted">{t.exit_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default function BacktestPage() {
  const [running, setRunning] = useState(false)
  const [selectedRun, setSelectedRun] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { data: runs, mutate } = useSWR<BacktestRun[]>('backtest-runs', () => api.getBacktestRuns(), { refreshInterval: 10_000 })

  async function handleRun(cfg: BacktestConfig) {
    setRunning(true)
    setError(null)
    try {
      const { run_id } = await api.triggerBacktest(cfg)
      setSelectedRun(run_id)
      await mutate()
    } catch {
      setError('Failed to start backtest. Check backend.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-page-header font-bold text-text-primary">Backtest Explorer</h1>
        <p className="text-text-muted text-table mt-1">Replay 2018–2023 earnings events with configurable signal and RL settings</p>
      </div>

      {error && (
        <div className="bg-negative/10 border border-negative/30 rounded-md px-4 py-2">
          <p className="text-micro text-negative">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1">
          <RunConfigPanel onSubmit={handleRun} loading={running} />
        </div>
        <div className="lg:col-span-2">
          <RunHistory runs={runs ?? []} selected={selectedRun} onSelect={setSelectedRun} />
        </div>
      </div>

      {selectedRun && <RunResults runId={selectedRun} />}
    </div>
  )
}
