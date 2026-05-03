'use client'

import useSWR from 'swr'
import Link from 'next/link'
import { api, PortfolioSummary, Position, ActivityEvent } from '@/lib/api'
import { StatCard } from '@/components/ui/StatCard'
import { Badge } from '@/components/ui/Badge'
import { MacroRegimeCard } from '@/components/dashboard/MacroRegimeCard'
import { EquityCurve } from '@/components/charts/EquityCurve'
import { CardSkeleton, TableSkeleton } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import {
  formatCurrency,
  formatPct,
  pnlColor,
  formatDate,
  timeAgo,
} from '@/lib/utils'
import { cn } from '@/lib/utils'
import { TrendingUp } from 'lucide-react'

function PortfolioBar() {
  const { data, isLoading } = useSWR<PortfolioSummary>(
    'portfolio-summary',
    () => api.getPortfolioSummary(),
    { refreshInterval: 30_000 }
  )

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <CardSkeleton key={i} />)}
      </div>
    )
  }

  if (!data) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {['Total NAV', 'Daily P&L', 'Daily P&L %', 'Open Positions'].map((title) => (
          <StatCard key={title} title={title} value="—" subtitle="No data" />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard
        title="Total NAV"
        value={formatCurrency(data.total_nav)}
        subtitle={`Cash: ${formatCurrency(data.cash_balance, true)}`}
      />
      <StatCard
        title="Daily P&L"
        value={formatCurrency(data.daily_pnl)}
        color={data.daily_pnl > 0 ? 'positive' : data.daily_pnl < 0 ? 'negative' : 'default'}
      />
      <StatCard
        title="Daily P&L %"
        value={formatPct(data.daily_pnl_pct)}
        color={data.daily_pnl_pct > 0 ? 'positive' : data.daily_pnl_pct < 0 ? 'negative' : 'default'}
        subtitle={`Total: ${formatPct(data.total_return_pct)}`}
      />
      <StatCard
        title="Open Positions"
        value={String(data.open_positions_count)}
        subtitle="Active trades"
      />
    </div>
  )
}

function RLPerformanceStrip() {
  const { data, isLoading } = useSWR(
    'rl-factors',
    () => api.getRLFactors(),
    { refreshInterval: 300_000 }
  )

  if (isLoading) return <CardSkeleton />

  if (!data) {
    return (
      <div className="bg-surface border border-border rounded-lg p-4">
        <p className="text-micro text-text-muted">No RL data available</p>
      </div>
    )
  }

  const factors = [
    { label: 'MKT-RF', value: data.mkt_rf },
    { label: 'SMB', value: data.smb },
    { label: 'HML', value: data.hml },
    { label: 'RMW', value: data.rmw },
    { label: 'CMA', value: data.cma },
  ]

  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <h2 className="text-card-title font-semibold text-text-primary mb-3">FF5 Factor Betas</h2>
      <div className="grid grid-cols-5 gap-2">
        {factors.map(({ label, value }) => (
          <div key={label} className="text-center">
            <p className="text-micro text-text-muted">{label}</p>
            <p className={cn('font-mono font-semibold text-body', pnlColor(value))}>
              {value >= 0 ? '+' : ''}{value.toFixed(3)}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

function OpenPositionsTable() {
  const { data, isLoading } = useSWR<Position[]>(
    'positions',
    () => api.getPositions(),
    { refreshInterval: 30_000 }
  )

  return (
    <div className="bg-surface border border-border rounded-lg">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h2 className="text-card-title font-semibold text-text-primary">Open Positions</h2>
        <Link href="/positions" className="text-micro text-primary hover:text-primary/80 transition-colors">
          View All →
        </Link>
      </div>
      <div className="overflow-x-auto">
        {isLoading ? (
          <div className="p-4"><TableSkeleton rows={5} /></div>
        ) : !data || data.length === 0 ? (
          <EmptyState
            title="No open positions"
            description="Positions will appear here when trades are entered"
            icon={<TrendingUp size={32} />}
          />
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Entry Date</th>
                <th className="text-right">Entry</th>
                <th className="text-right">Current</th>
                <th className="text-right">P&L</th>
                <th className="text-right">P&L %</th>
                <th className="text-right">Days</th>
                <th className="text-right">Stop</th>
              </tr>
            </thead>
            <tbody>
              {data.slice(0, 10).map((pos) => (
                <tr key={pos.ticker}>
                  <td>
                    <span className="font-mono font-semibold text-text-primary">{pos.ticker}</span>
                  </td>
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
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function activityEventColor(type: ActivityEvent['type']): 'positive' | 'negative' | 'warning' | 'muted' {
  switch (type) {
    case 'ENTRY': return 'positive'
    case 'EXIT': return 'muted'
    case 'STOP': return 'negative'
    case 'MACRO_CHANGE': return 'warning'
  }
}

function RecentActivityFeed() {
  const { data, isLoading } = useSWR<ActivityEvent[]>(
    'activity-feed',
    () => api.getActivityFeed(),
    { refreshInterval: 30_000 }
  )

  return (
    <div className="bg-surface border border-border rounded-lg">
      <div className="px-4 py-3 border-b border-border">
        <h2 className="text-card-title font-semibold text-text-primary">Recent Activity</h2>
      </div>
      <div className="p-4">
        {isLoading ? (
          <TableSkeleton rows={6} />
        ) : !data || data.length === 0 ? (
          <EmptyState title="No recent activity" description="Trade events will appear here" />
        ) : (
          <div className="space-y-3">
            {data.slice(0, 10).map((event) => (
              <div key={event.id} className="flex items-start gap-3">
                <Badge variant={activityEventColor(event.type)} className="mt-0.5 flex-shrink-0">
                  {event.type.replace('_', ' ')}
                </Badge>
                <div className="flex-1 min-w-0">
                  <p className="text-table text-text-primary truncate">{event.message}</p>
                  {event.details && (
                    <p className="text-micro text-text-muted truncate">{event.details}</p>
                  )}
                </div>
                <span className="text-micro text-text-muted flex-shrink-0">
                  {timeAgo(event.timestamp)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-page-header font-bold text-text-primary">Dashboard</h1>
        <p className="text-text-muted text-table mt-1">Portfolio overview and system status</p>
      </div>

      {/* Portfolio summary bar */}
      <PortfolioBar />

      {/* Macro + RL strip */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <MacroRegimeCard />
        <RLPerformanceStrip />
      </div>

      {/* Equity curve */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <EquityCurve />
      </div>

      {/* Positions + Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <OpenPositionsTable />
        <RecentActivityFeed />
      </div>
    </div>
  )
}
