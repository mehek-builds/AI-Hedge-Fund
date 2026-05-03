'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { api, AlertEvent, AlertRules, AlertRuleConfig } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'
import { LoadingSkeleton } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn, formatDateTime } from '@/lib/utils'

const ALERT_LABELS: Record<AlertEvent['alert_type'], string> = {
  trade_entry: 'Trade Entry',
  stop_triggered: 'Stop Triggered',
  signal_skip: 'Signal Skip',
  macro_regime_change: 'Macro Regime Change',
  erp_alert: 'ERP Alert',
  carry_crash: 'Carry Crash',
  rl_retrain_complete: 'RL Retrain Complete',
  backtest_complete: 'Backtest Complete',
  ir_degradation: 'IR Degradation',
}

const ALERT_PRIORITY: Record<AlertEvent['alert_type'], 'high' | 'medium' | 'low'> = {
  trade_entry: 'medium',
  stop_triggered: 'high',
  signal_skip: 'low',
  macro_regime_change: 'high',
  erp_alert: 'high',
  carry_crash: 'high',
  rl_retrain_complete: 'medium',
  backtest_complete: 'low',
  ir_degradation: 'high',
}

const DEFAULT_RULES: AlertRules = {
  trade_entry: { enabled: true, channel: 'slack' },
  stop_triggered: { enabled: true, channel: 'both' },
  signal_skip: { enabled: false, channel: 'slack' },
  macro_regime_change: { enabled: true, channel: 'both' },
  erp_alert: { enabled: true, channel: 'both' },
  carry_crash: { enabled: true, channel: 'both' },
  rl_retrain_complete: { enabled: true, channel: 'slack' },
  backtest_complete: { enabled: false, channel: 'slack' },
  ir_degradation: { enabled: true, channel: 'both' },
}

function priorityBadge(type: AlertEvent['alert_type']) {
  const p = ALERT_PRIORITY[type]
  return (
    <Badge variant={p === 'high' ? 'negative' : p === 'medium' ? 'warning' : 'default'}>
      {p.toUpperCase()}
    </Badge>
  )
}

function channelBadge(channel: string) {
  return (
    <span className="text-micro font-mono text-text-muted uppercase">{channel}</span>
  )
}

function AlertFeed() {
  const { data, isLoading } = useSWR<AlertEvent[]>(
    'alerts',
    () => api.getAlerts(100),
    { refreshInterval: 15_000 }
  )

  if (isLoading) return <LoadingSkeleton className="h-64 w-full" />
  if (!data || !data.length) return <EmptyState title="No alerts yet" description="Alerts fire on trade events, macro changes, and system events" />

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <h3 className="text-body font-semibold text-text-primary">Alert Feed</h3>
        <span className="text-micro text-text-muted">{data.length} events</span>
      </div>
      <div className="divide-y divide-border max-h-[600px] overflow-y-auto">
        {data.map((alert) => (
          <div key={alert.id} className={cn('px-4 py-3 flex items-start gap-3', !alert.delivered && 'bg-primary/5')}>
            <div className="mt-0.5 flex-shrink-0">
              {priorityBadge(alert.alert_type)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-table text-text-primary font-medium">{ALERT_LABELS[alert.alert_type]}</span>
                {channelBadge(alert.channel)}
                {!alert.delivered && (
                  <span className="w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />
                )}
              </div>
              <p className="text-table text-text-muted">{alert.message}</p>
              <p className="text-micro text-text-muted/60 mt-1">{formatDateTime(alert.fired_at)}</p>
            </div>
            <Badge variant={alert.delivered ? 'positive' : 'default'} className="flex-shrink-0 text-micro">
              {alert.delivered ? 'SENT' : 'PENDING'}
            </Badge>
          </div>
        ))}
      </div>
    </div>
  )
}

function AlertRulesPanel() {
  const { data: savedRules, mutate } = useSWR<AlertRules>('alert-rules', () => api.getAlertRules())
  const [rules, setRules] = useState<AlertRules | null>(null)
  const [saving, setSaving] = useState(false)
  const [testSent, setTestSent] = useState(false)

  const effective = rules ?? savedRules ?? DEFAULT_RULES

  function updateRule(type: keyof AlertRules, patch: Partial<AlertRuleConfig>) {
    setRules((prev) => ({
      ...(prev ?? effective),
      [type]: { ...(prev ?? effective)[type], ...patch },
    }))
  }

  async function save() {
    setSaving(true)
    try {
      await api.updateAlertRules(effective)
      await mutate()
      setRules(null)
    } finally {
      setSaving(false)
    }
  }

  async function sendTest() {
    await api.sendTestAlert()
    setTestSent(true)
    setTimeout(() => setTestSent(false), 3000)
  }

  const dirty = rules !== null

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <h3 className="text-body font-semibold text-text-primary">Alert Rules</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={sendTest}
            className="px-3 py-1.5 text-micro border border-border rounded hover:border-primary hover:text-primary text-text-muted transition-colors"
          >
            {testSent ? 'Sent!' : 'Send Test Alert'}
          </button>
          {dirty && (
            <button
              onClick={save}
              disabled={saving}
              className="px-3 py-1.5 text-micro bg-primary text-white rounded hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving...' : 'Save Rules'}
            </button>
          )}
        </div>
      </div>

      <div className="divide-y divide-border">
        {(Object.keys(DEFAULT_RULES) as (keyof AlertRules)[]).map((type) => {
          const rule = effective[type]
          const priority = ALERT_PRIORITY[type as AlertEvent['alert_type']]
          return (
            <div key={type} className="px-4 py-3 flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rule.enabled}
                  onChange={(e) => updateRule(type, { enabled: e.target.checked })}
                  className="accent-primary"
                />
              </label>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className={cn('text-table', rule.enabled ? 'text-text-primary' : 'text-text-muted')}>
                    {ALERT_LABELS[type as AlertEvent['alert_type']]}
                  </span>
                  <Badge variant={priority === 'high' ? 'negative' : priority === 'medium' ? 'warning' : 'default'}>
                    {priority}
                  </Badge>
                </div>
              </div>
              <select
                value={rule.channel}
                onChange={(e) => updateRule(type, { channel: e.target.value as AlertRuleConfig['channel'] })}
                disabled={!rule.enabled}
                className="bg-background border border-border rounded px-2 py-1 text-micro text-text-primary disabled:opacity-40"
              >
                <option value="slack">Slack</option>
                <option value="email">Email</option>
                <option value="both">Both</option>
              </select>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function AlertsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-page-header font-bold text-text-primary">Alerting & Notifications</h1>
        <p className="text-text-muted text-table mt-1">Trade events, macro changes, and system notifications via email and Slack</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <AlertFeed />
        </div>
        <div className="lg:col-span-1">
          <AlertRulesPanel />
        </div>
      </div>
    </div>
  )
}
