'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { format, parseISO, isToday, isTomorrow, addDays, isAfter, isBefore } from 'date-fns'
import * as Select from '@radix-ui/react-select'
import { ChevronDown, ChevronUp, Check } from 'lucide-react'
import { api, EarningsEvent, SignalHistoryItem } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'
import { LoadingSkeleton, TableSkeleton } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn, pnlColor, formatDate } from '@/lib/utils'

function dayLabel(dateStr: string): string {
  const date = parseISO(dateStr)
  if (isToday(date)) return 'Today'
  if (isTomorrow(date)) return 'Tomorrow'
  return format(date, 'EEE, MMM d')
}

function EarningsCard({ event }: { event: EarningsEvent }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-background border border-border rounded-lg p-3">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <span className="font-mono font-bold text-body text-text-primary">{event.ticker}</span>
          <Badge variant="muted">{event.sector}</Badge>
          <Badge variant={event.report_time === 'BMO' ? 'primary' : 'warning'}>
            {event.report_time}
          </Badge>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-micro text-text-muted">EPS Est.</p>
            <p className="font-mono text-table text-text-primary">${event.consensus_eps.toFixed(2)}</p>
          </div>
          <div className="text-right">
            <p className="text-micro text-text-muted">Implied</p>
            <p className="font-mono text-table text-text-primary">${event.implied_eps.toFixed(2)}</p>
          </div>
          {expanded ? <ChevronUp size={16} className="text-text-muted" /> : <ChevronDown size={16} className="text-text-muted" />}
        </div>
      </div>

      {expanded && event.signal_breakdown && (
        <div className="mt-3 pt-3 border-t border-border grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Surprise Score', value: event.signal_breakdown.surprise_score },
            { label: 'Intangible Score', value: event.signal_breakdown.intangible_score },
            { label: 'ROIC Score', value: event.signal_breakdown.roic_score },
            { label: 'Momentum Score', value: event.signal_breakdown.momentum_score },
          ].map(({ label, value }) => (
            <div key={label} className="text-center bg-surface rounded p-2">
              <p className="text-micro text-text-muted">{label}</p>
              <p className={cn('font-mono font-semibold text-body', pnlColor(value))}>
                {value >= 0 ? '+' : ''}{value.toFixed(3)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function EarningsCalendar() {
  const { data, isLoading } = useSWR<EarningsEvent[]>(
    'earnings-calendar',
    () => api.getEarningsCalendar(),
    { refreshInterval: 300_000 }
  )

  if (isLoading) return <LoadingSkeleton className="h-48 w-full" />
  if (!data || data.length === 0) {
    return <EmptyState title="No upcoming earnings" description="Earnings events will appear here" />
  }

  // Group by date, next 5 days
  const now = new Date()
  const cutoff = addDays(now, 5)
  const filtered = data.filter((e) => {
    const d = parseISO(e.date)
    return isAfter(d, now) || isToday(d)
  }).filter((e) => isBefore(parseISO(e.date), cutoff))

  const grouped = filtered.reduce<Record<string, EarningsEvent[]>>((acc, ev) => {
    const key = ev.date.split('T')[0]
    if (!acc[key]) acc[key] = []
    acc[key].push(ev)
    return acc
  }, {})

  return (
    <div className="space-y-4">
      {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([date, events]) => (
        <div key={date}>
          <h3 className="text-table font-semibold text-text-muted mb-2 uppercase tracking-wider">
            {dayLabel(date)}
          </h3>
          <div className="space-y-2">
            {events.map((ev) => <EarningsCard key={ev.ticker} event={ev} />)}
          </div>
        </div>
      ))}
    </div>
  )
}

function SignalCard({ signal }: { signal: { ticker: string; surprise_score: number; direction: 'LONG' | 'SHORT' | 'NO_TRADE'; intangible_multiplier: number; roic_multiplier: number; rl_action_size: number; proposed_position_size_pct: number; sector: string } }) {
  const directionVariant: Record<string, 'positive' | 'negative' | 'muted'> = {
    LONG: 'positive',
    SHORT: 'negative',
    NO_TRADE: 'muted',
  }

  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono font-bold text-body text-text-primary">{signal.ticker}</span>
        <Badge variant={directionVariant[signal.direction]}>{signal.direction.replace('_', ' ')}</Badge>
      </div>

      <div className="mb-3">
        <p className="text-micro text-text-muted mb-0.5">Surprise Score</p>
        <p className={cn('font-mono text-3xl font-bold', pnlColor(signal.surprise_score))}>
          {signal.surprise_score >= 0 ? '+' : ''}{signal.surprise_score.toFixed(3)}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="bg-background rounded p-2">
          <p className="text-micro text-text-muted">Intangible</p>
          <p className="font-mono text-table text-text-primary">{signal.intangible_multiplier.toFixed(2)}x</p>
        </div>
        <div className="bg-background rounded p-2">
          <p className="text-micro text-text-muted">ROIC</p>
          <p className="font-mono text-table text-text-primary">{signal.roic_multiplier.toFixed(2)}x</p>
        </div>
        <div className="bg-background rounded p-2">
          <p className="text-micro text-text-muted">RL Action</p>
          <p className="font-mono text-table text-text-primary">{signal.rl_action_size.toFixed(3)}</p>
        </div>
        <div className="bg-background rounded p-2">
          <p className="text-micro text-text-muted">Position Size</p>
          <p className="font-mono text-table text-text-primary">{signal.proposed_position_size_pct.toFixed(1)}%</p>
        </div>
      </div>

      <div className="mt-2">
        <Badge variant="muted">{signal.sector}</Badge>
      </div>
    </div>
  )
}

function SignalGrid() {
  const { data, isLoading } = useSWR(
    'signals',
    () => api.getSignals(),
    { refreshInterval: 300_000 }
  )

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => <LoadingSkeleton key={i} className="h-48" />)}
      </div>
    )
  }

  if (!data || data.length === 0) {
    return <EmptyState title="No active signals" description="Post-announcement signals appear here" />
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {data.map((s) => <SignalCard key={`${s.ticker}-${s.date}`} signal={s} />)}
    </div>
  )
}

