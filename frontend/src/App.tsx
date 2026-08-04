import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Garage from './pages/Garage'
import Charges from './pages/Charges'
import Stats from './pages/Stats'
import Compare from './pages/Compare'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          {/* Logging is the thing you do most, so it is the landing page. */}
          <Route index element={<Charges />} />
          <Route path="garage" element={<Garage />} />
          <Route path="stats" element={<Stats />} />
          <Route path="compare" element={<Compare />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
