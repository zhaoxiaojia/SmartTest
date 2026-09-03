import { Chart, registerables } from 'chart.js'
import { createManualAuditApi, createProjectFactsApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { preferencesReady } from './main.js'
import { createProjects } from './projects.js'

const projectFactsApi = createProjectFactsApi()
const manualAuditApi = createManualAuditApi()
Chart.register(...registerables)

startAuthenticatedPage({
  mount: (root, session) => createProjects({
    root,
    account: session.username,
    api: { ...projectFactsApi, ...manualAuditApi },
    chartFactory: (canvas, config) => new Chart(canvas, config),
    waitForPreferences: async () => {
      await preferencesReady
      await new Promise(resolve => setTimeout(resolve, 0))
    },
  }),
})
