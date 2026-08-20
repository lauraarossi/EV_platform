import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { Providers } from '../Providers'

vi.mock('../api/auth', () => ({
  getMe: vi.fn(),
  logout: vi.fn(),
  getOptions: vi.fn().mockResolvedValue({
    google_enabled: false, registration_open: true, google_client_id: null,
  }),
  login: vi.fn(),
  register: vi.fn(),
  signInWithGoogle: vi.fn(),
}))
vi.mock('../api/currency', () => ({
  getRates: vi.fn().mockResolvedValue({ base: 'EUR', rates: { EUR: 1 }, choices: [], source: 't' }),
  setCurrency: vi.fn(),
}))

import { getMe } from '../api/auth'

beforeEach(() => {
  // Signed out: the session cookie is absent, so /auth/me refuses.
  vi.mocked(getMe).mockRejectedValue(new Error('401'))
  window.history.pushState({}, '', '/')
})

describe('the front door', () => {
  it('describes the product rather than asking for a password', async () => {
    render(<Providers><App /></Providers>)

    const heading = await screen.findByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent(/what your car actually costs to run/i)
    // The thing a crawler needs and a login form does not have: prose.
    expect(screen.getByText(/log every charge and fill-up/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).toBeNull()
  })

  it('has exactly one h1, which is what gets indexed', async () => {
    render(<Providers><App /></Providers>)
    await screen.findByRole('heading', { level: 1 })
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('explains why a manufacturer figure is not enough', async () => {
    // The reason the app exists; if this copy goes, the page says nothing
    // a hundred other pages do not.
    render(<Providers><App /></Providers>)
    expect(await screen.findByText(/laboratory figure is not your car/i)).toBeInTheDocument()
  })

  it('leads to the form without being the form', async () => {
    render(<Providers><App /></Providers>)
    const links = await screen.findAllByRole('link', { name: /sign in|start logging|create an account/i })
    expect(links.length).toBeGreaterThan(0)

    await userEvent.click(links[0])
    await waitFor(() => expect(screen.getByLabelText(/password/i)).toBeInTheDocument())
  })

  it('offers a way back out of the form', async () => {
    render(<Providers><App /></Providers>)
    await userEvent.click((await screen.findAllByRole('link', { name: /sign in/i }))[0])
    await waitFor(() => expect(screen.getByLabelText(/password/i)).toBeInTheDocument())

    await userEvent.click(screen.getByRole('link', { name: /eevie/i }))
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/actually costs/i),
    )
  })

  it('sends an unknown address to the landing page, not to a blank screen', async () => {
    window.history.pushState({}, '', '/garage')
    render(<Providers><App /></Providers>)
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(/actually costs/i)
  })
})
