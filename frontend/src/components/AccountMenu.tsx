import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../hooks/useAuth'

export default function AccountMenu() {
  const { user, signOut } = useAuth()
  const [open, setOpen] = useState(false)
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
          className="glass glass-sheen absolute right-0 z-30 mt-2 w-56 rounded-xl p-1.5"
        >
          <div className="px-3 py-2">
            {user.display_name && (
              <p className="truncate text-sm font-medium text-ink">{user.display_name}</p>
            )}
            <p className="truncate text-xs text-ink-3">{user.email}</p>
          </div>
          <div className="my-1 h-px bg-edge" />
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
    </div>
  )
}
