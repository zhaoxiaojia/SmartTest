import { createAuthApi, createPreferenceApi } from './api.js'
import { createAuthShell } from './auth-shell.js'
import { createPreferenceStore } from './preference-store.js'
import { createAppShell } from './app-shell.js'

export let preferencesReady = Promise.resolve()

const DISPOSABLE_DISPLAY_PREFIX = 'smarttest:projects-display:'

function clearDisposableDisplayState() {
  for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
    const key = sessionStorage.key(index)
    if (key?.startsWith(DISPOSABLE_DISPLAY_PREFIX)) sessionStorage.removeItem(key)
  }
}

async function startStaticShell() {
  const host = document.querySelector('[data-app-shell]')
  if (!host) throw new Error('app_shell_host_missing')
  const pageKey = window.location.pathname.startsWith('/wifi-database/') ? 'wifi' : host.dataset.pageKey
  const { desktopHost, mobileHost } = createAppShell({ pageKey, root: host })
  let session
    const applyTheme = theme => {
      const dark = theme === 'dark'; document.documentElement.classList.toggle('dark-theme', dark); document.body.classList.toggle('dark-theme', dark)
    }
    for (const toggle of document.querySelectorAll('.theme-toggle')) {
      toggle.dataset.preferenceRegion = ''; toggle.dataset.preferenceScope = 'global'
      for (const button of toggle.querySelectorAll('.theme-btn-light, [data-theme="light"]')) { button.dataset.preferenceKey = 'theme'; button.dataset.preferenceValue = 'light' }
      for (const button of toggle.querySelectorAll('.theme-btn-dark, [data-theme="dark"]')) { button.dataset.preferenceKey = 'theme'; button.dataset.preferenceValue = 'dark' }
    }
    document.body.addEventListener('preference:restored', event => { if (event.target.dataset.preferenceKey === 'theme') applyTheme(event.detail.value) })
    document.body.addEventListener('click', event => { if (event.target.closest('[data-preference-key="theme"]')) applyTheme(event.target.closest('[data-preference-key="theme"]').dataset.preferenceValue) })
    let preferences
  session = await createAuthShell({ root: document.body, desktopHost, mobileHost, api: createAuthApi(),
      onChanging() {
        preferences?.destroy()
        clearDisposableDisplayState()
        window.dispatchEvent(new Event('session:changing'))
      },
      async onSession(session) {
        if (session.authenticated) {
          preferences = createPreferenceStore({ root: document, api: createPreferenceApi() })
          preferencesReady = preferences.start()
        } else preferencesReady = Promise.resolve()
        window.dispatchEvent(new CustomEvent('session:ready', { detail: session }))
        await preferencesReady
      }
  }).start()
  if (window.location.pathname.startsWith('/wifi-database/')) {
    const { startWifiData } = await import('./wifi-main.js')
    await startWifiData()
  }
  return session
}

export const shellReady = startStaticShell()
