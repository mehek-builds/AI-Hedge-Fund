'use client'

interface EmptyStateProps {
  title: string
  description?: string
  icon?: React.ReactNode
}

export function EmptyState({ title, description, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon && <div className="text-text-muted mb-3 opacity-50">{icon}</div>}
      <p className="text-body text-text-muted font-medium">{title}</p>
      {description && (
        <p className="text-table text-text-muted/70 mt-1 max-w-xs">{description}</p>
      )}
    </div>
  )
}
