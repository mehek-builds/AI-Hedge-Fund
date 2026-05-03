'use client'

import { cn } from '@/lib/utils'

interface StatCardProps {
  title: string
  value: string
  subtitle?: string
  color?: 'positive' | 'negative' | 'warning' | 'primary' | 'default'
  className?: string
}

const colorMap = {
  positive: 'text-positive',
  negative: 'text-negative',
  warning: 'text-warning',
  primary: 'text-primary',
  default: 'text-text-primary',
}

export function StatCard({ title, value, subtitle, color = 'default', className }: StatCardProps) {
  return (
    <div className={cn('bg-surface border border-border rounded-lg p-4', className)}>
      <p className="text-micro text-text-muted uppercase tracking-wider font-medium mb-1">{title}</p>
      <p className={cn('text-2xl font-mono font-semibold leading-tight', colorMap[color])}>
        {value}
      </p>
      {subtitle && (
        <p className="text-micro text-text-muted mt-1">{subtitle}</p>
      )}
    </div>
  )
}
