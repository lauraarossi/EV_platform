import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ThemeProvider } from './hooks/useTheme'
import { AuthProvider } from './hooks/useAuth'
import { UnitsProvider } from './hooks/useUnits'
import { CurrencyProvider } from './hooks/useCurrency'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <UnitsProvider>
          <CurrencyProvider>
            <App />
          </CurrencyProvider>
        </UnitsProvider>
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>,
)
