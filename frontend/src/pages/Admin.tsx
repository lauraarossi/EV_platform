import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getOverview, getRuns, getUsers, runTask, setUserRole,
  type AdminOverview, type AdminUser, type ImportRun, type UserRole,
} from '../api/admin'
import { useAuth } from '../hooks/useAuth'
import PageHeader from '../components/PageHeader'
import GlassCard from '../components/GlassCard'
import StatTile from '../components/StatTile'
import { Loading, ErrorState } from '../components/States'

const SOURCE_LABEL: Record<string, string> = {
  eea: 'EEA registrations',
  evdb: 'EV database',
  vca: 'VCA new-car data',
  manual: 'Entered by hand',
}

const when = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleString('en-IE', {
        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
      })
    : '—'

const took = (ms: number | null) => {
  if (ms == null) return '—'
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

/** Status never rides on colour alone — each pairs a glyph with a word. */
function RunStatus({ status }: { status: ImportRun['status'] }) {
  const look = {
    ok: { mark: '✓', text: 'Succeeded', colour: 'var(--positive)' },
    failed: { mark: '✕', text: 'Failed', colour: 'var(--critical)' },
    running: { mark: '⟳', text: 'Running', colour: 'var(--accent)' },
  }[status]

  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium" style={{ color: look.colour }}>
      <span aria-hidden="true" className={status === 'running' ? 'animate-spin' : ''}>
        {look.mark}
      </span>
      {look.text}
    </span>
  )
}

