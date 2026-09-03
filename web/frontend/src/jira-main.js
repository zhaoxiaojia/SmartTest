import { createManualAuditApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { createJiraManualAudit } from './manual-audits.js'

const api = createManualAuditApi()
startAuthenticatedPage({ mount: root => createJiraManualAudit({ root, api }) })
