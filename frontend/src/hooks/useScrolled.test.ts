import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useScrolled } from './useScrolled'
import { scrollTo } from '../test/setup'

/** Move the page and let the frame the hook is waiting on actually run. */
async function scrollAndSettle(y: number) {
  await act(async () => {
    scrollTo(y)
    await new Promise(r => setTimeout(r, 40))
  })
}

describe('useScrolled', () => {
  it('starts false at the top of the page', () => {
    scrollTo(0)
    const { result } = renderHook(() => useScrolled())
    expect(result.current).toBe(false)
  })

  it('turns true past the threshold', async () => {
    scrollTo(0)
    const { result } = renderHook(() => useScrolled(24))

    await scrollAndSettle(200)
    expect(result.current).toBe(true)
  })

  it('ignores a small bounce at the top', async () => {
    // iOS rubber-banding would otherwise flip the chrome back and forth.
    scrollTo(0)
    const { result } = renderHook(() => useScrolled(24))

    await scrollAndSettle(8)
    expect(result.current).toBe(false)
  })

  it('comes back down when the page returns to the top', async () => {
    scrollTo(300)
    const { result } = renderHook(() => useScrolled(24))
    await scrollAndSettle(300)
    expect(result.current).toBe(true)

    await scrollAndSettle(0)
    expect(result.current).toBe(false)
  })

  it('reads the position once per frame, not once per event', async () => {
    // The scroll event fires far more often than the screen repaints, and
    // reading scrollY in each one forces layout.
    scrollTo(0)
    const raf = vi.spyOn(window, 'requestAnimationFrame')
    renderHook(() => useScrolled())

    await act(async () => {
      for (let i = 0; i < 20; i++) scrollTo(100 + i)
    })
    expect(raf.mock.calls.length).toBeLessThan(20)
  })

  it('stops listening when unmounted', () => {
    const remove = vi.spyOn(window, 'removeEventListener')
    const { unmount } = renderHook(() => useScrolled())
    unmount()
    expect(remove).toHaveBeenCalledWith('scroll', expect.any(Function))
  })
})