const SECTORS = ['All', 'Technology', 'Healthcare', 'Financials', 'Consumer Discretionary', 'Industrials', 'Energy', 'Materials', 'Utilities', 'Real Estate', 'Communication Services']

function SignalHistoryTable() {
  const [sectorFilter, setSectorFilter] = useState('All')
  const { data, isLoading } = useSWR<SignalHistoryItem[]>(
    'signal-history',
    () => api.getSignalHistory(),
    { refreshInterval: 300_000 }
  )

  const filtered = data?.filter((item) =>
    sectorFilter === 'All' || item.sector === sectorFilter
  ) ?? []

  return (
    <div className="bg-surface border border-border rounded-lg">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h2 className="text-card-title font-semibold text-text-primary">Signal History</h2>
        <Select.Root value={sectorFilter} onValueChange={setSectorFilter}>
          <Select.Trigger className="flex items-center gap-2 bg-background border border-border rounded px-3 py-1.5 text-micro text-text-primary hover:border-primary transition-colors">
            <Select.Value />
            <Select.Icon><ChevronDown size={14} /></Select.Icon>
          </Select.Trigger>
          <Select.Portal>
            <Select.Content className="bg-surface border border-border rounded-lg shadow-xl z-50 overflow-hidden">
              <Select.Viewport className="p-1">
                {SECTORS.map((s) => (
                  <Select.Item
                    key={s}
                    value={s}
                    className="flex items-center gap-2 px-3 py-2 text-micro text-text-primary hover:bg-border/50 cursor-pointer rounded"
                  >
                    <Select.ItemText>{s}</Select.ItemText>
                    <Select.ItemIndicator><Check size={12} /></Select.ItemIndicator>
                  </Select.Item>
                ))}
              </Select.Viewport>
            </Select.Content>
          </Select.Portal>
        </Select.Root>
      </div>

      <div className="overflow-x-auto">
        {isLoading ? (
          <div className="p-4"><TableSkeleton rows={8} /></div>
        ) : filtered.length === 0 ? (
          <EmptyState title="No signal history" description="Completed signals will appear here" />
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Date</th>
                <th className="text-right">Surprise</th>
                <th>Direction</th>
                <th className="text-right">RL Action</th>
                <th>Entered</th>
                <th className="text-right">Exit P&L</th>
                <th className="text-right">FF5 Alpha</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={`${item.ticker}-${item.date}`}>
                  <td><span className="font-mono font-semibold text-text-primary">{item.ticker}</span></td>
                  <td className="text-text-muted">{formatDate(item.date)}</td>
                  <td className={cn('text-right font-mono', pnlColor(item.surprise_score))}>
                    {item.surprise_score >= 0 ? '+' : ''}{item.surprise_score.toFixed(3)}
                  </td>
                  <td>
                    <Badge variant={item.direction === 'LONG' ? 'positive' : item.direction === 'SHORT' ? 'negative' : 'muted'}>
                      {item.direction.replace('_', ' ')}
                    </Badge>
                  </td>
                  <td className="text-right font-mono text-text-muted">{item.rl_action.toFixed(3)}</td>
                  <td>
                    <Badge variant={item.entered ? 'positive' : 'muted'}>
                      {item.entered ? 'Y' : 'N'}
                    </Badge>
                  </td>
                  <td className={cn('text-right font-mono', item.exit_pnl !== null ? pnlColor(item.exit_pnl) : 'text-text-muted')}>
                    {item.exit_pnl !== null ? `${item.exit_pnl >= 0 ? '+' : ''}${item.exit_pnl.toFixed(2)}%` : '—'}
                  </td>
                  <td className={cn('text-right font-mono', item.ff5_alpha !== null ? pnlColor(item.ff5_alpha) : 'text-text-muted')}>
                    {item.ff5_alpha !== null ? `${item.ff5_alpha >= 0 ? '+' : ''}${item.ff5_alpha.toFixed(3)}` : '—'}
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

export default function SignalsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-page-header font-bold text-text-primary">Signals</h1>
        <p className="text-text-muted text-table mt-1">Earnings calendar and signal feed</p>
      </div>

      {/* Earnings Calendar */}
      <section>
        <h2 className="text-card-title font-semibold text-text-primary mb-4">Earnings Calendar (Next 5 Days)</h2>
        <EarningsCalendar />
      </section>

      {/* Live signal cards */}
      <section>
        <h2 className="text-card-title font-semibold text-text-primary mb-4">Active Signals</h2>
        <SignalGrid />
      </section>

      {/* Signal history */}
      <SignalHistoryTable />
    </div>
  )
}
