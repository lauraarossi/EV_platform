import { useCallback, useEffect, useState, type FormEvent } from 'react'
import * as authApi from '../api/auth'
import type { AuthOptions } from '../api/auth'
import { useAuth } from '../hooks/useAuth'
import GlassCard from '../components/GlassCard'
import GoogleButton from '../components/GoogleButton'
import { Field, TextInput, FormError } from '../components/form'

function describeError(e: unknown): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(d => d.msg).join(' · ')
  return e instanceof Error ? e.message : 'Something went wrong'
}

export default function SignIn() {
  const { signIn } = useAuth()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [options, setOptions] = useState<AuthOptions | null>(null)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    authApi.getOptions().then(setOptions).catch(() => setOptions(null))
  }, [])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const user =
        mode === 'signin'
          ? await authApi.login(email, password)
          : await authApi.register(email, password)
      signIn(user)
    } catch (err) {
      setError(describeError(err))
      setBusy(false)
    }
  }

  const onCredential = useCallback(
    async (credential: string) => {
      setError(null)
      try {
        signIn(await authApi.signInWithGoogle(credential))
      } catch (err) {
        setError(describeError(err))
      }
    },
    [signIn]
  )

  const signingUp = mode === 'signup'

  return (
    <div className="grid min-h-svh place-items-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <span
            aria-hidden="true"
            className="grid h-9 w-9 place-items-center rounded-lg"
            style={{ background: 'linear-gradient(135deg, var(--accent-2), var(--accent))' }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-ink)"
                 strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M13 2 4 14h7l-1 8 9-12h-7z" />
            </svg>
          </span>
          <span className="text-xl font-semibold tracking-tight text-ink">Eevie</span>
        </div>

        <GlassCard glassSheen className="p-6">
          <h1 className="text-lg font-semibold text-ink">
            {signingUp ? 'Create your account' : 'Welcome back'}
          </h1>
          <p className="mt-1 text-sm text-ink-2">
            {signingUp
              ? 'Track what your EV really costs to run.'
              : 'Sign in to keep logging your charges.'}
          </p>

          <form onSubmit={submit} className="mt-5 space-y-4">
            <FormError message={error} />

            <Field label="Email" required>
              <TextInput
                type="email" value={email} required autoComplete="email"
                onChange={e => setEmail(e.target.value)} placeholder="you@example.com"
              />
            </Field>

            <Field
              label="Password"
              required
              hint={signingUp ? 'At least 8 characters' : undefined}
            >
              <TextInput
                type="password" value={password} required minLength={signingUp ? 8 : undefined}
                autoComplete={signingUp ? 'new-password' : 'current-password'}
                onChange={e => setPassword(e.target.value)} placeholder="••••••••"
              />
            </Field>

            <button
              type="submit" disabled={busy}
              className="btn-primary focus-ring w-full rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-60"
            >
              {busy ? 'One moment…' : signingUp ? 'Create account' : 'Sign in'}
            </button>
          </form>

          {options?.google_enabled && options.google_client_id && (
            <>
              <div className="my-5 flex items-center gap-3">
                <span className="h-px flex-1 bg-edge" />
                <span className="text-[11px] uppercase tracking-wider text-ink-3">or</span>
                <span className="h-px flex-1 bg-edge" />
              </div>
              <GoogleButton
                clientId={options.google_client_id}
                onCredential={onCredential}
                onError={setError}
              />
            </>
          )}

          {options?.registration_open !== false && (
            <p className="mt-5 text-center text-sm text-ink-2">
              {signingUp ? 'Already have an account?' : "Don't have an account?"}{' '}
              <button
                type="button"
                onClick={() => {
                  setMode(signingUp ? 'signin' : 'signup')
                  setError(null)
                }}
                className="focus-ring rounded font-medium text-accent hover:underline"
              >
                {signingUp ? 'Sign in' : 'Create one'}
              </button>
            </p>
          )}
        </GlassCard>
      </div>
    </div>
  )
}
