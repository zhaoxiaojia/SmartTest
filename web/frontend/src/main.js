import { createAuthApi } from './api.js'
import { createAuthShell } from './auth-shell.js'

if (window.location.pathname.startsWith('/wifi-database/')) {
  import('./wifi-main.js').then(({ startWifiData }) => startWifiData())
} else {
  const desktop = document.querySelector('.nav-right')
  const mobile = document.querySelector('.mobile-menu-footer')
  if (desktop && mobile) {
    const desktopHost = document.createElement('div'); desktopHost.className = 'user-entry'
    const mobileHost = document.createElement('div'); mobileHost.setAttribute('data-user-mobile', '')
    desktop.insertBefore(desktopHost, desktop.querySelector('.mobile-menu-btn'))
    mobile.insertBefore(mobileHost, mobile.firstChild)
    createAuthShell({ root: document.body, desktopHost, mobileHost, api: createAuthApi() }).start()
  }
}
