import { Chart, registerables } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { GridStack } from 'gridstack'
import 'gridstack/dist/gridstack.min.css'
import { createJiraTeamBugApi, createPreferenceApi, createProjectFactsApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { createDashboardGrid } from './dashboard/dashboard-grid.js'
import { createWidgetRegistry } from './dashboard/widget-registry.js'
import { createRoleWorkloadWidget, ROLE_WORKLOAD_LAYOUT } from './widgets/role-workload.js'
import { createJiraTeamBugWidget, JIRA_TEAM_BUG_LAYOUT } from './widgets/jira-team-bugs.js'

if (!window.location.pathname.startsWith('/wifi-database/')) {
  Chart.register(...registerables, ChartDataLabels)
  const preferenceApi = createPreferenceApi()
  const projectFactsApi = createProjectFactsApi()
  const jiraTeamBugApi = createJiraTeamBugApi()
  startAuthenticatedPage({ mount: root => {
    const registry = createWidgetRegistry()
    registry.register({
      type: 'role-workload', title: 'Role workload', ...ROLE_WORKLOAD_LAYOUT,
      create: () => createRoleWorkloadWidget({ chartFactory: (canvas, config) => new Chart(canvas, config) }),
    })
    registry.register({
      type: 'jira-team-bugs', title: 'Team Jira bugs', ...JIRA_TEAM_BUG_LAYOUT,
      create: () => createJiraTeamBugWidget({ chartFactory: (canvas, config) => new Chart(canvas, config) }),
    })
    return createDashboardGrid({
      root, registry, preferenceApi,
      gridFactory: (options, element) => GridStack.init(options, element),
      widgetConfig: async type => {
        if (type === 'jira-team-bugs') return { api: jiraTeamBugApi }
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
