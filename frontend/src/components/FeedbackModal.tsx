import { useState, type FormEvent } from 'react'
import { sendFeedback } from '../api/feedback'
import Modal from './Modal'
import { Field, TextInput } from './form'
import { useAuth } from '../hooks/useAuth'

/**
 * The form behind "tell me what is wrong".
 *
 * Asks for as little as possible: a message, and an address only if they want
 * an answer. Which page they were on is taken from the URL rather than asked
 * for, since it is the part people never think to include and the part that
 * makes a vague report actionable.
 */
export default function FeedbackModal({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const { user } = useAuth()
  const [message, setMessage] = useState('')
  const [email, setEmail] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const close = () => {
    onClose()
    // Reset only after it has gone, so the reset is not visible on the way out.
    window.setTimeout(() => {
      setMessage('')
      setSent(false)
      setError(null)
    }, 200)
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setSending(true)
    setError(null)
    try {
      await sendFeedback(message, window.location.pathname, email)
      setSent(true)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? 'That did not send. Try again in a moment.')
    } finally {
      setSending(false)
    }
  }

  return (
    <Modal open={open} title={sent ? 'Thank you' : 'Tell me what is wrong'} onClose={close}>
      {sent ? (
        <div className="p-5">
          <p className="text-sm leading-relaxed text-ink-2">
            That has landed, along with the page you were on. It genuinely does change what
            gets built next.
          </p>
          <button
            type="button"
            onClick={close}
            className="btn-primary focus-ring mt-4 rounded-lg px-4 py-2 text-sm font-medium"
          >
            Close
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="p-5">
          <p className="mb-4 text-sm leading-relaxed text-ink-3">
            Anything at all — something broken, something confusing, something missing. The
            page you are on is sent along with it.
          </p>

          <Field label="What happened?">
            <textarea
              value={message}
              onChange={e => setMessage(e.target.value)}
              required
              maxLength={4000}
              rows={5}
              autoFocus
              placeholder="The efficiency figure on Stats looks far too low for my car…"
              className="focus-ring w-full rounded-lg border border-edge bg-transparent px-3 py-2 text-sm text-ink placeholder:text-ink-3"
            />
          </Field>

          {!user && (
            <div className="mt-3">
              <Field label="Email, only if you want a reply">
                <TextInput
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </Field>
            </div>
          )}

          {error && (
            <p className="mt-3 text-sm" style={{ color: 'var(--critical)' }}>
              {error}
            </p>
          )}

          <div className="mt-4 flex items-center gap-2">
            <button
              type="submit"
              disabled={sending || message.trim() === ''}
              className="btn-primary focus-ring rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
            >
              {sending ? 'Sending…' : 'Send'}
            </button>
            <button
              type="button"
              onClick={close}
              className="focus-ring rounded-lg px-4 py-2 text-sm text-ink-3 hover:text-ink"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}
