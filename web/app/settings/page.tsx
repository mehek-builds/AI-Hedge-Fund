'use client'

import { useState, useEffect } from 'react'
import useSWR from 'swr'
import * as Tabs from '@radix-ui/react-tabs'
import * as Switch from '@radix-ui/react-switch'
import * as Slider from '@radix-ui/react-slider'
import * as Dialog from '@radix-ui/react-dialog'
import { Eye, EyeOff, X } from 'lucide-react'
import { api, Settings, DataSource } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn, formatDateTime } from '@/lib/utils'

function MaskedInput({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <input
        type={show ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-background border border-border rounded-md px-3 py-2.5 text-table text-text-primary focus:outline-none focus:border-primary pr-10 transition-colors font-mono"
      />
      <button
        type="button"
        onClick={() => setShow(!show)}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
      >
        {show ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  )
}

function LabeledSlider({
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  unit: string
  onChange: (v: number) => void
}) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <label className="text-table text-text-primary">{label}</label>
        <span className="font-mono text-table text-primary font-semibold">
          {value}{unit}
        </span>
      </div>
      <Slider.Root
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={([v]) => onChange(v)}
        className="relative flex items-center w-full h-5"
      >
        <Slider.Track className="bg-border relative grow rounded-full h-1.5">
          <Slider.Range className="absolute bg-primary rounded-full h-full" />
        </Slider.Track>
        <Slider.Thumb className="block w-5 h-5 bg-primary rounded-full shadow-lg focus:outline-none focus:ring-2 focus:ring-primary/50 cursor-pointer" />
      </Slider.Root>
      <div className="flex justify-between text-micro text-text-muted">
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  )
}

function SwitchRow({ label, description, checked, onCheckedChange }: { label: string; description?: string; checked: boolean; onCheckedChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="text-table text-text-primary">{label}</p>
        {description && <p className="text-micro text-text-muted">{description}</p>}
      </div>
      <Switch.Root
        checked={checked}
        onCheckedChange={onCheckedChange}
        className={cn(
          'w-11 h-6 rounded-full transition-colors focus:outline-none',
          checked ? 'bg-primary' : 'bg-border'
        )}
      >
        <Switch.Thumb
          className={cn(
            'block w-5 h-5 bg-white rounded-full shadow transition-transform',
            checked ? 'translate-x-[22px]' : 'translate-x-[2px]'
          )}
        />
      </Switch.Root>
    </div>
  )
}

