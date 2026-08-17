import { useEffect, useState } from 'react'

/**
 * A value that settles before anything acts on it.
 *
 * Dragging a slider fires on every pixel; without this each one would be a
 * round trip, and the answers would arrive out of order.
 */
export function useDebounced<T>(value: T, ms = 250): T {
  const [settled, setSettled] = useState(value)

  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), ms)
    return () => window.clearTimeout(timer)
  }, [value, ms])

  return settled
}
