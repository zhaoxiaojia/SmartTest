import { Chart, registerables } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { createJiraAnalyticsApi, createJiraTeamBugApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { createJiraFilterBuilder } from './jira-filter-builder.js'
import { createJiraTeamBugWidget } from './widgets/jira-team-bugs.js'

const api = createJiraAnalyticsApi()
const teamBugApi = createJiraTeamBugApi()
Chart.register(...registerables, ChartDataLabels)

startAuthenticatedPage({ mount: (root, session) => {
  root.innerHTML = `<section class="card page-ranking-widget" data-page-widget="jira-team-bugs"><header class="dashboard-widget-head"><strong>Team Jira bugs</strong></header><div data-widget-body></div></section><div data-page-primary></div>`
  const overview = createJiraTeamBugWidget({ chartFactory: (canvas, config) => new Chart(canvas, config) })
  const filter = createJiraFilterBuilder({ root: root.querySelector('[data-page-primary]'), api, account: session.username })
  overview.mount(root.querySelector('[data-widget-body]'), { api: teamBugApi })
  return { start: () => filter.start(), destroy() { overview.destroy(); filter.destroy() } }
} })