function PaperLiveConfirmModal({ open, onClose, onConfirm, currentMode }: { open: boolean; onClose: () => void; onConfirm: () => void; currentMode: boolean }) {
  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-40" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-surface border border-border rounded-xl p-6 w-full max-w-md shadow-2xl focus:outline-none">
          <div className="flex items-center justify-between mb-4">
            <Dialog.Title className="text-body font-semibold text-text-primary">
              Switch to {currentMode ? 'Live' : 'Paper'} Trading
            </Dialog.Title>
            <Dialog.Close asChild>
              <button className="p-1 rounded hover:bg-border/50 text-text-muted transition-colors">
                <X size={16} />
              </button>
            </Dialog.Close>
          </div>

          <div className={cn('rounded-lg p-4 mb-4', currentMode ? 'bg-positive/10 border border-positive/30' : 'bg-warning/10 border border-warning/30')}>
            <p className={cn('text-table font-medium', currentMode ? 'text-positive' : 'text-warning')}>
              {currentMode
                ? 'Switching to LIVE trading. Real money will be used.'
                : 'Switching to PAPER trading. Orders will be simulated.'}
            </p>
          </div>

          <p className="text-table text-text-muted mb-6">
            Are you sure you want to switch to {currentMode ? 'live' : 'paper'} trading mode?
          </p>

          <div className="flex gap-3">
            <Dialog.Close asChild>
              <button className="flex-1 border border-border text-text-muted hover:text-text-primary py-2 px-4 rounded-md text-table transition-colors">
                Cancel
              </button>
            </Dialog.Close>
            <button
              onClick={onConfirm}
              className={cn(
                'flex-1 py-2 px-4 rounded-md text-table font-medium text-white transition-colors',
                currentMode ? 'bg-positive hover:bg-positive/90' : 'bg-warning hover:bg-warning/90'
              )}
            >
              Confirm
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function BrokerageTab({ settings, onSave }: { settings: Settings; onSave: (s: Partial<Settings>) => void }) {
  const [apiKey, setApiKey] = useState(settings.brokerage.alpaca_api_key)
  const [secretKey, setSecretKey] = useState(settings.brokerage.alpaca_secret_key)
  const [showConfirm, setShowConfirm] = useState(false)
  const [pendingMode, setPendingMode] = useState(false)

  const statusVariant = settings.brokerage.connection_status === 'connected'
    ? 'positive'
    : settings.brokerage.connection_status === 'error'
    ? 'negative'
    : 'muted'

  function handleToggle() {
    setPendingMode(!settings.brokerage.paper_trading)
    setShowConfirm(true)
  }

  function confirmToggle() {
    onSave({ brokerage: { ...settings.brokerage, paper_trading: pendingMode } })
    setShowConfirm(false)
  }

  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-table text-text-muted uppercase tracking-wider text-micro">Connection Status</label>
          <Badge variant={statusVariant}>{settings.brokerage.connection_status.toUpperCase()}</Badge>
        </div>
        <p className="text-micro text-text-muted">Last sync: {formatDateTime(settings.brokerage.last_sync)}</p>
      </div>

      <div>
        <label className="block text-micro text-text-muted uppercase tracking-wider mb-1.5">Alpaca API Key</label>
        <MaskedInput value={apiKey} onChange={setApiKey} placeholder="PK..." />
      </div>

      <div>
        <label className="block text-micro text-text-muted uppercase tracking-wider mb-1.5">Alpaca Secret Key</label>
        <MaskedInput value={secretKey} onChange={setSecretKey} placeholder="Secret key" />
      </div>

      <div className="flex items-center justify-between py-3 border-t border-border">
        <div>
          <p className="text-table text-text-primary">Trading Mode</p>
          <p className="text-micro text-text-muted">
            Currently: <span className={cn('font-semibold', settings.brokerage.paper_trading ? 'text-warning' : 'text-positive')}>
              {settings.brokerage.paper_trading ? 'Paper Trading' : 'Live Trading'}
            </span>
          </p>
        </div>
        <button
          onClick={handleToggle}
          className={cn(
            'px-4 py-2 rounded-md text-table font-medium text-white transition-colors',
            settings.brokerage.paper_trading ? 'bg-positive hover:bg-positive/90' : 'bg-warning hover:bg-warning/90'
          )}
        >
          Switch to {settings.brokerage.paper_trading ? 'Live' : 'Paper'}
        </button>
      </div>

      <button
        onClick={() => onSave({ brokerage: { ...settings.brokerage, alpaca_api_key: apiKey, alpaca_secret_key: secretKey } })}
        className="bg-primary hover:bg-primary/90 text-white font-medium py-2.5 px-6 rounded-md text-table transition-colors"
      >
        Save Brokerage Settings
      </button>

      <PaperLiveConfirmModal
        open={showConfirm}
        onClose={() => setShowConfirm(false)}
        onConfirm={confirmToggle}
        currentMode={!settings.brokerage.paper_trading}
      />
    </div>
  )
}

function RiskTab({ settings, onSave }: { settings: Settings; onSave: (s: Partial<Settings>) => void }) {
  const [risk, setRisk] = useState(settings.risk)

  return (
    <div className="space-y-6 max-w-lg">
      <LabeledSlider
        label="Hard Stop %"
        value={risk.hard_stop_pct}
        min={0}
        max={20}
        step={0.5}
        unit="%"
        onChange={(v) => setRisk({ ...risk, hard_stop_pct: v })}
      />
      <LabeledSlider
        label="Max Position Size %"
        value={risk.max_position_size_pct}
        min={1}
        max={10}
        step={0.5}
        unit="%"
        onChange={(v) => setRisk({ ...risk, max_position_size_pct: v })}
      />
      <LabeledSlider
        label="Max Sector Concentration %"
        value={risk.max_sector_concentration_pct}
        min={10}
        max={50}
        step={5}
        unit="%"
        onChange={(v) => setRisk({ ...risk, max_sector_concentration_pct: v })}
      />
      <LabeledSlider
        label="Macro Halt Threshold"
        value={risk.macro_halt_threshold}
        min={-6}
        max={-1}
        step={1}
        unit=""
        onChange={(v) => setRisk({ ...risk, macro_halt_threshold: v })}
      />

      <button
        onClick={() => onSave({ risk })}
        className="bg-primary hover:bg-primary/90 text-white font-medium py-2.5 px-6 rounded-md text-table transition-colors"
      >
        Save Risk Settings
      </button>
    </div>
  )
}

