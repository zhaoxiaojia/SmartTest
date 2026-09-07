import { createAuditEmailApi } from './api.js'
import { startAuthenticatedPage } from './authenticated-page.js'
import { createAuditEmailPage } from './audit-email.js'

startAuthenticatedPage({ mount: root => createAuditEmailPage({ root, api: createAuditEmailApi() }) })
