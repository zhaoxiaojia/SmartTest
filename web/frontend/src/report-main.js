import { Chart, registerables } from 'chart.js'
import { createProjectFactsApi, createReportWorkspaceApi } from './api.js'
import { createConfluenceProjects } from './confluence-projects.js'
import { shellReady } from './main.js'
import { createReportWorkspace } from './report-workspace.js'

const api = createReportWorkspaceApi()
const projectFactsApi = createProjectFactsApi()
Chart.register(...registerables)
const root = document.querySelector('main.main-content')
const source = window.location.pathname === '/confluence.html' ? 'confluence' : 'jira'
const section = document.createElement('div')
root.replaceChildren(section)
if (source === 'confluence') createConfluenceProjects({
  root: section,
  api: projectFactsApi,
  chartFactory: (canvas, config) => new Chart(canvas, config),
  waitForPreferences: async () => {
    await shellReady
    await new Promise(resolve => setTimeout(resolve, 0))
  }
}).start()
else createReportWorkspace({ root: section, source, api }).start()
