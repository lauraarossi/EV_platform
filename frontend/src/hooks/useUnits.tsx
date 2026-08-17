import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { makeUnits, type UnitSystem, type Units } from '../units'

const STORAGE_KEY = 'ev-platform-units'

function initialSystem(): UnitSystem {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'metric' || stored === 'imperial') return stored
  // Ireland is metric, and so is the API, so that is the sensible default.
  return 'metric'
}

interface UnitsState {
  units: Units
  setSystem: (s: UnitSystem) => void
  toggle: () => void
}

const UnitsContext = createContext<UnitsState | null>(null)

export function UnitsProvider({ children }: { children: ReactNode }) {
  const [system, setSystemState] = useState<UnitSystem>(initialSystem)

  const setSystem = useCallback((s: UnitSystem) => {
    setSystemState(s)
    localStorage.setItem(STORAGE_KEY, s)
  }, [])

  const toggle = useCallback(
    () => setSystem(system === 'metric' ? 'imperial' : 'metric'),
    [system, setSystem]
  )

  const units = useMemo(() => makeUnits(system), [system])

  return (
    <UnitsContext.Provider value={{ units, setSystem, toggle }}>{children}</UnitsContext.Provider>
  )
}

export function useUnits() {
  const ctx = useContext(UnitsContext)
  if (!ctx) throw new Error('useUnits must be used inside UnitsProvider')
  return ctx
}
