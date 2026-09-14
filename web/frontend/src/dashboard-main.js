import { Chart, registerables } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { GridStack } from 'gridstack'
import 'gridstack/dist/gridstack.min.css'
import { createPreferenceApi, createProjectFactsApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { createDashboardGrid } from './dashboard/dashboard-grid.js'
import { createWidgetRegistry } from './dashboard/widget-registry.js'
import { createRoleWorkloadWidget, ROLE_WORKLOAD_LAYOUT } from './widgets/role-workload.js'

if (!window.location.pathname.startsWith('/wifi-database/')) {
  Chart.register(...registerables, ChartDataLabels)
  const preferenceApi = createPreferenceApi()
  const projectFactsApi = createProjectFactsApi()
  startAuthenticatedPage({ mount: root => {
    const registry = createWidgetRegistry()
    registry.register({
      type: 'role-workload', title: 'Role workload', ...ROLE_WORKLOAD_LAYOUT,
      create: () => createRoleWorkloadWidget({ chartFactory: (canvas, config) => new Chart(canvas, config) }),
    })
    return createDashboardGrid({
      root, registry, preferenceApi,
      gridFactory: (options, element) => GridStack.init(options, element),
      widgetConfig: async type => {
        if (type !== 'role-workload') return {}
        try {
          const payload = await projectFactsApi.getProjectFacts()
          return { ownerHierarchy: payload.ownerHierarchy ?? [], productSpaces: payload.productSpaces ?? [], shellTitle: true }
        } catch {
          return { error: 'Local project facts API is unavailable.', shellTitle: true }
        }
      },
    })
  } })
}
