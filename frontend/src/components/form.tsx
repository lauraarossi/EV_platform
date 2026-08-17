import type { ReactNode, InputHTMLAttributes, SelectHTMLAttributes } from 'react'

const controlClass =
  'focus-ring w-full rounded-lg border border-edge bg-surface-solid px-3 py-2 text-sm text-ink placeholder:text-ink-3'

export function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string
  hint?: string
  required?: boolean
  children: ReactNode
}) {
  // Column layout with the control pushed to the bottom, so a label that wraps
  // to two lines doesn't shove its input out of line with the rest of the row.
  return (
    <label className="flex h-full flex-col">
      <span className="text-[11px] uppercase tracking-wider text-ink-3">
        {label}
        {required && <span className="text-critical"> *</span>}
      </span>
      <div className="mt-1.5 mt-auto pt-1.5">{children}</div>
      {hint && <p className="mt-1 text-[11px] text-ink-3">{hint}</p>}
    </label>
  )
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const numeric = props.type === 'number'
  return <input {...props} className={`${controlClass} ${numeric ? 'readout' : ''}`} />
}

export function Select({
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { children: ReactNode }) {
  return (
    <select {...props} className={controlClass}>
      {children}
    </select>
  )
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg px-3 py-2 text-sm"
      style={{
        background: 'color-mix(in oklab, var(--critical) 12%, transparent)',
        border: '1px solid color-mix(in oklab, var(--critical) 35%, transparent)',
      }}
    >
      {/* icon + text, so the status colour never carries the meaning alone */}
      <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none"
        stroke="var(--critical)" strokeWidth="2" strokeLinecap="round" className="mt-0.5 shrink-0">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v5M12 16.5v.01" />
      </svg>
      <span className="text-ink">{message}</span>
    </div>
  )
}
