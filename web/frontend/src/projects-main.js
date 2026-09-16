import { Chart, registerables } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { createManualAuditApi, createProjectFactsApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { preferencesReady } from './main.js'
import { createProjects } from './projects.js'
import { createRoleWorkloadWidget } from './widgets/role-workload.js'

const projectFactsApi = createProjectFactsApi()
const manualAuditApi = createManualAuditApi()
Chart.register(...registerables, ChartDataLabels)
startAuthenticatedPage({
  mount: (root, session) => {
    root.innerHTML = `<section class="card page-ranking-widget" data-page-widget="role-workload"><header class="dashboard-widget-head"><strong>Role workload</strong></header><div data-widget-body></div></section><div data-page-primary></div>`
    const workload = createRoleWorkloadWidget({ chartFactory: (canvas, config) => new Chart(canvas, config) })
    const projects = createProjects({
      root: root.querySelector('[data-page-primary]'),
      account: session.username,
      api: { ...projectFactsApi, ...manualAuditApi },
      waitForPreferences: async () => {
        await preferencesReady
        await new Promise(resolve => setTimeout(resolve, 0))
      },
      enableReview: false,
    })
    let disposed = false
    void projectFactsApi.getProjectFacts().then(payload => {
      if (!disposed) workload.mount(root.querySelector('[data-widget-body]'), {
        ownerHierarchy: payload.ownerHierarchy ?? [], productSpaces: payload.productSpaces ?? [], shellTitle: true,
      })
    }).catch(() => {
      if (!disposed) workload.mount(root.querySelector('[data-widget-body]'), { error: 'Local project facts API is unavailable.', shellTitle: true })
    })
    return { start: () => projects.start(), destroy() { disposed = true; workload.destroy(); projects.destroy() } }
  },
})
