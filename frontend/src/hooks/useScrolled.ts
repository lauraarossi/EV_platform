import { useEffect, useState } from 'react'

/**
 * Whether the page has been scrolled past a threshold.
 *
 * Read inside a rAF rather than straight from the scroll event: the handler
 * fires far more often than the screen repaints, and reading scrollY in each
 * one forces layout every time.
 *
 * The threshold is deliberately past zero, so a rubber-band bounce at the top
 * of iOS does not flip the chrome back and forth.
 */
export function useScrolled(threshold = 24): boolean {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    let frame = 0

    const read = () => {
      frame = 0
      setScrolled(window.scrollY > threshold)
    }
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(read)
    }

    read()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [threshold])

  return scrolled
}
