import { createAuthApi } from './api.js'
import { applyLoginBackground } from './login-background.js'
import { createLoginPage } from './login-page.js'

applyLoginBackground()
createLoginPage({ root: document, api: createAuthApi() }).start()
