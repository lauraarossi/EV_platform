import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useUnits } from '../hooks/useUnits'
import { useCurrency } from '../hooks/useCurrency'
import FeedbackModal from './FeedbackModal'

export default function AccountMenu() {
  const { user, signOut } = useAuth()
  const { units, setSystem } = useUnits()
  const { code, choices, choose } = useCurrency()
  const [open, setOpen] = useState(false)
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!user) return null

  const label = user.display_name || user.email
  const initial = label.trim().charAt(0).toUpperCase() || '?'

  return (
    <div ref={wrap} className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account"
        className="glass focus-ring grid h-9 w-9 place-items-center overflow-hidden rounded-full text-sm font-semibold text-ink"
      >
        {user.avatar_url ? (
          <img src={user.avatar_url} alt="" className="h-full w-full object-cover" />
        ) : (
          initial
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="glass glass-frosted glass-popover glass-sheen absolute right-0 z-30 mt-2 w-56 rounded-xl p-1.5"
        >
          <div className="px-3 py-2">
            {user.display_name && (
              <p className="truncate text-sm font-medium text-ink">{user.display_name}</p>
            )}
            <p className="truncate text-xs text-ink-3">{user.email}</p>
          </div>
          <div className="my-1 h-px bg-edge" />

          <div className="px-3 pb-1 pt-1.5">
            <p className="text-[10px] uppercase tracking-wider text-ink-3">Units</p>
            <div className="mt-1.5 flex gap-1" role="group" aria-label="Units">
              {(['metric', 'imperial'] as const).map(s => {
                const active = units.system === s
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSystem(s)}
                    aria-pressed={active}
                    className={`focus-ring flex-1 rounded-lg px-2 py-1.5 text-xs font-medium capitalize ${
                      active ? 'text-ink' : 'text-ink-3 hover:text-ink-2'
                    }`}
                    style={
                      active
                        ? {
                            background: 'color-mix(in oklab, var(--accent) 18%, transparent)',
                            border: '1px solid color-mix(in oklab, var(--accent) 35%, transparent)',
                          }
                        : { border: '1px solid var(--border)' }
                    }
                  >
                    {s === 'metric' ? 'km' : 'miles'}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="px-3 pb-1 pt-1.5">
            <p className="text-[10px] uppercase tracking-wider text-ink-3">Currency</p>
            <select
              value={code}
              onChange={e => { void choose(e.target.value) }}
              aria-label="Currency"
              // Opaque, not transparent: the popup list is drawn by the
              // browser, and against a transparent control it came out white
              // with white text in dark mode.
              className="focus-ring mt-1.5 w-full rounded-lg border border-edge bg-surface-solid px-2 py-1.5 text-xs text-ink"
            >
              {choices.map(c => (
                <option key={c.code} value={c.code} className="bg-surface-solid text-ink">
                  {c.symbol.trim()} {c.code}
                </option>
              ))}
            </select>
          </div>

          <div className="my-1 h-px bg-edge" />
          <button
            type="button"
            role="menuitem"
            onClick={() => { setOpen(false); setFeedbackOpen(true) }}
            className="focus-ring w-full rounded-lg px-3 py-2 text-left text-sm text-ink-2 hover:text-ink"
          >
            Send feedback
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={signOut}
            className="focus-ring w-full rounded-lg px-3 py-2 text-left text-sm text-ink-2 hover:text-ink"
          >
            Sign out
          </button>
        </div>
      )}

      <FeedbackModal open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </div>
  )
}
