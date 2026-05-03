'use client'

import { useState } from 'react'
import useSWR from 'swr'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { api, Position, ClosedPosition, PerformanceStats, SectorBreakdown } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'
import { StatCard } from '@/components/ui/StatCard'
import { TableSkeleton, CardSkeleton } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn, pnlColor, formatCurrency, formatPct, formatDate } from '@/lib/utils'

type SortKey = keyof Position
type SortDir = 'asc' | 'desc'

function PositionDetailDrawer({ position, open, onClose }: { position: Position | null; open: boolean; onClose: () => void }) {
  if (!position) return null

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-40" />
        <Dialog.Content className="fixed right-0 top-0 h-full w-full max-w-xl bg-surface border-l border-border z-50 overflow-y-auto p-6 focus:outline-none">
          <div className="flex items-center justify-between mb-6">
            <div>
              <Dialog.Title className="text-page-header font-bold font-mono text-text-primary">
                {position.ticker}
              </Dialog.Title>
              <p className="text-micro text-text-muted">{position.sector} · {position.intangible_tier}</p>
            </div>
            <Dialog.Close asChild>
              <button className="p-2 rounded hover:bg-border/50 text-text-muted transition-colors">
                <X size={18} />
              </button>
            </Dialog.Close>
          </div>

          {/* P&L summary */}
          <div className="grid grid-cols-2 gap-3 mb-6">
            <StatCard
              title="Unrealized P&L"
              value={formatCurrency(position.unrealized_pnl)}
              color={position.unrealized_pnl > 0 ? 'positive' : position.unrealized_pnl < 0 ? 'negative' : 'default'}
            />
            <StatCard
              title="P&L %"
              value={formatPct(position.unrealized_pnl_pct)}
              color={position.unrealized_pnl_pct > 0 ? 'positive' : position.unrealized_pnl_pct < 0 ? 'negative' : 'default'}
            />
          </div>

          {/* Price chart placeholder */}
          <div className="bg-background border border-border rounded-lg p-4 mb-6">
            <h3 className="text-table font-semibold text-text-muted mb-3">Price (90 days)</h3>
            <div className="h-40 flex items-center justify-center">
              <p className="text-micro text-text-muted">
                Price chart — connect <span className="font-mono">/api/v1/positions/{position.ticker}/price-history</span>
              </p>
            </div>
          </div>

          {/* Signal breakdown */}
          <div className="bg-background border border-border rounded-lg p-4 mb-6">
            <h3 className="text-table font-semibold text-text-muted mb-3">Signal Breakdown</h3>
            <div className="space-y-2">
              {[
                { label: 'Signal Score', value: position.signal_score },
                { label: 'RL Action Size', value: position.unrealized_pnl_pct / 100 },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between items-center">
                  <span className="text-micro text-text-muted">{label}</span>
                  <span className={cn('font-mono text-table', pnlColor(value))}>
                    {value >= 0 ? '+' : ''}{value.toFixed(4)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Key levels */}
          <div className="bg-background border border-border rounded-lg p-4">
            <h3 className="text-table font-semibold text-text-muted mb-3">Key Levels</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-micro text-text-muted">Entry</span>
                <span className="font-mono text-table text-text-primary">${position.entry_price.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-micro text-text-muted">Current</span>
                <span className="font-mono text-table text-text-primary">${position.current_price.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-micro text-text-muted">Stop</span>
                <span className="font-mono text-table text-negative">${position.stop_level.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-micro text-text-muted">% to Stop</span>
                <span className="font-mono text-table text-warning">{formatPct(position.pct_to_stop)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-micro text-text-muted">Days Held</span>
                <span className="font-mono text-table text-text-primary">{position.days_held}</span>
              </div>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function OpenPositionsTable() {
  const { data, isLoading } = useSWR<Position[]>(
    'positions',
    () => api.getPositions(),
    { refreshInterval: 30_000 }
  )
  const [sortKey, setSortKey] = useState<SortKey>('unrealized_pnl_pct')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [selectedPos, setSelectedPos] = useState<Position | null>(null)

  const sorted = [...(data ?? [])].sort((a, b) => {
    const av = a[sortKey]
    const bv = b[sortKey]
    const cmp = typeof av === 'number' && typeof bv === 'number'
      ? av - bv
      : String(av).localeCompare(String(bv))
    return sortDir === 'asc' ? cmp : -cmp
  })

  function handleSort(key: SortKey) {
    if (key === sortKey) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  function SortHeader({ label, field }: { label: string; field: SortKey }) {
    return (
      <th
        className="cursor-pointer select-none hover:text-text-primary transition-colors"
        onClick={() => handleSort(field)}
      >
        <span className="flex items-center gap-1">
          {label}
          {sortKey === field && (sortDir === 'asc' ? ' ↑' : ' ↓')}
        </span>
      </th>
    )
  }

  return (
    <>
      <div className="bg-surface border border-border rounded-lg">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-card-title font-semibold text-text-primary">Open Positions</h2>
        </div>
        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="p-4"><TableSkeleton rows={6} /></div>
          ) : sorted.length === 0 ? (
            <EmptyState title="No open positions" />
          ) : (
            <table className="w-full">
              <thead>
                <tr>
                  <SortHeader label="Ticker" field="ticker" />
                  <SortHeader label="Entry Date" field="entry_date" />
                  <th className="text-right">Entry</th>
                  <th className="text-right">Current</th>
                  <SortHeader label="P&L" field="unrealized_pnl" />
                  <SortHeader label="P&L %" field="unrealized_pnl_pct" />
                  <SortHeader label="Days" field="days_held" />
                  <th className="text-right">Stop</th>
                  <th className="text-right">% to Stop</th>
                  <th>Signal</th>
                  <th>Sector</th>
                  <th>Tier</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((pos) => (
                  <tr
                    key={pos.ticker}
                    className="cursor-pointer"
                    onClick={() => setSelectedPos(pos)}
                  >
                    <td><span className="font-mono font-bold text-text-primary">{pos.ticker}</span></td>
                    <td className="text-text-muted">{formatDate(pos.entry_date)}</td>
                    <td className="text-right font-mono">${pos.entry_price.toFixed(2)}</td>
                    <td className="text-right font-mono">${pos.current_price.toFixed(2)}</td>
                    <td className={cn('text-right font-mono', pnlColor(pos.unrealized_pnl))}>
                      {formatCurrency(pos.unrealized_pnl)}
                    </td>
                    <td className={cn('text-right font-mono', pnlColor(pos.unrealized_pnl_pct))}>
                      {formatPct(pos.unrealized_pnl_pct)}
                    </td>
                    <td className="text-right text-text-muted">{pos.days_held}d</td>
                    <td className="text-right font-mono text-text-muted">${pos.stop_level.toFixed(2)}</td>
                    <td className={cn('text-right font-mono', pnlColor(-pos.pct_to_stop))}>
                      {formatPct(pos.pct_to_stop)}
                    </td>
                    <td className={cn('font-mono text-micro', pnlColor(pos.signal_score))}>
                      {pos.signal_score.toFixed(3)}
                    </td>
                    <td>
                      <Badge variant="muted">{pos.sector}</Badge>
                    </td>
                    <td className="text-text-muted text-micro">{pos.intangible_tier}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
      <PositionDetailDrawer
        position={selectedPos}
        open={!!selectedPos}
        onClose={() => setSelectedPos(null)}
      />
    </>
  )
}

const exitReasonVariant: Record<ClosedPosition['exit_reason'], 'negative' | 'muted' | 'warning' | 'neutral'> = {
  STOP: 'negative',
  EXPIRY: 'muted',
  REVERSAL: 'warning',
  MANUAL: 'neutral',
}

function ClosedPositionsTable() {
  const { data, isLoading } = useSWR<ClosedPosition[]>(
    'closed-positions',
    () => api.getClosedPositions(),
    { refreshInterval: 300_000 }
  )

  return (
    <div className="bg-surface border border-border rounded-lg">
      <div className="px-4 py-3 border-b border-border">
        <h2 className="text-card-title font-semibold text-text-primary">Closed Positions</h2>
      </div>
      <div className="overflow-x-auto">
        {isLoading ? (
          <div className="p-4"><TableSkeleton rows={8} /></div>
        ) : !data || data.length === 0 ? (
          <EmptyState title="No closed positions" />
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Entry</th>
                <th>Exit</th>
                <th className="text-right">Hold (d)</th>
                <th className="text-right">P&L</th>
                <th className="text-right">P&L %</th>
                <th className="text-right">FF5 Alpha</th>
                <th>Exit Reason</th>
              </tr>
            </thead>
            <tbody>
              {data.map((pos) => (
                <tr key={`${pos.ticker}-${pos.exit_date}`}>
                  <td><span className="font-mono font-bold text-text-primary">{pos.ticker}</span></td>
                  <td className="text-text-muted">{formatDate(pos.entry_date)}</td>
                  <td className="text-text-muted">{formatDate(pos.exit_date)}</td>
                  <td className="text-right text-text-muted">{pos.holding_period}</td>
                  <td className={cn('text-right font-mono', pnlColor(pos.pnl))}>
                    {formatCurrency(pos.pnl)}
                  </td>
                  <td className={cn('text-right font-mono', pnlColor(pos.pnl_pct))}>
                    {formatPct(pos.pnl_pct)}
                  </td>
                  <td className={cn('text-right font-mono', pnlColor(pos.ff5_alpha))}>
                    {pos.ff5_alpha >= 0 ? '+' : ''}{pos.ff5_alpha.toFixed(4)}
                  </td>
                  <td>
                    <Badge variant={exitReasonVariant[pos.exit_reason]}>
                      {pos.exit_reason}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function PerformanceAnalytics() {
  const { data: stats, isLoading: statsLoading } = useSWR<PerformanceStats>(
    'performance-stats',
    () => api.getPerformanceStats(),
    { refreshInterval: 300_000 }
  )
  const { data: sectors, isLoading: sectorsLoading } = useSWR<SectorBreakdown[]>(
    'sector-breakdown',
    () => api.getSectorBreakdown(),
    { refreshInterval: 300_000 }
  )

  return (
    <div className="space-y-4">
      <h2 className="text-card-title font-semibold text-text-primary">Performance Analytics</h2>
      {statsLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="Win Rate" value={`${stats.win_rate.toFixed(1)}%`} />
          <StatCard title="Avg Hold Days" value={`${stats.avg_hold_days.toFixed(1)}d`} />
          <StatCard
            title="Avg FF5 Alpha"
            value={`${stats.avg_ff5_alpha >= 0 ? '+' : ''}${stats.avg_ff5_alpha.toFixed(4)}`}
            color={stats.avg_ff5_alpha > 0 ? 'positive' : 'negative'}
          />
          <StatCard title="Best Sector" value={stats.best_sector} />
        </div>
      ) : null}

      {/* Sector breakdown */}
      <div className="bg-surface border border-border rounded-lg">
        <div className="px-4 py-3 border-b border-border">
          <h3 className="text-body font-semibold text-text-primary">Sector Breakdown</h3>
        </div>
        <div className="overflow-x-auto">
          {sectorsLoading ? (
            <div className="p-4"><TableSkeleton rows={5} /></div>
          ) : !sectors || sectors.length === 0 ? (
            <EmptyState title="No sector data" />
          ) : (
            <table className="w-full">
              <thead>
                <tr>
                  <th>Sector</th>
                  <th className="text-right">Trades</th>
                  <th className="text-right">Win Rate</th>
                  <th className="text-right">Avg P&L</th>
                  <th className="text-right">Total P&L</th>
                </tr>
              </thead>
              <tbody>
                {sectors.map((s) => (
                  <tr key={s.sector}>
                    <td className="text-text-primary">{s.sector}</td>
                    <td className="text-right text-text-muted">{s.n_trades}</td>
                    <td className={cn('text-right font-mono', pnlColor(s.win_rate - 50))}>
                      {s.win_rate.toFixed(1)}%
                    </td>
                    <td className={cn('text-right font-mono', pnlColor(s.avg_pnl))}>
                      {formatPct(s.avg_pnl)}
                    </td>
                    <td className={cn('text-right font-mono', pnlColor(s.total_pnl))}>
                      {formatCurrency(s.total_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

export default function PositionsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-page-header font-bold text-text-primary">Positions</h1>
        <p className="text-text-muted text-table mt-1">Open and closed position management</p>
      </div>

      <OpenPositionsTable />
      <ClosedPositionsTable />
      <PerformanceAnalytics />
    </div>
  )
}
