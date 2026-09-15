import { startAuthenticatedPage } from './authenticated-page.js'
import { createTools } from './tools.js'

startAuthenticatedPage({ mount: root => createTools({ root }) })
