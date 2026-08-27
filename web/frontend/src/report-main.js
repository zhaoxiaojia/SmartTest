import { createAuthApi, createPreferenceApi, createProjectFactsApi, createReportWorkspaceApi } from './api.js'
import { createApp } from './app.js'
import { createConfluenceProjects } from './confluence-projects.js'
import { createReportWorkspace } from './report-workspace.js'

const api = createReportWorkspaceApi()
const projectFactsApi = createProjectFactsApi()
const app = createApp({
  root: document.querySelector('#app'),
  api: {},
  capabilities: {
    authApi: createAuthApi(),
    preferenceApi: createPreferenceApi(),
    reportWorkspace(source) {
      const section = document.createElement('div')
      return source === 'confluence'
        ? { section, start: () => createConfluenceProjects({ root: section, api: projectFactsApi }).start() }
        : { section, start: () => createReportWorkspace({ root: section, source, api }).start() }
    }
  }
})
app.start()
