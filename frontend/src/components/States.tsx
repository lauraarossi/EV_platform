import type { ReactNode } from 'react'
import GlassCard from './GlassCard'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <GlassCard className="grid place-items-center p-10">
      <p className="text-sm text-ink-3">{label}</p>
    </GlassCard>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <GlassCard className="p-6">
      <div className="flex items-start gap-3">
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--critical)" strokeWidth="2" strokeLinecap="round" className="mt-0.5 shrink-0">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 8v5M12 16.5v.01" />
        </svg>
        <div>
          {/* status colour never carries meaning alone — icon + label pairing */}
          <p className="text-sm font-medium text-ink">Couldn’t load data</p>
          <p className="mt-1 text-sm text-ink-2">{message}</p>
          <p className="mt-2 text-xs text-ink-3">
            Is the API running? <code className="text-ink-2">uvicorn app.main:app --reload</code>
          </p>
          {onRetry && (
            <button onClick={onRetry} className="btn-primary focus-ring mt-3 rounded-lg px-3 py-1.5 text-sm font-medium">
              Retry
            </button>
          )}
        </div>
      </div>
    </GlassCard>
  )
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <GlassCard className="grid place-items-center p-12 text-center">
      <div className="max-w-sm">
        <h2 className="text-base font-medium text-ink">{title}</h2>
        <p className="mt-1.5 text-sm text-ink-2">{body}</p>
        {action && <div className="mt-4">{action}</div>}
      </div>
    </GlassCard>
  )
}
