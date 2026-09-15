import { createJiraAnalyticsApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { createJiraFilterBuilder } from './jira-filter-builder.js'

const api = createJiraAnalyticsApi()
startAuthenticatedPage({ mount: (root, session) => createJiraFilterBuilder({ root, api, account: session.username }) })
