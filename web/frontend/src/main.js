import { createAuthApi, createPreferenceApi } from './api.js'
import { createAuthShell } from './auth-shell.js'
import { createPreferenceStore } from './preference-store.js'
import { createAppShell } from './app-shell.js'
import { clearDisposableDisplayState } from './disposable-display.js'
import { initializeTheme } from './theme.js'

initializeTheme()

export let preferencesReady = Promise.resolve()

async function startStaticShell() {
  const host = document.querySelector('[data-app-shell]')
  if (!host) throw new Error('app_shell_host_missing')
  const pageKey = window.location.pathname.startsWith('/wifi-database/') ? 'wifi' : host.dataset.pageKey
  const { desktopHost, mobileHost } = createAppShell({ pageKey, root: host })
  let session
    const applyTheme = theme => {
      globalThis.SmartTestTheme.apply(theme)
    }
    document.body.addEventListener('preference:restored', event => { if (event.target.dataset.preferenceKey === 'theme') applyTheme(event.detail.value) })
    document.body.addEventListener('click', event => {
      const input = event.target.closest('.theme-toggle input')
      if (!input) return
      input.dataset.preferenceValue = input.checked ? 'dark' : 'light'
      applyTheme(input.dataset.preferenceValue)
    })
    let preferences
  session = await createAuthShell({ root: document.body, desktopHost, mobileHost, api: createAuthApi(),
      onChanging() {
        preferences?.destroy()
        clearDisposableDisplayState()
        globalThis.SmartTestTheme.clear()
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
