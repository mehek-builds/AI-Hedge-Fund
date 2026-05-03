'use client'

import { cn } from '@/lib/utils'

type BadgeVariant = 'positive' | 'negative' | 'warning' | 'neutral' | 'primary' | 'muted'

interface BadgeProps {
  variant?: BadgeVariant
  children: React.ReactNode
  className?: string
}

const variantStyles: Record<BadgeVariant, string> = {
  positive: 'bg-positive/20 text-positive border-positive/30',
  negative: 'bg-negative/20 text-negative border-negative/30',
  warning: 'bg-warning/20 text-warning border-warning/30',
  neutral: 'bg-text-muted/20 text-text-muted border-text-muted/30',
  primary: 'bg-primary/20 text-primary border-primary/30',
  muted: 'bg-border/50 text-text-muted border-border',
}

export function Badge({ variant = 'neutral', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-micro font-medium border',
        variantStyles[variant],
        className
      )}
    >
      {children}
    </span>
  )
}
