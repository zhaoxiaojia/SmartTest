import { startAuthenticatedPage } from './authenticated-page.js'

if (!window.location.pathname.startsWith('/wifi-database/')) {
  startAuthenticatedPage({ mount: root => {
    root.replaceChildren()
    return {
      async start() {},
      destroy() {},
    }
  } })
}
