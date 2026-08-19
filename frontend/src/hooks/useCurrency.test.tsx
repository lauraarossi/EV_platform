import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { CurrencyProvider, useCurrency } from './useCurrency'
import { AuthProvider } from './useAuth'
import type { AuthUser } from '../api/auth'

vi.mock('../api/auth', () => ({ getMe: vi.fn(), logout: vi.fn() }))
vi.mock('../api/currency', () => ({ getRates: vi.fn(), setCurrency: vi.fn() }))

import { getMe } from '../api/auth'
import { getRates, setCurrency } from '../api/currency'

const user: AuthUser = {
  id: 1, email: 'l@example.com', display_name: null, avatar_url: null,
  has_password: true, has_google: false, is_admin: false, currency: 'EUR',
}

const RATES = {
  base: 'EUR',
  rates: { EUR: 1, GBP: 0.85585, USD: 1.1576 },
  choices: [
    { code: 'EUR', symbol: '€' },
    { code: 'GBP', symbol: '£' },
    { code: 'USD', symbol: '$' },
  ],
  source: 'test',
}

const wrapper = ({ children }: { children: ReactNode }) => (
  <AuthProvider>
    <CurrencyProvider>{children}</CurrencyProvider>
  </AuthProvider>
)

async function currency(as: Partial<AuthUser> = {}) {
  vi.mocked(getMe).mockResolvedValue({ ...user, ...as })
  vi.mocked(getRates).mockResolvedValue(RATES)
  const { result } = renderHook(() => useCurrency(), { wrapper })
  await waitFor(() => expect(getRates).toHaveBeenCalled())
  return result
}

beforeEach(() => {
  vi.mocked(setCurrency).mockResolvedValue(undefined)
})

describe('showing money in the chosen currency', () => {
  it('leaves euro amounts alone', async () => {
    const result = await currency()
    await waitFor(() => expect(result.current.code).toBe('EUR'))
    expect(result.current.format(43.92)).toBe('€43.92')
  })

  it('converts to the account currency', async () => {
    const result = await currency({ currency: 'GBP' })
    await waitFor(() => expect(result.current.code).toBe('GBP'))
    // 100 euro at 0.85585.
    expect(result.current.format(100)).toBe('£85.59')
    expect(result.current.convert(100)).toBeCloseTo(85.585, 3)
  })

  it('honours the digits asked for, since a per-kWh price needs three', async () => {
    const result = await currency({ currency: 'USD' })
    await waitFor(() => expect(result.current.code).toBe('USD'))
    expect(result.current.format(0.3, 3)).toBe('$0.347')
  })

  it('has nothing to show for a missing amount', async () => {
    const result = await currency()
    expect(result.current.format(null)).toBe('—')
    expect(result.current.format(undefined)).toBe('—')
  })

  it('takes the choice from the account, not the browser', async () => {
    // It changes how entered money reads back, so it has to follow the person
    // to another device rather than reset to euro there.
    const result = await currency({ currency: 'USD' })
    await waitFor(() => expect(result.current.code).toBe('USD'))
    expect(result.current.symbol).toBe('$')
  })

  it('saves a new choice and shows it straight away', async () => {
    const result = await currency()
    await waitFor(() => expect(result.current.code).toBe('EUR'))

    await act(async () => {
      await result.current.choose('GBP')
    })

    expect(setCurrency).toHaveBeenCalledWith('GBP')
    expect(result.current.code).toBe('GBP')
    expect(result.current.format(100)).toBe('£85.59')
  })

  it('falls back to euro figures when no rate is known', async () => {
    vi.mocked(getMe).mockResolvedValue({ ...user, currency: 'GBP' })
    vi.mocked(getRates).mockResolvedValue({ ...RATES, rates: { EUR: 1 } })
    const { result } = renderHook(() => useCurrency(), { wrapper })

    await waitFor(() => expect(result.current.code).toBe('GBP'))
    // Reported rather than silently multiplied by one, so the interface can say so.
    expect(result.current.unconverted).toBe(true)
    expect(result.current.convert(100)).toBe(100)
  })
})
