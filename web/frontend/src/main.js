import { createAuthApi, createPreferenceApi } from './api.js'
import { createAuthShell } from './auth-shell.js'
import { createPreferenceStore } from './preference-store.js'

async function startStaticShell() {
  const desktop = document.querySelector('.nav-right')
  const mobile = document.querySelector('.mobile-menu-footer')
  if (desktop && mobile) {
    const desktopHost = document.createElement('div'); desktopHost.className = 'user-entry'
    const mobileHost = document.createElement('div'); mobileHost.setAttribute('data-user-mobile', '')
    desktop.insertBefore(desktopHost, desktop.querySelector('.mobile-menu-btn'))
    mobile.insertBefore(mobileHost, mobile.firstChild)
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
    const session = await createAuthShell({ root: document.body, desktopHost, mobileHost, api: createAuthApi() }).start()
    if (session.authenticated) await createPreferenceStore({ root: document, api: createPreferenceApi() }).start()
  }
  if (window.location.pathname.startsWith('/wifi-database/')) {
    for (const link of document.querySelectorAll('.nav-menu a, .mobile-menu-nav a')) {
      link.classList.toggle('active', link.getAttribute('href')?.startsWith('/wifi-database/'))
    }
    const databaseNav = document.querySelector('.database-nav')
    databaseNav.hidden = false
    for (const link of databaseNav.querySelectorAll('a')) link.classList.toggle('active', link.pathname === window.location.pathname)
    const { startWifiData } = await import('./wifi-main.js')
    await startWifiData()
  }
}

export const shellReady = startStaticShell()
