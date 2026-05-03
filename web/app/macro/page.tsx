'use client'

import useSWR from 'swr'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts'
import { api, YieldCurve, InflationData, CreditRiskData, GDPPoint, MacroRegime, CarryData } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'
import { LoadingSkeleton } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn, macroScoreColor, formatDateTime } from '@/lib/utils'

interface TooltipPayload {
  value: number
  name: string
  color: string
}

interface ChartTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string
  suffix?: string
}

function ChartTooltip({ active, payload, label, suffix = '' }: ChartTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface border border-border rounded-lg p-3 shadow-xl">
      <p className="text-micro text-text-muted mb-1">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2 text-micro">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-text-muted">{entry.name}:</span>
          <span className="font-mono text-text-primary">{Number(entry.value).toFixed(2)}{suffix}</span>
        </div>
      ))}
    </div>
  )
}

function YieldCurvePanel() {
  const { data, isLoading } = useSWR<YieldCurve>(
    'yield-curve',
    () => api.getYieldCurve(),
    { refreshInterval: 300_000 }
  )

  if (isLoading) return <LoadingSkeleton className="h-72 w-full" />
  if (!data) return <EmptyState title="No yield curve data" />

  const spreadBps = Math.round(data.spread_10y_2y * 100)
  const isInverted = data.spread_10y_2y < 0

  const curveData = data.nominal.map((n, i) => ({
    maturity: n.maturity,
    Nominal: n.yield,
    Real: data.real[i]?.yield,
  }))

  const spreadHistory = data.spread_history.map((d) => ({
    date: d.date.split('T')[0],
    Spread: d.spread * 100,
  }))

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-card-title font-semibold text-text-primary">Yield Curve</h2>
        <div className="flex items-center gap-2">
          <span className="text-micro text-text-muted">10Y-2Y Spread:</span>
          <span className={cn('font-mono text-table font-semibold', isInverted ? 'text-negative' : 'text-positive')}>
            {spreadBps >= 0 ? '+' : ''}{spreadBps} bps
          </span>
          {isInverted && <Badge variant="negative">INVERTED</Badge>}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={curveData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
          <XAxis dataKey="maturity" tick={{ fill: '#6B7280', fontSize: 11 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
          <YAxis tick={{ fill: '#6B7280', fontSize: 11 }} axisLine={{ stroke: '#222222' }} tickLine={false} tickFormatter={(v: number) => `${v.toFixed(1)}%`} />
          <Tooltip content={<ChartTooltip suffix="%" />} />
          <Line type="monotone" dataKey="Nominal" stroke="#3B82F6" strokeWidth={2} dot={{ r: 3 }} />
          <Line type="monotone" dataKey="Real" stroke="#6B7280" strokeWidth={1.5} strokeDasharray="4 4" dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>

      <div>
        <p className="text-micro text-text-muted mb-2">10Y-2Y Spread History</p>
        <ResponsiveContainer width="100%" height={120}>
          <AreaChart data={spreadHistory} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="spreadGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#EF4444" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
            <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
            <Tooltip content={<ChartTooltip suffix=" bps" />} />
            <ReferenceLine y={0} stroke="#EF4444" strokeDasharray="4 4" />
            <Area type="monotone" dataKey="Spread" stroke="#EF4444" strokeWidth={1.5} fill="url(#spreadGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function InflationPanel() {
  const { data, isLoading } = useSWR<InflationData>(
    'inflation',
    () => api.getInflation(),
    { refreshInterval: 300_000 }
  )

  if (isLoading) return <LoadingSkeleton className="h-64 w-full" />
  if (!data) return <EmptyState title="No inflation data" />

  const pceLine = data.core_pce.map((d) => ({ date: d.date.split('T')[0], 'Core PCE YoY': d.value }))
  const cpiLine = data.cpi.map((d) => ({ date: d.date.split('T')[0], 'CPI YoY': d.value }))

  return (
    <div className="space-y-4">
      <h2 className="text-card-title font-semibold text-text-primary">Inflation Indicators</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Core PCE */}
        <div>
          <div className="flex items-baseline gap-2 mb-3">
            <span className="text-3xl font-mono font-bold text-text-primary">
              {data.current_core_pce.toFixed(1)}%
            </span>
            <span className="text-micro text-text-muted">Core PCE YoY</span>
          </div>
          <ResponsiveContainer width="100%" height={150}>
            <LineChart data={pceLine} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} tickFormatter={(v: number) => `${v}%`} />
              <Tooltip content={<ChartTooltip suffix="%" />} />
              <ReferenceLine y={2} stroke="#F59E0B" strokeDasharray="4 4" label={{ value: '2% target', fill: '#F59E0B', fontSize: 10 }} />
              <Line type="monotone" dataKey="Core PCE YoY" stroke="#3B82F6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* CPI */}
        <div>
          <div className="flex items-baseline gap-2 mb-3">
            <span className="text-3xl font-mono font-bold text-text-primary">
              {data.current_cpi.toFixed(1)}%
            </span>
            <span className="text-micro text-text-muted">CPI YoY</span>
          </div>
          <ResponsiveContainer width="100%" height={150}>
            <LineChart data={cpiLine} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} tickFormatter={(v: number) => `${v}%`} />
              <Tooltip content={<ChartTooltip suffix="%" />} />
              <ReferenceLine y={2} stroke="#F59E0B" strokeDasharray="4 4" label={{ value: '2% target', fill: '#F59E0B', fontSize: 10 }} />
              <Line type="monotone" dataKey="CPI YoY" stroke="#22C55E" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

function CreditRiskPanel() {
  const { data, isLoading } = useSWR<CreditRiskData>(
    'credit-risk',
    () => api.getCreditRisk(),
    { refreshInterval: 300_000 }
  )

  if (isLoading) return <LoadingSkeleton className="h-64 w-full" />
  if (!data) return <EmptyState title="No credit/risk data" />

  const hyData = data.hy_oas.map((d) => ({ date: d.date.split('T')[0], 'HY OAS': d.value }))
  const vixData = data.vix.map((d) => ({ date: d.date.split('T')[0], VIX: d.value }))
  const hyElevated = data.current_hy_oas > 500
  const vixElevated = data.current_vix > 30

  return (
    <div className="space-y-4">
      <h2 className="text-card-title font-semibold text-text-primary">Credit & Risk</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* HY OAS */}
        <div>
          <div className="flex items-baseline gap-2 mb-3">
            <span className={cn('text-3xl font-mono font-bold', hyElevated ? 'text-warning' : 'text-text-primary')}>
              {data.current_hy_oas.toFixed(0)}
            </span>
            <span className="text-micro text-text-muted">HY OAS (bps)</span>
            {hyElevated && <Badge variant="warning">&gt;500bps</Badge>}
          </div>
          <ResponsiveContainer width="100%" height={150}>
            <AreaChart data={hyData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="hyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
              <Tooltip content={<ChartTooltip suffix=" bps" />} />
              <ReferenceLine y={500} stroke="#F59E0B" strokeDasharray="4 4" />
              <Area type="monotone" dataKey="HY OAS" stroke="#F59E0B" strokeWidth={1.5} fill="url(#hyGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* VIX */}
        <div>
          <div className="flex items-baseline gap-2 mb-3">
            <span className={cn('text-3xl font-mono font-bold', vixElevated ? 'text-negative' : 'text-text-primary')}>
              {data.current_vix.toFixed(1)}
            </span>
            <span className="text-micro text-text-muted">VIX</span>
            {vixElevated && <Badge variant="negative">&gt;30</Badge>}
          </div>
          <ResponsiveContainer width="100%" height={150}>
            <LineChart data={vixData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
              <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine y={30} stroke="#EF4444" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="VIX" stroke="#EF4444" strokeWidth={1.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

function GDPPanel() {
  const { data, isLoading } = useSWR<GDPPoint[]>(
    'gdp-data',
    () => api.getGDPData(),
    { refreshInterval: 300_000 }
  )
  const { data: macro } = useSWR<MacroRegime>('macro-regime', () => api.getMacroRegime())

  if (isLoading) return <LoadingSkeleton className="h-48 w-full" />

  // Find Sahm Rule signal
  const sahmSignal = macro?.signals.find((s) => s.name === 'sahm_rule')
  const sahmTriggered = sahmSignal?.status === 'adverse'

  return (
    <div className="space-y-4">
      <h2 className="text-card-title font-semibold text-text-primary">GDP & Employment</h2>

      {/* Sahm Rule */}
      <div className="flex items-center gap-4">
        <div>
          <p className="text-micro text-text-muted mb-1">Sahm Rule</p>
          <span className={cn('text-2xl font-bold font-mono', sahmTriggered ? 'text-negative' : 'text-positive')}>
            {sahmTriggered ? 'TRIGGERED' : 'NORMAL'}
          </span>
        </div>
        {sahmSignal && (
          <div className="text-right">
            <p className="text-micro text-text-muted">Reading</p>
            <span className="font-mono text-xl text-text-primary">{sahmSignal.current_value.toFixed(2)}</span>
          </div>
        )}
      </div>

      {/* GDP Bar chart */}
      {data && data.length > 0 ? (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
            <XAxis dataKey="quarter" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
            <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} tickFormatter={(v: number) => `${v}%`} />
            <Tooltip content={<ChartTooltip suffix="%" />} />
            <ReferenceLine y={0} stroke="#222222" />
            <Bar dataKey="real_gdp_qoq" name="Real GDP QoQ" radius={[2, 2, 0, 0]}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.real_gdp_qoq >= 0 ? '#22C55E' : '#EF4444'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState title="No GDP data available" />
      )}
    </div>
  )
}

function MacroCompositePanel() {
  const { data, isLoading } = useSWR<MacroRegime>(
    'macro-regime',
    () => api.getMacroRegime(),
    { refreshInterval: 30_000 }
  )

  if (isLoading) return <LoadingSkeleton className="h-64 w-full" />
  if (!data) return <EmptyState title="No macro composite data" />

  const scoreColor = macroScoreColor(data.composite_score)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-card-title font-semibold text-text-primary">Composite Macro Score</h2>
        {data.halted && <Badge variant="negative" className="text-sm">HALTED</Badge>}
      </div>

      <div className="flex items-center gap-6">
        <span className={cn('text-7xl font-mono font-bold', scoreColor)}>
          {data.composite_score}
        </span>
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span
              className={cn(
                'w-4 h-4 rounded-full',
                data.composite_score >= 0 ? 'bg-positive' : data.composite_score >= -2 ? 'bg-warning' : 'bg-negative'
              )}
            />
            <span className="text-body text-text-muted">
              {data.composite_score >= 0 ? 'Favorable' : data.composite_score >= -2 ? 'Caution' : 'Adverse'}
            </span>
          </div>
          <p className="text-table text-text-muted">
            Sizing multiplier:{' '}
            <span className="font-mono text-text-primary font-semibold">{data.sizing_multiplier.toFixed(2)}x</span>
          </p>
          <p className="text-micro text-text-muted/60 mt-1">Updated {formatDateTime(data.last_updated)}</p>
        </div>
      </div>

      {/* Signal breakdown table */}
      <table className="w-full">
        <thead>
          <tr>
            <th>Signal</th>
            <th className="text-right">Current</th>
            <th className="text-right">Threshold</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {data.signals.map((sig) => (
            <tr key={sig.name}>
              <td className="text-text-primary">{sig.label}</td>
              <td className="text-right font-mono">{sig.current_value.toFixed(3)}</td>
              <td className="text-right font-mono text-text-muted">{sig.threshold.toFixed(3)}</td>
              <td>
                <Badge variant={sig.status === 'adverse' ? 'negative' : 'positive'}>
                  {sig.status.toUpperCase()}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CarryOverlayPanel() {
  const { data, isLoading } = useSWR<CarryData>(
    'carry-overlay',
    () => api.getCarryOverlay(),
    { refreshInterval: 300_000 }
  )

  if (isLoading) return <LoadingSkeleton className="h-48 w-full" />
  if (!data) return <EmptyState title="No carry overlay data" />

  const chartData = data.jpy_aud.map((d) => ({
    date: d.date.split('T')[0],
    'JPY/AUD 14d RoC': d.value,
  }))

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-card-title font-semibold text-text-primary">Carry Overlay (JPY/AUD)</h2>
        <Badge variant={data.triggered ? 'negative' : 'positive'}>
          {data.triggered ? 'CARRY UNWIND ALERT' : 'NORMAL'}
        </Badge>
      </div>
      <p className="text-micro text-text-muted">
        14-day RoC: <span className={cn('font-mono', data.current_rate_of_change < data.threshold ? 'text-negative' : 'text-text-primary')}>
          {data.current_rate_of_change.toFixed(2)}%
        </span>
        {' · '}
        Threshold: <span className="font-mono text-text-muted">{data.threshold.toFixed(2)}%</span>
      </p>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
          <XAxis dataKey="date" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} tickFormatter={(v: number) => `${v}%`} />
          <Tooltip content={<ChartTooltip suffix="%" />} />
          <ReferenceLine y={data.threshold} stroke="#EF4444" strokeDasharray="4 4" label={{ value: 'Alert', fill: '#EF4444', fontSize: 10 }} />
          <ReferenceLine y={0} stroke="#222222" />
          <Line type="monotone" dataKey="JPY/AUD 14d RoC" stroke="#3B82F6" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function MacroPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-page-header font-bold text-text-primary">Macro Dashboard</h1>
        <p className="text-text-muted text-table mt-1">Macroeconomic indicators and regime analysis</p>
      </div>

      {/* Yield curve - full width */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <YieldCurvePanel />
      </div>

      {/* Inflation */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <InflationPanel />
      </div>

      {/* Credit & Risk */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <CreditRiskPanel />
      </div>

      {/* GDP & Employment */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <GDPPanel />
      </div>

      {/* Composite score - full width */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <MacroCompositePanel />
      </div>

      {/* Carry overlay */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <CarryOverlayPanel />
      </div>
    </div>
  )
}
