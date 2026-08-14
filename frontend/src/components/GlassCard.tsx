import type { ReactNode } from 'react'

export default function GlassCard({
  children,
  className = '',
  interactive = false,
  glassSheen = true,
}: {
  children: ReactNode
  className?: string
  interactive?: boolean
  glassSheen?: boolean
}) {
  return (
    <div
      className={`glass ${glassSheen ? 'glass-sheen' : ''} rounded-2xl ${
        interactive ? 'glass-hover' : ''
      } ${className}`}
    >
      {children}
    </div>
  )
}
