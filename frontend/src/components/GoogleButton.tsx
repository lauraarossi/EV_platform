import { useEffect, useRef } from 'react'
import { useTheme } from '../hooks/useTheme'

const SCRIPT_SRC = 'https://accounts.google.com/gsi/client'

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void
          renderButton: (el: HTMLElement, options: Record<string, unknown>) => void
        }
      }
    }
  }
}

function loadScript(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve()

  const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_SRC}"]`)
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener('load', () => resolve())
      existing.addEventListener('error', () => reject(new Error('Google script failed')))
    })
  }

  return new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = SCRIPT_SRC
    s.async = true
    s.defer = true
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('Google script failed'))
    document.head.appendChild(s)
  })
}

/**
 * Google's own button, which hands back a signed credential that the backend
 * verifies. Nothing is trusted client-side — the token is checked against
 * Google's public keys, including that it was issued for this app.
 */
export default function GoogleButton({
  clientId,
  onCredential,
  onError,
}: {
  clientId: string
  onCredential: (credential: string) => void
  onError: (message: string) => void
}) {
  const holder = useRef<HTMLDivElement>(null)
  const { theme } = useTheme()

  useEffect(() => {
    let cancelled = false

    loadScript()
      .then(() => {
        if (cancelled || !holder.current || !window.google) return
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response: { credential?: string }) => {
            if (response.credential) onCredential(response.credential)
            else onError('Google did not return a credential')
          },
        })
        // Rendering appends, so without clearing first a theme toggle leaves
        // two Google buttons stacked in the card.
        holder.current.replaceChildren()
        window.google.accounts.id.renderButton(holder.current, {
          // Google draws this button itself, in its own iframe, so none of our
          // styling reaches inside it — the theme is the only lever we have.
          // "filled_black" is the closest thing to transparent on a dark page;
          // "outline" is a white card, which is what looked pasted on.
          theme: theme === 'dark' ? 'filled_black' : 'outline',
          size: 'large',
          width: 320,
          text: 'continue_with',
          shape: 'pill',
        })
      })
      .catch(() => {
        if (!cancelled) onError("Couldn't load Google sign-in")
      })

    return () => {
      cancelled = true
    }
  }, [clientId, theme, onCredential, onError])

  // The personalised form of the button ("Continue as …") draws a white card
  // whatever theme is asked for. Clipping to the same pill the button uses at
  // least keeps its corners from showing as a rectangle behind it.
  return (
    <div className="flex justify-center">
      <div ref={holder} className="overflow-hidden rounded-full" />
    </div>
  )
}
