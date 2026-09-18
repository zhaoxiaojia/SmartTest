import { Chart, registerables } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { createJiraAnalyticsApi, createJiraTeamBugApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { createJiraFilterBuilder } from './jira-filter-builder.js'
import { createJiraTeamBugWidget, JIRA_SELF_TEST_TITLE, JIRA_CUSTOMER_TITLE } from './widgets/jira-team-bugs.js'

const api = createJiraAnalyticsApi()
const teamBugApi = createJiraTeamBugApi({ cardKey: 'self-test' })
Chart.register(...registerables, ChartDataLabels)

startAuthenticatedPage({ mount: (root, session) => {
  root.innerHTML = `<div data-page-primary></div><section class="card page-ranking-widget" data-page-widget="jira-team-bugs"><header class="dashboard-widget-head"><strong>${JIRA_SELF_TEST_TITLE}</strong></header><div data-widget-body></div></section><section class="card page-ranking-widget" data-page-widget="jira-customer-statistics"><header class="dashboard-widget-head"><strong>${JIRA_CUSTOMER_TITLE}</strong></header><div data-widget-body data-customer-body></div></section>`
  const overview = createJiraTeamBugWidget({ chartFactory: (canvas, config) => new Chart(canvas, config) })
  const filter = createJiraFilterBuilder({ root: root.querySelector('[data-page-primary]'), api, account: session.username, onApplied: () => overview.update({ query: true }) })
  overview.mount(root.querySelector('[data-widget-body]'), { api: teamBugApi, account: session.username })
  return { start: () => filter.start(), destroy() { overview.destroy(); filter.destroy() } }
} })
