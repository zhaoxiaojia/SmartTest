import { createManualAuditApi, createReleaseApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { createJiraWorkbench } from './jira-workbench.js'

const api = { ...createManualAuditApi(), ...createReleaseApi() }
const query = new URLSearchParams(window.location.search)
const snapshot = query.get('snapshot') || ''
const projectId = query.get('projectId') || ''
startAuthenticatedPage({ mount: root => createJiraWorkbench({ root, api, snapshot, projectId }) })
