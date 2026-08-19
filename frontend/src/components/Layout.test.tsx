import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Layout from './Layout'
import { AuthProvider } from '../hooks/useAuth'
import { ThemeProvider } from '../hooks/useTheme'
import { UnitsProvider } from '../hooks/useUnits'
import { CurrencyProvider } from '../hooks/useCurrency'
import { scrollTo } from '../test/setup'
import type { AuthUser } from '../api/auth'

// The real providers, with only the network stubbed — so the test exercises
// the wiring the app actually uses rather than a hand-built context.
vi.mock('../api/auth', () => ({
  getMe: vi.fn(),
  logout: vi.fn().mockResolvedValue(undefined),
}))
vi.mock('../api/currency', () => ({
  getRates: vi.fn().mockResolvedValue({
    base: 'EUR', rates: { EUR: 1 }, choices: [{ code: 'EUR', symbol: '€' }], source: 'test',
  }),
  setCurrency: vi.fn().mockResolvedValue(undefined),
}))

import { getMe } from '../api/auth'

const user: AuthUser = {
  id: 1, email: 'laura@example.com', display_name: 'Laura', avatar_url: null,
  has_password: true, has_google: false, is_admin: false, currency: 'EUR',
}

beforeEach(() => {
  vi.mocked(getMe).mockResolvedValue(user)
})

async function renderLayout(as: AuthUser = user) {
  vi.mocked(getMe).mockResolvedValue(as)
  const view = render(
    <ThemeProvider>
      <AuthProvider>
        <UnitsProvider>
          <CurrencyProvider>
            <MemoryRouter initialEntries={['/']}>
              <Routes>
                <Route path="/" element={<Layout />}>
                  <Route index element={<p>the page</p>} />
                  <Route path="stats" element={<p>stats</p>} />
                </Route>
              </Routes>
            </MemoryRouter>
          </CurrencyProvider>
        </UnitsProvider>
      </AuthProvider>
    </ThemeProvider>,
  )
  await waitFor(() => expect(screen.getByText('the page')).toBeInTheDocument())
  return view
}

async function scrollDown(y = 200) {
  await act(async () => {
    scrollTo(y)
    await new Promise(r => setTimeout(r, 40))
  })
}

describe('mobile chrome', () => {
  it('shows the tabs while the page is at the top', async () => {
    scrollTo(0)
    await renderLayout()
    expect(screen.getAllByRole('link', { name: 'Garage' }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /show navigation/i })).toBeNull()
  })

  it('folds the tabs into a button once the page moves', async () => {
    scrollTo(0)
    await renderLayout()
    await scrollDown()

    expect(screen.getByRole('button', { name: /show navigation/i })).toBeInTheDocument()
    // The tabs that remain belong to the desktop bar, which is hidden by CSS
    // rather than unmounted — so the bottom bar's copy is what disappears.
    expect(screen.getAllByRole('link', { name: 'Garage' })).toHaveLength(1)
  })

  it('brings the tabs back when the button is tapped', async () => {
    scrollTo(0)
    await renderLayout()
    await scrollDown()
    await userEvent.click(screen.getByRole('button', { name: /show navigation/i }))

    expect(screen.getAllByRole('link', { name: 'Garage' })).toHaveLength(2)
    expect(screen.queryByRole('button', { name: /show navigation/i })).toBeNull()
  })

  it('folds away again if the page is scrolled after opening it', async () => {
    scrollTo(0)
    await renderLayout()
    await scrollDown()
    await userEvent.click(screen.getByRole('button', { name: /show navigation/i }))

    await scrollDown(400)
    expect(screen.getByRole('button', { name: /show navigation/i })).toBeInTheDocument()
  })

  it('closes itself once you have gone somewhere', async () => {
    scrollTo(0)
    await renderLayout()
    await scrollDown()
    await userEvent.click(screen.getByRole('button', { name: /show navigation/i }))
    await userEvent.click(screen.getAllByRole('link', { name: 'Stats' })[0])

    expect(screen.getByRole('button', { name: /show navigation/i })).toBeInTheDocument()
  })

  it('marks the top bar so the stylesheet can collapse it', async () => {
    // The pill is CSS, keyed off this attribute; jsdom does no layout, so the
    // flag is the honest thing to assert here.
    scrollTo(0)
    const { container } = await renderLayout()
    const bar = container.querySelector('.top-bar')!
    expect(bar).toHaveAttribute('data-scrolled', 'false')

    await scrollDown()
    expect(bar).toHaveAttribute('data-scrolled', 'true')
  })

  it('keeps the badge and the theme toggle in the collapsed bar', async () => {
    scrollTo(0)
    await renderLayout()
    await scrollDown()

    expect(screen.getByRole('button', { name: /account/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /theme|dark|light/i })).toBeInTheDocument()
  })

  it('offers the Admin tab only to an admin', async () => {
    scrollTo(0)
    await renderLayout({ ...user, is_admin: true })
    // The frame renders before /auth/me settles, so the tab arrives a tick later.
    expect((await screen.findAllByRole('link', { name: 'Admin' })).length).toBeGreaterThan(0)
  })

  it('does not offer it to anyone else', async () => {
    scrollTo(0)
    await renderLayout()
    expect(screen.queryByRole('link', { name: 'Admin' })).toBeNull()
  })
})
