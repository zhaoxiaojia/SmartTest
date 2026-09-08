import { createJiraFilterApi, createManualAuditApi, createProjectFactsApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { preferencesReady } from './main.js'
import { createTools } from './tools.js'

const api = { ...createJiraFilterApi(), ...createManualAuditApi(), ...createProjectFactsApi() }
startAuthenticatedPage({ mount: (root, session) => createTools({
  root, api, account: session.username,
  waitForPreferences: async () => { await preferencesReady; await new Promise(resolve => setTimeout(resolve, 0)) },
}) })
