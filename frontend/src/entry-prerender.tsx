import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import Landing from './pages/Landing'

/**
 * The landing page, rendered to HTML at build time.
 *
 * Without this the page a crawler receives is an empty <div id="root">: the
 * copy only exists once JavaScript has run, and Google renders JavaScript on a
 * second pass that runs days or weeks behind for a new domain. The words that
 * are supposed to be indexed were not in the document at all.
 *
 * Only this page. Everything else needs an account, so there is nothing for a
 * crawler to see and no reason to pay for rendering it.
 */
export function render(): string {
  return renderToString(
    <MemoryRouter initialEntries={['/']}>
      <Landing />
    </MemoryRouter>,
  )
}
