import { startAuthenticatedPage } from './authenticated-page.js'

const pageKey = document.querySelector('[data-app-shell]').dataset.pageKey
const loaders = {
  settings: () => import('./pages/settings.js'),
  inbox: () => import('./pages/inbox.js'),
  analytics: () => import('./pages/analytics.js'),
}
if (!loaders[pageKey]) throw new Error(`static_page_unknown:${pageKey}`)
const page = await loaders[pageKey]()
startAuthenticatedPage({ mount: root => {
  const instance = page.mount(root)
  globalThis.setGreeting?.()
  return instance
} })