function SignalTab({ settings, onSave }: { settings: Settings; onSave: (s: Partial<Settings>) => void }) {
  const [signal, setSignal] = useState(settings.signal)

  function InputField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
    return (
      <div>
        <label className="block text-micro text-text-muted uppercase tracking-wider mb-1.5">{label}</label>
        <input
          type="number"
          step="0.01"
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          className="w-full bg-background border border-border rounded-md px-3 py-2.5 text-table text-text-primary focus:outline-none focus:border-primary font-mono transition-colors"
        />
      </div>
    )
  }

  return (
    <div className="space-y-5 max-w-lg">
      <LabeledSlider
        label="Min Signal Threshold"
        value={signal.min_signal_threshold}
        min={0}
        max={5}
        step={0.1}
        unit=""
        onChange={(v) => setSignal({ ...signal, min_signal_threshold: v })}
      />

      <div className="space-y-3">
        <p className="text-table text-text-muted font-medium uppercase tracking-wider text-micro">Intangible Tier Multipliers</p>
        <div className="grid grid-cols-3 gap-3">
          <InputField
            label="Tier 1"
            value={signal.intangible_tier_multipliers.tier1}
            onChange={(v) => setSignal({ ...signal, intangible_tier_multipliers: { ...signal.intangible_tier_multipliers, tier1: v } })}
          />
          <InputField
            label="Tier 2"
            value={signal.intangible_tier_multipliers.tier2}
            onChange={(v) => setSignal({ ...signal, intangible_tier_multipliers: { ...signal.intangible_tier_multipliers, tier2: v } })}
          />
          <InputField
            label="Tier 3"
            value={signal.intangible_tier_multipliers.tier3}
            onChange={(v) => setSignal({ ...signal, intangible_tier_multipliers: { ...signal.intangible_tier_multipliers, tier3: v } })}
          />
        </div>
      </div>

      <InputField
        label="ROIC Multiplier"
        value={signal.roic_multiplier}
        onChange={(v) => setSignal({ ...signal, roic_multiplier: v })}
      />

      <button
        onClick={() => onSave({ signal })}
        className="bg-primary hover:bg-primary/90 text-white font-medium py-2.5 px-6 rounded-md text-table transition-colors"
      >
        Save Signal Settings
      </button>
    </div>
  )
}

