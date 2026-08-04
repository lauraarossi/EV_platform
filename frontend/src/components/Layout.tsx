import { NavLink, Outlet } from 'react-router-dom'
import ThemeToggle from './ThemeToggle'

// Ordered as the workflow runs: set up a car, log charges, read the numbers,
// then compare. '/' stays the Charges route since logging is the frequent task.
const navItems = [
  { to: '/garage', label: 'Garage' },
  { to: '/', label: 'Charges' },
  { to: '/stats', label: 'Stats' },
  { to: '/compare', label: 'vs Petrol' },
]

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

export default function Layout() {
  return (
    <>
      <div className="relative z-[1] flex min-h-svh flex-col">
        <header className="sticky top-0 z-20 px-4 pt-4">
          <div className="glass glass-sheen mx-auto flex max-w-6xl items-center gap-3 rounded-2xl px-4 py-2.5">
            <a href="/" className="focus-ring flex items-center gap-2.5 rounded-lg">
              <span
                aria-hidden="true"
                className="grid h-8 w-8 place-items-center rounded-lg"
                style={{ background: 'linear-gradient(135deg, var(--accent-2), var(--accent))' }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-ink)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M13 2 4 14h7l-1 8 9-12h-7z" />
                </svg>
              </span>
              <span className="text-base font-semibold tracking-tight text-ink">Eevie</span>
            </a>

            {/* Desktop nav */}
            <nav className="ml-auto hidden items-center gap-1 md:flex">
              {navItems.map(({ to, label }) => (
                <NavLink key={to} to={to} end={to === '/'} className={navClass}>
                  {({ isActive }) => (
                    <>
                      <ActivePill isActive={isActive} />
                      {label}
                    </>
                  )}
                </NavLink>
              ))}
            </nav>

            <div className="ml-auto md:ml-2">
              <ThemeToggle />
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-28 pt-8 md:pb-12">
          <Outlet />
        </main>

        {/* Mobile nav — thumb-reachable, since this is a phone-first logging app */}
        <nav className="fixed inset-x-0 bottom-0 z-20 px-4 pb-4 md:hidden">
          <div className="glass glass-sheen mx-auto flex max-w-md items-center justify-between gap-1 rounded-2xl px-2 py-2">
            {navItems.map(({ to, label }) => (
              <NavLink key={to} to={to} end={to === '/'} className={navClass}>
                {({ isActive }) => (
                  <>
                    <ActivePill isActive={isActive} />
                    {label}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        </nav>
      </div>
    </>
  )
}
