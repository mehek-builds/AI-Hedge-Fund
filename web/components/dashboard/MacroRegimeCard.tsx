'use client'

import useSWR from 'swr'
import { api, MacroRegime, MacroSignal } from '@/lib/api'
import { cn, macroScoreColor, formatDateTime } from '@/lib/utils'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/LoadingSpinner'

function SignalRow({ signal }: { signal: MacroSignal }) {
  const isAdverse = signal.status === 'adverse'
  return (
    <div className="flex items-center justify-between py-1.5">
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'w-1.5 h-1.5 rounded-full flex-shrink-0',
            isAdverse ? 'bg-negative' : 'bg-positive'
          )}
        />
        <span className="text-micro text-text-muted">{signal.label}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="font-mono text-micro text-text-primary">
          {signal.current_value.toFixed(2)}
        </span>
        <span className="text-micro text-border">vs</span>
        <span className="font-mono text-micro text-text-muted">
          {signal.threshold.toFixed(2)}
        </span>
        <span
          className={cn(
            'w-1.5 h-1.5 rounded-full',
            isAdverse ? 'bg-negative' : 'bg-positive'
          )}
        />
      </div>
    </div>
  )
}

export function MacroRegimeCard() {
  const { data, error, isLoading } = useSWR<MacroRegime>(
    'macro-regime',
    () => api.getMacroRegime(),
    { refreshInterval: 30_000 }
  )

  if (isLoading) return <CardSkeleton />
  if (error) {
    return (
      <div className="bg-surface border border-border rounded-lg p-4">
        <p className="text-micro text-negative">Failed to load macro regime data</p>
      </div>
    )
  }
  if (!data) return null

  const scoreColor = macroScoreColor(data.composite_score)

  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-card-title font-semibold text-text-primary">Macro Regime</h2>
        {data.halted && (
          <Badge variant="negative" className="text-sm font-bold px-3 py-1">
            HALTED
          </Badge>
        )}
      </div>

      {/* Composite score */}
      <div className="flex items-center gap-3 mb-4">
        <span className={cn('text-5xl font-mono font-bold', scoreColor)}>
          {data.composite_score}
        </span>
        <div className="flex flex-col gap-1">
          <span
            className={cn(
              'w-3 h-3 rounded-full',
              data.composite_score >= 0
                ? 'bg-positive'
                : data.composite_score >= -2
                ? 'bg-warning'
                : 'bg-negative'
            )}
          />
          <span className="text-micro text-text-muted">
            Sizing: <span className="font-mono text-text-primary">{data.sizing_multiplier.toFixed(2)}x</span>
          </span>
        </div>
      </div>

      {/* Signal grid */}
      <div className="border-t border-border pt-3">
        <p className="text-micro text-text-muted uppercase tracking-wider mb-2">Signals</p>
        <div className="divide-y divide-border/50">
          {data.signals.map((signal) => (
            <SignalRow key={signal.name} signal={signal} />
          ))}
        </div>
      </div>

      {/* Last updated */}
      <p className="text-micro text-text-muted/60 mt-3">
        Updated {formatDateTime(data.last_updated)}
      </p>
    </div>
  )
}
