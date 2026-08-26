import { createAuthApi } from './api.js'
import { createLoginPage } from './login-page.js'

createLoginPage({ root: document, api: createAuthApi() }).start()
