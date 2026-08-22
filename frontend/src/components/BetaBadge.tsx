import { useState } from 'react'
import { IS_BETA } from '../site'
import FeedbackModal from './FeedbackModal'

/**
 * A small mark next to the name, so nobody has to discover that the thing is
 * half-built by running into a rough edge.
 */
export function BetaBadge() {
  if (!IS_BETA) return null
  return (
    <span
      className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
      style={{
        color: 'var(--accent)',
        background: 'color-mix(in oklab, var(--accent) 14%, transparent)',
        border: '1px solid color-mix(in oklab, var(--accent) 30%, transparent)',
      }}
    >
      Beta
    </span>
  )
}

/**
 * The fuller version, for a page with room to explain itself.
 */
export function BetaNotice({ className = '' }: { className?: string }) {
  const [open, setOpen] = useState(false)
  if (!IS_BETA) return null
  return (
    <>
      <p className={`text-sm leading-relaxed text-ink-3 ${className}`}>
        Eevie is in beta and still being built, so expect the odd rough edge and
        the occasional change under your feet. Your data stays put through all of it.{' '}
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="focus-ring rounded underline decoration-dotted underline-offset-2 hover:text-ink-2"
        >
          Tell me what is wrong or missing
        </button>
        {' — it is the fastest way to change what gets built next.'}
      </p>
      <FeedbackModal open={open} onClose={() => setOpen(false)} />
    </>
  )
}
