import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// jsdom implements neither, and the app leans on both: the layout reads scroll
// position inside a frame, and the theme asks the OS what it prefers.
if (!window.requestAnimationFrame) {
  window.requestAnimationFrame = (cb: FrameRequestCallback) =>
    window.setTimeout(() => cb(performance.now()), 0) as unknown as number
  window.cancelAnimationFrame = (id: number) => window.clearTimeout(id)
}

if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}

/** Move the page and let the listeners see it. */
export function scrollTo(y: number) {
  Object.defineProperty(window, 'scrollY', { value: y, writable: true, configurable: true })
  window.dispatchEvent(new Event('scroll'))
}
