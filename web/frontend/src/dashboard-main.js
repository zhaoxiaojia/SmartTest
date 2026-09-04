import { createReleaseApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { createReleaseDashboard } from './release-dashboard.js'

startAuthenticatedPage({ mount: root => createReleaseDashboard({ root, api: createReleaseApi() }) })
