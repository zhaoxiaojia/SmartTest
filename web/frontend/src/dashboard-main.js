import { createProjectFactsApi, createReleaseApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { createProjects } from './projects.js'
import { createReleaseDashboard } from './release-dashboard.js'

if (!window.location.pathname.startsWith('/wifi-database/')) {
  startAuthenticatedPage({ mount: (root, session) => {
    root.innerHTML = '<div data-global-confluence-filter></div><div data-release-dashboard></div>'
    const filter = createProjects({
      root: root.querySelector('[data-global-confluence-filter]'), api: createProjectFactsApi(),
      account: session.username, enableReview: false, filterOnly: true,
    })
    const dashboard = createReleaseDashboard({ root: root.querySelector('[data-release-dashboard]'), api: createReleaseApi() })
    return {
      async start() { await filter.start(); await dashboard.start() },
      destroy() { filter.destroy(); dashboard.destroy() },
    }
  } })
}
