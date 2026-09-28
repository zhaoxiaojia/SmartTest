import { Chart, registerables } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { createJiraAnalyticsApi, createJiraStatisticsCardApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { createJiraFilterBuilder } from './jira-filter-builder.js'
import { createJiraStatisticsCard, JIRA_STATISTICS_CARDS } from './widgets/jira-statistics-card.js'

const api = createJiraAnalyticsApi()
const cards = Object.entries(JIRA_STATISTICS_CARDS).map(([cardKey, metadata]) => ({
  cardKey, metadata, api: createJiraStatisticsCardApi({ cardKey }),
}))
Chart.register(...registerables, ChartDataLabels)

startAuthenticatedPage({ mount: (root, session) => {
  root.innerHTML = `<div data-page-primary></div>${cards.map(({ cardKey, metadata }) => `<section class="card page-ranking-widget" data-page-widget="jira-${cardKey}"><header class="dashboard-widget-head"><strong>${metadata.title}</strong></header><div data-widget-body="${cardKey}"></div></section>`).join('')}`
  const widgets = cards.map(({ cardKey, api: cardApi }) => {
    const widget = createJiraStatisticsCard({ chartFactory: (canvas, config) => new Chart(canvas, config) })
    widget.mount(root.querySelector(`[data-widget-body="${cardKey}"]`), { api: cardApi, account: session.username, cardKey })
    return widget
  })
  const filter = createJiraFilterBuilder({ root: root.querySelector('[data-page-primary]'), api, account: session.username, onApplied: () => widgets.forEach(widget => widget.update({ query: true })) })
  return { start: () => filter.start(), destroy() { widgets.forEach(widget => widget.destroy()); filter.destroy() } }
} })
