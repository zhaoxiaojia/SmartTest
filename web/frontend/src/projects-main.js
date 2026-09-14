import { createManualAuditApi, createProjectFactsApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { preferencesReady } from './main.js'
import { createProjects } from './projects.js'

const projectFactsApi = createProjectFactsApi()
const manualAuditApi = createManualAuditApi()
startAuthenticatedPage({
  mount: (root, session) => createProjects({
    root,
    account: session.username,
    api: { ...projectFactsApi, ...manualAuditApi },
    waitForPreferences: async () => {
      await preferencesReady
      await new Promise(resolve => setTimeout(resolve, 0))
    },
    enableReview: false,
  }),
})
