import type { ReactNode } from 'react'

export default function GlassCard({
  children,
  className = '',
  interactive = false,
}: {
  children: ReactNode
  className?: string
  interactive?: boolean
}) {
  return (
    <div
      className={`glass glass-sheen rounded-2xl ${interactive ? 'glass-hover' : ''} ${className}`}
    >
      {children}
    </div>
  )
}
