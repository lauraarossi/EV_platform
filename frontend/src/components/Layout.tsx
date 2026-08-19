import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import ThemeToggle from './ThemeToggle'
import AccountMenu from './AccountMenu'
import { useAuth } from '../hooks/useAuth'
import { useScrolled } from '../hooks/useScrolled'

// Ordered as the workflow runs: set up a car, log charges, read the numbers,
// then compare. '/' stays the Charges route since logging is the frequent task.
const navItems = [
  { to: '/garage', label: 'Garage' },
  { to: '/', label: 'Charges' },
  { to: '/stats', label: 'Stats' },
  { to: '/compare', label: 'vs Petrol' },
]

// Appended rather than placed in the run of tasks: it is a different kind of
// thing, and it should not push the four everyday tabs around on a phone.
const adminItem = { to: '/admin', label: 'Admin' }

function navClass({ isActive }: { isActive: boolean }) {
  return [
    'focus-ring relative rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors whitespace-nowrap',
    isActive ? 'text-ink' : 'text-ink-3 hover:text-ink-2',
  ].join(' ')
}

function ActivePill({ isActive }: { isActive: boolean }) {
  if (!isActive) return null
  return (
    <span
      aria-hidden="true"
      className="absolute inset-0 -z-10 rounded-full"
      style={{
        background: 'color-mix(in oklab, var(--accent) 18%, transparent)',
        boxShadow: '0 0 20px var(--glow)',
        border: '1px solid color-mix(in oklab, var(--accent) 35%, transparent)',
      }}
    />
  )
}

/**
 * The app frame.
 *
 * On a phone both bars get out of the way once the page moves: the top one
 * shrinks to a pill holding the badge and the theme toggle, which is all it
 * ever carried there, and the tab bar folds into a button in the thumb's
 * reach. Neither disappears — a nav you cannot find is worse than one taking
 * up room — and both come back on a tap or a scroll to the top.
 *
 * Desktop keeps the full bars: there is room for them, and the pointer has no
 * trouble reaching the top of the screen.
 */
export default function Layout() {
  const { user } = useAuth()
  const items = user?.is_admin ? [...navItems, adminItem] : navItems
  const scrolled = useScrolled()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  // Reopening it on every scroll would fight the person reading; going
  // somewhere is what the menu is for, so it closes on arrival.
  useEffect(() => setMenuOpen(false), [location.pathname])

  // Any further scrolling folds it away again, so it never sits over the
  // content once it has been ignored.
  useEffect(() => {
    if (!menuOpen) return
    const close = () => setMenuOpen(false)
    window.addEventListener('scroll', close, { passive: true })
    return () => window.removeEventListener('scroll', close)
  }, [menuOpen])

  const tabs = items.map(({ to, label }) => (
    <NavLink key={to} to={to} end={to === '/'} className={navClass}>
      {({ isActive }) => (
        <>
          <ActivePill isActive={isActive} />
          {label}
        </>
      )}
    </NavLink>
  ))

  const collapsed = scrolled && !menuOpen

  return (
    <div className="relative z-[1] flex min-h-svh flex-col">
      <header className="sticky top-0 z-20 px-4 pt-4">
        <div
          data-scrolled={scrolled}
          className="top-bar glass glass-frosted glass-sheen flex max-w-6xl items-center gap-3 rounded-2xl py-2.5"
        >
          <a href="/" className="top-bar-brand focus-ring items-center gap-2.5 rounded-lg">
            <span
              aria-hidden="true"
              className="grid h-8 w-8 shrink-0 place-items-center rounded-lg"
              style={{ background: 'linear-gradient(135deg, var(--accent-2), var(--accent))' }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-ink)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M13 2 4 14h7l-1 8 9-12h-7z" />
              </svg>
            </span>
            <span className="ml-2.5 text-base font-semibold tracking-tight text-ink">Eevie</span>
          </a>

          {/* Desktop nav */}
          <nav className="ml-auto hidden items-center gap-1 md:flex">{tabs}</nav>

          <div className="ml-auto flex items-center gap-2 md:ml-2">
            <ThemeToggle />
            <AccountMenu />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-28 pt-8 md:pb-12">
        <Outlet />
      </main>

      {/* Mobile nav — thumb-reachable, since this is a phone-first logging app */}
      <nav className="fixed inset-x-0 bottom-0 z-20 px-4 pb-4 md:hidden">
        {collapsed ? (
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label="Show navigation"
            aria-expanded={false}
            className="glass glass-frosted glass-sheen focus-ring mx-auto grid h-12 w-12 place-items-center rounded-2xl text-ink"
          >
            <svg
              aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round"
            >
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
        ) : (
          <div className="glass glass-frosted glass-sheen mx-auto flex max-w-md items-center justify-between gap-1 rounded-2xl px-2 py-2">
            {tabs}
          </div>
        )}
      </nav>
    </div>
  )
}