function DataSourcesTab() {
  const { data, isLoading } = useSWR<DataSource[]>(
    'data-sources',
    () => api.getDataSources(),
    { refreshInterval: 300_000 }
  )
  const [fredKey, setFredKey] = useState('')
  const [fmpKey, setFmpKey] = useState('')

  const statusVariant = (status: DataSource['status']): 'positive' | 'negative' | 'warning' => {
    if (status === 'fresh') return 'positive'
    if (status === 'error') return 'negative'
    return 'warning'
  }

  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <label className="block text-micro text-text-muted uppercase tracking-wider mb-1.5">FRED API Key</label>
        <MaskedInput value={fredKey} onChange={setFredKey} placeholder="FRED API key" />
      </div>

      <div>
        <label className="block text-micro text-text-muted uppercase tracking-wider mb-1.5">FMP API Key</label>
        <MaskedInput value={fmpKey} onChange={setFmpKey} placeholder="FMP API key" />
      </div>

      <div className="bg-surface border border-border rounded-lg">
        <div className="px-4 py-3 border-b border-border">
          <h3 className="text-body font-semibold text-text-primary">Data Source Status</h3>
        </div>
        {isLoading ? (
          <div className="p-4"><CardSkeleton /></div>
        ) : !data || data.length === 0 ? (
          <EmptyState title="No data sources configured" />
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th>Source</th>
                <th>Status</th>
                <th>Last Fetched</th>
                <th>API Key</th>
              </tr>
            </thead>
            <tbody>
              {data.map((source) => (
                <tr key={source.name}>
                  <td className="text-text-primary">{source.name}</td>
                  <td>
                    <Badge variant={statusVariant(source.status)}>
                      {source.status.toUpperCase()}
                    </Badge>
                  </td>
                  <td className="text-text-muted text-micro">{formatDateTime(source.last_fetched)}</td>
                  <td>
                    <Badge variant={source.api_key_configured ? 'positive' : 'negative'}>
                      {source.api_key_configured ? 'Configured' : 'Missing'}
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

function NotificationsTab({ settings, onSave }: { settings: Settings; onSave: (s: Partial<Settings>) => void }) {
  const [notifs, setNotifs] = useState(settings.notifications)
  const [testLoading, setTestLoading] = useState(false)
  const [testStatus, setTestStatus] = useState<'idle' | 'sent' | 'error'>('idle')

  async function handleTest() {
    setTestLoading(true)
    setTestStatus('idle')
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/notifications/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ webhook_url: notifs.webhook_url }),
      })
      setTestStatus('sent')
    } catch {
      setTestStatus('error')
    } finally {
      setTestLoading(false)
    }
  }

  return (
    <div className="space-y-4 max-w-lg">
      <div className="bg-surface border border-border rounded-lg divide-y divide-border">
        <SwitchRow
          label="Trade Executed"
          description="Notify when a trade is entered or exited"
          checked={notifs.trade_executed}
          onCheckedChange={(v) => setNotifs({ ...notifs, trade_executed: v })}
        />
        <SwitchRow
          label="Stop Triggered"
          description="Notify when a stop loss is hit"
          checked={notifs.stop_triggered}
          onCheckedChange={(v) => setNotifs({ ...notifs, stop_triggered: v })}
        />
        <SwitchRow
          label="Macro Regime Change"
          description="Notify when the macro composite score changes"
          checked={notifs.macro_regime_change}
          onCheckedChange={(v) => setNotifs({ ...notifs, macro_regime_change: v })}
        />
        <SwitchRow
          label="RL Training Complete"
          description="Notify when a training job finishes"
          checked={notifs.rl_training_complete}
          onCheckedChange={(v) => setNotifs({ ...notifs, rl_training_complete: v })}
        />
      </div>

      <div>
        <label className="block text-micro text-text-muted uppercase tracking-wider mb-1.5">Slack Webhook URL</label>
        <input
          type="url"
          value={notifs.webhook_url}
          onChange={(e) => setNotifs({ ...notifs, webhook_url: e.target.value })}
          placeholder="https://hooks.slack.com/..."
          className="w-full bg-background border border-border rounded-md px-3 py-2.5 text-table text-text-primary focus:outline-none focus:border-primary transition-colors"
        />
      </div>

      {testStatus === 'sent' && (
        <div className="bg-positive/10 border border-positive/30 rounded-md px-3 py-2">
          <p className="text-micro text-positive">Test notification sent successfully</p>
        </div>
      )}
      {testStatus === 'error' && (
        <div className="bg-negative/10 border border-negative/30 rounded-md px-3 py-2">
          <p className="text-micro text-negative">Test notification failed. Check webhook URL.</p>
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={() => onSave({ notifications: notifs })}
          className="flex-1 bg-primary hover:bg-primary/90 text-white font-medium py-2.5 px-6 rounded-md text-table transition-colors"
        >
          Save
        </button>
        <button
          onClick={handleTest}
          disabled={testLoading || !notifs.webhook_url}
          className="flex-1 border border-border text-text-muted hover:text-text-primary py-2.5 px-6 rounded-md text-table transition-colors disabled:opacity-50"
        >
          {testLoading ? 'Sending...' : 'Test Notification'}
        </button>
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { data: settings, isLoading, mutate } = useSWR<Settings>(
    'settings',
    () => api.getSettings(),
    { refreshInterval: 0 }
  )
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  async function handleSave(partial: Partial<Settings>) {
    setSaveStatus('saving')
    try {
      await api.updateSettings(partial)
      await mutate()
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus('idle'), 2000)
    } catch {
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 3000)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4 max-w-2xl">
        {[...Array(5)].map((_, i) => <CardSkeleton key={i} />)}
      </div>
    )
  }

  if (!settings) {
    return <EmptyState title="Could not load settings" description="Check that the backend API is running" />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-page-header font-bold text-text-primary">Settings</h1>
          <p className="text-text-muted text-table mt-1">System configuration and preferences</p>
        </div>
        {saveStatus === 'saved' && (
          <Badge variant="positive">Settings saved</Badge>
        )}
        {saveStatus === 'error' && (
          <Badge variant="negative">Save failed</Badge>
        )}
        {saveStatus === 'saving' && (
          <Badge variant="muted">Saving...</Badge>
        )}
      </div>

      <Tabs.Root defaultValue="brokerage" className="space-y-6">
        <Tabs.List className="flex gap-0 bg-surface border border-border rounded-lg p-1 max-w-2xl">
          {['brokerage', 'risk', 'signal', 'data', 'notifications'].map((tab) => (
            <Tabs.Trigger
              key={tab}
              value={tab}
              className="flex-1 py-2 px-3 text-micro font-medium capitalize rounded-md transition-colors text-text-muted data-[state=active]:bg-primary data-[state=active]:text-white hover:text-text-primary"
            >
              {tab === 'data' ? 'Data Sources' : tab === 'notifications' ? 'Alerts' : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="brokerage">
          <BrokerageTab settings={settings} onSave={handleSave} />
        </Tabs.Content>

        <Tabs.Content value="risk">
          <RiskTab settings={settings} onSave={handleSave} />
        </Tabs.Content>

        <Tabs.Content value="signal">
          <SignalTab settings={settings} onSave={handleSave} />
        </Tabs.Content>

        <Tabs.Content value="data">
          <DataSourcesTab />
        </Tabs.Content>

        <Tabs.Content value="notifications">
          <NotificationsTab settings={settings} onSave={handleSave} />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  )
}