export default function Admin() {
  const { user } = useAuth()
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [runs, setRuns] = useState<ImportRun[]>([])
  const [users, setUsers] = useState<AdminUser[]>([])
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(async () => {
    const [o, r, u] = await Promise.all([getOverview(), getRuns(), getUsers()])
    setOverview(o)
    setRuns(r)
    setUsers(u)
    return r
  }, [])

  useEffect(() => {
    load().catch(e => setError(e?.message ?? 'Could not load the console'))
  }, [load])

  // Refreshes run in the background, so the page polls while one is going
  // rather than leaving a stale "Running" on screen indefinitely.
  const anyRunning = runs.some(r => r.status === 'running')
  const pollRef = useRef<number | null>(null)

  useEffect(() => {
    if (!anyRunning) return
    pollRef.current = window.setInterval(() => {
      load().catch(() => {})
    }, 2000)
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current)
    }
  }, [anyRunning, load])

  const start = async (key: string, label: string, slow: boolean) => {
    if (slow && !window.confirm(`${label} takes a few minutes. Start it now?`)) return
    setBusy(key)
    setNotice(null)
    try {
      await runTask(key)
      setNotice(`${label} started.`)
      await load()
    } catch (e: any) {
      setNotice(e?.response?.data?.detail ?? `Could not start ${label}.`)
    } finally {
      setBusy(null)
    }
  }

  const changeRole = async (target: AdminUser, role: UserRole) => {
    setNotice(null)
    try {
      const updated = await setUserRole(target.id, role)
      setUsers(list => list.map(u => (u.id === updated.id ? updated : u)))
    } catch (e: any) {
      setNotice(e?.response?.data?.detail ?? 'Could not change that role.')
    }
  }

  if (error) return <ErrorState message={error} onRetry={() => load().catch(() => {})} />
  if (!overview) return <Loading label="Reading the console…" />

  return (
    <>
      <PageHeader
        title="Admin"
        subtitle="Refresh the reference data, and see what state it is in."
      />

      {notice && (
        <GlassCard className="mb-4 p-3">
          <p className="text-sm text-ink-2">{notice}</p>
        </GlassCard>
      )}

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Catalogue"
          value={overview.catalogue_total.toLocaleString('en-IE')}
          unit="entries"
          hint={`${overview.distinct_makes} makes · ${overview.distinct_models} models`}
        />
        <StatTile
          label="Accounts"
          value={String(overview.users)}
          hint={`${overview.admins} with admin access`}
          accent="var(--accent-2)"
        />
        <StatTile
          label="Logged"
          value={overview.fuel_events.toLocaleString('en-IE')}
          unit="fill-ups"
          hint={`across ${overview.vehicles} vehicles`}
        />
        <StatTile
          label="Fuel prices"
          value={overview.fuel_prices.toLocaleString('en-IE')}
          hint={`${overview.tariffs} electricity tariffs`}
          accent="var(--accent-2)"
        />
      </section>

      {/* --- refreshes ------------------------------------------------------ */}
      <h2 className="mb-3 mt-8 text-sm font-medium uppercase tracking-wider text-ink-3">
        Data refreshes
      </h2>
      <div className="grid gap-3 md:grid-cols-2">
        {overview.tasks.map(task => {
          const running = task.last_run?.status === 'running'
          return (
            <GlassCard key={task.key} className="flex flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-ink">{task.label}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-ink-3">{task.description}</p>
                </div>
                <button
                  type="button"
                  onClick={() => start(task.key, task.label, task.slow)}
                  disabled={running || busy === task.key}
                  className="btn-primary focus-ring shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                >
                  {running ? 'Running…' : 'Run'}
                </button>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-edge pt-3 text-xs text-ink-3">
                {task.last_run ? (
                  <>
                    <RunStatus status={task.last_run.status} />
                    <span>· {when(task.last_run.started_at)}</span>
                    <span>· {took(task.last_run.duration_ms)}</span>
                  </>
                ) : (
                  <span>Never run</span>
                )}
              </div>

              {task.last_run?.error && (
                <p className="mt-2 break-words text-xs" style={{ color: 'var(--critical)' }}>
                  {task.last_run.error}
                </p>
              )}
            </GlassCard>
          )
        })}
      </div>

      {/* --- catalogue coverage --------------------------------------------- */}
      <h2 className="mb-3 mt-8 text-sm font-medium uppercase tracking-wider text-ink-3">
        Where the catalogue comes from
      </h2>
      <GlassCard className="overflow-x-auto p-1">
        <table className="w-full min-w-[34rem] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-ink-3">
              <th className="px-4 py-3 font-medium">Source</th>
              <th className="px-4 py-3 text-right font-medium">Entries</th>
              <th className="px-4 py-3 text-right font-medium">With trim</th>
              <th className="px-4 py-3 text-right font-medium">With battery</th>
              <th className="px-4 py-3 text-right font-medium">With L/100km</th>
            </tr>
          </thead>
          <tbody>
            {overview.catalogue_by_source.map(s => (
              <tr key={s.source} className="border-t border-edge">
                <td className="px-4 py-3 text-ink">{SOURCE_LABEL[s.source] ?? s.source}</td>
                <td className="readout px-4 py-3 text-right text-ink">
                  {s.entries.toLocaleString('en-IE')}
                </td>
                <td className="readout px-4 py-3 text-right text-ink-2">
                  {s.with_trim.toLocaleString('en-IE')}
                </td>
                <td className="readout px-4 py-3 text-right text-ink-2">
                  {s.with_battery.toLocaleString('en-IE')}
                </td>
                <td className="readout px-4 py-3 text-right text-ink-2">
                  {s.with_consumption.toLocaleString('en-IE')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassCard>

      {/* --- history --------------------------------------------------------- */}
      <h2 className="mb-3 mt-8 text-sm font-medium uppercase tracking-wider text-ink-3">
        Recent runs
      </h2>
      <GlassCard className="overflow-x-auto p-1">
        {runs.length === 0 ? (
          <p className="px-4 py-6 text-sm text-ink-3">Nothing has been refreshed yet.</p>
        ) : (
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wider text-ink-3">
                <th className="px-4 py-3 font-medium">Task</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Started</th>
                <th className="px-4 py-3 text-right font-medium">Took</th>
                <th className="px-4 py-3 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(run => (
                <tr key={run.id} className="border-t border-edge align-top">
                  <td className="px-4 py-3 text-ink">{run.task}</td>
                  <td className="px-4 py-3"><RunStatus status={run.status} /></td>
                  <td className="px-4 py-3 text-ink-2">{when(run.started_at)}</td>
                  <td className="readout px-4 py-3 text-right text-ink-2">
                    {took(run.duration_ms)}
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-3">
                    {run.error ? (
                      <span style={{ color: 'var(--critical)' }}>{run.error}</span>
                    ) : run.result ? (
                      Object.entries(run.result)
                        .filter(([, v]) => typeof v !== 'object')
                        .map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`)
                        .join(' · ')
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </GlassCard>

      {/* --- accounts -------------------------------------------------------- */}
      <h2 className="mb-3 mt-8 text-sm font-medium uppercase tracking-wider text-ink-3">
        Accounts
      </h2>
      <GlassCard className="overflow-x-auto p-1">
        <table className="w-full min-w-[34rem] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-ink-3">
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 text-right font-medium">Vehicles</th>
              <th className="px-4 py-3 font-medium">Last seen</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-t border-edge">
                <td className="px-4 py-3 text-ink">
                  {u.email}
                  {u.id === user?.id && <span className="ml-2 text-xs text-ink-3">(you)</span>}
                </td>
                <td className="px-4 py-3 text-ink-2">{u.role === 'admin' ? 'Admin' : 'User'}</td>
                <td className="readout px-4 py-3 text-right text-ink-2">{u.vehicles}</td>
                <td className="px-4 py-3 text-ink-2">{when(u.last_login_at)}</td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => changeRole(u, u.role === 'admin' ? 'user' : 'admin')}
                    className="focus-ring rounded-lg px-2 py-1 text-xs text-ink-3 hover:text-ink"
                  >
                    {u.role === 'admin' ? 'Remove admin' : 'Make admin'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassCard>

      <p className="mt-4 text-xs text-ink-3">
        Accounts are listed with their roles only. Vehicles and charges stay private to
        whoever logged them — admin covers the shared catalogue, not other people’s data.
      </p>
    </>
  )
}
