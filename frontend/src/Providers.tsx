import type { ReactNode } from 'react'
import { ThemeProvider } from './hooks/useTheme'
import { AuthProvider } from './hooks/useAuth'
import { UnitsProvider } from './hooks/useUnits'
import { CurrencyProvider } from './hooks/useCurrency'

/**
 * Everything the app reads from context, in one place.
 *
 * Kept out of main.tsx so tests mount the same stack the browser does, rather
 * than a hand-assembled approximation that can quietly drift from it. Order
 * matters: currency asks the account which one to show.
 */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <UnitsProvider>
          <CurrencyProvider>{children}</CurrencyProvider>
        </UnitsProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
