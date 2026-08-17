import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Garage from './pages/Garage'
import Charges from './pages/Charges'
import Stats from './pages/Stats'
import Compare from './pages/Compare'
import Admin from './pages/Admin'
import SignIn from './pages/SignIn'
import { useAuth } from './hooks/useAuth'

export default function App() {
  const { user, ready } = useAuth()

  // Until /auth/me has answered we don't know which way to go; rendering the
  // sign-in page first would flash it at people who are already signed in.
  if (!ready) {
    return (
      <div className="grid min-h-svh place-items-center">
        <p className="text-sm text-ink-3">Loading…</p>
      </div>
    )
  }

  if (!user) return <SignIn />

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          {/* Logging is the thing you do most, so it is the landing page. */}
          <Route index element={<Charges />} />
          <Route path="garage" element={<Garage />} />
          <Route path="stats" element={<Stats />} />
          <Route path="compare" element={<Compare />} />
          {/* Routed only for admins, so the page cannot be reached by typing
              the URL. The API refuses regardless — this just avoids showing a
              screenful of failed requests. */}
          {user.is_admin && <Route path="admin" element={<Admin />} />}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
