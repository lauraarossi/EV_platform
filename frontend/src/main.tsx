import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ThemeProvider } from './hooks/useTheme'
import { AuthProvider } from './hooks/useAuth'
import { UnitsProvider } from './hooks/useUnits'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <UnitsProvider>
          <App />
        </UnitsProvider>
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>,
)
