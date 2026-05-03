'use client'

import { useState } from 'react'
import useSWR from 'swr'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts'
import { api, RLEpisode, RLFactors, RLAgentStats, SectorReward } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'
import { LoadingSkeleton, CardSkeleton } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn, pnlColor, formatDateTime } from '@/lib/utils'

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

function ChartTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface border border-border rounded-lg p-3 shadow-xl">
      <p className="text-micro text-text-muted mb-1">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2 text-micro">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-text-muted">{entry.name}:</span>
          <span className="font-mono text-text-primary">{Number(entry.value).toFixed(4)}</span>
        </div>
      ))}
    </div>
  )
}

function RewardCurve() {
  const { data, isLoading } = useSWR<RLEpisode[]>(
    'rl-episodes',
    () => api.getRLEpisodes(),
    { refreshInterval: 300_000 }
  )

  if (isLoading) return <LoadingSkeleton className="h-64 w-full" />
  if (!data || data.length === 0) {
    return <EmptyState title="No training episodes" description="Reward curve appears after training" />
  }

  const chartData = data.map((ep) => ({
    episode: ep.episode,
    'Raw Reward': ep.reward,
    'Smoothed (20)': ep.smoothed_reward,
  }))

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-card-title font-semibold text-text-primary">Reward Curve</h2>
        <p className="text-micro text-text-muted">{data.length.toLocaleString()} episodes</p>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
          <XAxis dataKey="episode" tick={{ fill: '#6B7280', fontSize: 11 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
          <YAxis tick={{ fill: '#6B7280', fontSize: 11 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
          <Tooltip content={<ChartTooltip />} />
          <ReferenceLine y={0} stroke="#222222" />
          <Line
            type="monotone"
            dataKey="Raw Reward"
            stroke="#3B82F6"
            strokeWidth={1}
            dot={false}
            strokeOpacity={0.3}
          />
          <Line
            type="monotone"
            dataKey="Smoothed (20)"
            stroke="#3B82F6"
            strokeWidth={2.5}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function FactorAttribution() {
  const { data, isLoading } = useSWR<RLFactors>(
    'rl-factors',
    () => api.getRLFactors(),
    { refreshInterval: 300_000 }
  )

  if (isLoading) return <LoadingSkeleton className="h-48 w-full" />
  if (!data) return <EmptyState title="No factor data available" />

  const factors = [
    { name: 'MKT-RF', value: data.mkt_rf },
    { name: 'SMB', value: data.smb },
    { name: 'HML', value: data.hml },
    { name: 'RMW', value: data.rmw },
    { name: 'CMA', value: data.cma },
  ]

  return (
    <div>
      <h2 className="text-card-title font-semibold text-text-primary mb-4">FF5 Factor Attribution</h2>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={factors} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
          <XAxis dataKey="name" tick={{ fill: '#6B7280', fontSize: 11 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
          <YAxis tick={{ fill: '#6B7280', fontSize: 11 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
          <Tooltip content={<ChartTooltip />} />
          <ReferenceLine y={0} stroke="#6B7280" />
          <Bar dataKey="value" name="Beta" radius={[2, 2, 0, 0]}>
            {factors.map((f) => (
              <Cell key={f.name} fill={f.value >= 0 ? '#3B82F6' : '#EF4444'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function ActionDistribution({ distribution }: { distribution: { bin: string; count: number }[] }) {
  if (!distribution || distribution.length === 0) {
    return <EmptyState title="No action distribution data" />
  }

  return (
    <div>
      <h2 className="text-card-title font-semibold text-text-primary mb-4">Agent Action Distribution</h2>
      <p className="text-micro text-text-muted mb-3">Last 100 episodes · Position size bins (-1 to 1)</p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={distribution} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#222222" />
          <XAxis dataKey="bin" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
          <YAxis tick={{ fill: '#6B7280', fontSize: 11 }} axisLine={{ stroke: '#222222' }} tickLine={false} />
          <Tooltip content={<ChartTooltip />} />
          <Bar dataKey="count" name="Count" fill="#3B82F6" opacity={0.8} radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function SectorRewardTable({ sectors }: { sectors: SectorReward[] }) {
  if (!sectors || sectors.length === 0) {
    return <EmptyState title="No sector reward data" />
  }

  const minReward = Math.min(...sectors.map((s) => s.avg_reward))
  const maxReward = Math.max(...sectors.map((s) => s.avg_reward))
  const range = maxReward - minReward || 1

  function cellBg(value: number): string {
    if (value > 0) {
      const intensity = Math.min(value / maxReward, 1)
      return `rgba(34, 197, 94, ${0.05 + intensity * 0.25})`
    } else {
      const intensity = Math.min(Math.abs(value) / Math.abs(minReward), 1)
      return `rgba(239, 68, 68, ${0.05 + intensity * 0.25})`
    }
  }

  return (
    <div className="bg-surface border border-border rounded-lg">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-body font-semibold text-text-primary">Sector Reward Breakdown</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th>Sector</th>
              <th className="text-right">Avg Reward</th>
              <th className="text-right">N Trades</th>
              <th className="text-right">Win Rate</th>
            </tr>
          </thead>
          <tbody>
            {sectors.map((s) => (
              <tr key={s.sector}>
                <td className="text-text-primary">{s.sector}</td>
                <td
                  className={cn('text-right font-mono', pnlColor(s.avg_reward))}
                  style={{ backgroundColor: cellBg(s.avg_reward) }}
                >
                  {s.avg_reward >= 0 ? '+' : ''}{s.avg_reward.toFixed(4)}
                </td>
                <td className="text-right text-text-muted">{s.n_trades}</td>
                <td className={cn('text-right font-mono', pnlColor(s.win_rate - 50))}>
                  {s.win_rate.toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function TrainingControls() {
  const [training, setTraining] = useState(false)
  const [lastTriggered, setLastTriggered] = useState<string | null>(null)
  const [trainError, setTrainError] = useState<string | null>(null)
  const { data: stats, isLoading, mutate } = useSWR<RLAgentStats>(
    'rl-agent-stats',
    () => api.getRLAgentStats(),
    { refreshInterval: 60_000 }
  )

  async function handleTrain() {
    setTraining(true)
    setTrainError(null)
    try {
      await api.triggerTraining()
      setLastTriggered(new Date().toISOString())
      await mutate()
    } catch {
      setTrainError('Training trigger failed. Check backend.')
    } finally {
      setTraining(false)
    }
  }

  return (
    <div className="bg-surface border border-border rounded-lg p-4 space-y-4">
      <h2 className="text-card-title font-semibold text-text-primary">Training Controls</h2>

      {isLoading ? (
        <CardSkeleton />
      ) : stats ? (
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-micro text-text-muted">Last Trained</span>
            <span className="text-micro font-mono text-text-primary">
              {formatDateTime(stats.last_trained)}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-micro text-text-muted">Active Model</span>
            <span className="text-micro font-mono text-text-primary truncate max-w-[200px]">
              {stats.model_path}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-micro text-text-muted">Episode Buffer</span>
            <span className="font-mono text-table text-text-primary">{stats.episode_buffer_size.toLocaleString()}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-micro text-text-muted">Total Episodes</span>
            <span className="font-mono text-table text-text-primary">{stats.total_episodes.toLocaleString()}</span>
          </div>
        </div>
      ) : (
        <p className="text-micro text-text-muted">No agent stats available</p>
      )}

      {lastTriggered && (
        <div className="bg-positive/10 border border-positive/30 rounded-md px-3 py-2">
          <p className="text-micro text-positive">
            Training triggered at {formatDateTime(lastTriggered)}
          </p>
        </div>
      )}

      {trainError && (
        <div className="bg-negative/10 border border-negative/30 rounded-md px-3 py-2">
          <p className="text-micro text-negative">{trainError}</p>
        </div>
      )}

      <button
        onClick={handleTrain}
        disabled={training}
        className="w-full bg-primary hover:bg-primary/90 disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-md transition-colors text-table"
      >
        {training ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Training...
          </span>
        ) : (
          'Trigger Retraining'
        )}
      </button>
    </div>
  )
}

export default function RLPage() {
  const { data: stats, isLoading } = useSWR<RLAgentStats>(
    'rl-agent-stats',
    () => api.getRLAgentStats(),
    { refreshInterval: 60_000 }
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-page-header font-bold text-text-primary">RL Training Console</h1>
        <p className="text-text-muted text-table mt-1">Reinforcement learning agent performance and controls</p>
      </div>

      {/* Reward curve - full width */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <RewardCurve />
      </div>

      {/* Factor attribution + Action distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-surface border border-border rounded-lg p-4">
          <FactorAttribution />
        </div>
        <div className="bg-surface border border-border rounded-lg p-4">
          {isLoading ? (
            <LoadingSkeleton className="h-48 w-full" />
          ) : stats?.action_distribution ? (
            <ActionDistribution distribution={stats.action_distribution} />
          ) : (
            <EmptyState title="No action distribution data" />
          )}
        </div>
      </div>

      {/* Sector breakdown + Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          {isLoading ? (
            <CardSkeleton />
          ) : stats?.sector_rewards ? (
            <SectorRewardTable sectors={stats.sector_rewards} />
          ) : (
            <EmptyState title="No sector reward data" />
          )}
        </div>
        <TrainingControls />
      </div>
    </div>
  )
}
