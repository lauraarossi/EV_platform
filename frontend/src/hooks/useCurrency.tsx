import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { getRates, setCurrency as save, type CurrencyChoice } from '../api/currency'
import { useAuth } from './useAuth'

/**
 * Showing money in the currency someone actually uses.
 *
 * Amounts are held in euro — the fuel prices arrive that way, and so do the
 * ECB's rates — and converted here, at the edge, exactly as the unit system
 * converts distances. Converting on the way in would bake the rate of the day
 * into the stored figure, which is impossible to reason about later.
 *
 * The choice lives on the account rather than in the browser, unlike units: it
 * changes how the money you entered reads back, so it should follow you to a
 * phone rather than reset to euro there.
 */
interface CurrencyState {
  code: string
  symbol: string
  choices: CurrencyChoice[]
  /** Euro in, chosen currency out. */
  convert: (eur: number) => number
  format: (eur: number | null | undefined, digits?: number) => string
  choose: (code: string) => Promise<void>
  /** True when no rate is known, so figures are still euro. */
  unconverted: boolean
}

const CurrencyContext = createContext<CurrencyState | null>(null)

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [code, setCode] = useState(user?.currency ?? 'EUR')
  const [rates, setRates] = useState<Record<string, number>>({ EUR: 1 })
  const [choices, setChoices] = useState<CurrencyChoice[]>([{ code: 'EUR', symbol: '€' }])

  useEffect(() => {
    if (!user) return
    setCode(user.currency ?? 'EUR')
    getRates()
      .then(r => {
        setRates(r.rates)
        setChoices(r.choices)
      })
      .catch(() => {})
  }, [user])

  const rate = rates[code]
  const symbol = choices.find(c => c.code === code)?.symbol ?? '€'

  const convert = useCallback((eur: number) => eur * (rate ?? 1), [rate])

  const format = useCallback(
    (eur: number | null | undefined, digits = 2) => {
      if (eur == null) return '—'
      const value = eur * (rate ?? 1)
      return `${symbol}${value.toLocaleString('en-IE', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })}`
    },
    [rate, symbol],
  )

  const choose = useCallback(async (next: string) => {
    await save(next)
    setCode(next)
  }, [])

  return (
    <CurrencyContext.Provider
      value={{ code, symbol, choices, convert, format, choose, unconverted: rate == null }}
    >
      {children}
    </CurrencyContext.Provider>
  )
}

export function useCurrency() {
  const ctx = useContext(CurrencyContext)
  if (!ctx) throw new Error('useCurrency must be used inside CurrencyProvider')
  return ctx
}
