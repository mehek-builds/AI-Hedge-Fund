'use client'

import { useState } from 'react'
import useSWR from 'swr'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { api, EquityCurvePoint } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { LoadingSkeleton } from '@/components/ui/LoadingSpinner'

type ViewMode = 'raw' | 'alpha'

interface TooltipPayload {
  value: number
  name: string
  color: string
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface border border-border rounded-lg p-3 shadow-xl">
      <p className="text-micro text-text-muted mb-2">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2 text-micro">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-text-muted">{entry.name}:</span>
          <span className="font-mono text-text-primary font-medium">
            {entry.value >= 0 ? '+' : ''}{entry.value.toFixed(2)}%
          </span>
        </div>
      ))}
    </div>
  )
}

export function EquityCurve() {
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const { data, isLoading } = useSWR<EquityCurvePoint[]>(
    'equity-curve',
    () => api.getEquityCurve(),
    { refreshInterval: 30_000 }
  )

  if (isLoading) return <LoadingSkeleton className="h-64 w-full" />

  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center">
        <p className="text-text-muted text-table">No equity curve data available</p>
      </div>
    )
  }

  const chartData = data.map((d) => ({
    date: formatDate(d.date),
    Portfolio: viewMode === 'raw' ? d.portfolio_return : d.ff5_alpha,
    'S&P 500': viewMode === 'raw' ? d.sp500_return : 0,
  }))

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-card-title font-semibold text-text-primary">Equity Curve</h2>
        <div className="flex rounded-md overflow-hidden border border-border">
          {(['raw', 'alpha'] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={
                viewMode === mode
                  ? 'px-3 py-1.5 text-micro font-medium bg-primary text-white'
                  : 'px-3 py-1.5 text-micro font-medium text-text-muted hover:text-text-primary hover:bg-border/50 transition-colors'
              }
            >
              {mode === 'raw' ? 'Raw Return' : 'FF5 Alpha'}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="portfolioGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="sp500Gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6B7280" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#6B7280" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#6B7280', fontSize: 11 }}
            axisLine={{ stroke: '#222222' }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: '#6B7280', fontSize: 11 }}
            axisLine={{ stroke: '#222222' }}
            tickLine={false}
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: '12px', color: '#6B7280' }}
          />
          <Area
            type="monotone"
            dataKey="Portfolio"
            stroke="#3B82F6"
            strokeWidth={2}
            fill="url(#portfolioGradient)"
          />
          {viewMode === 'raw' && (
            <Area
              type="monotone"
              dataKey="S&P 500"
              stroke="#6B7280"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              fill="url(#sp500Gradient)"
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
