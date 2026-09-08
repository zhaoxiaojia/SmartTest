import { WEB_BRAND_NAME } from './brand.js'

const icons = {
  dashboard: '<rect x="3" y="3" width="7" height="7" rx="1"></rect><rect x="14" y="3" width="7" height="7" rx="1"></rect><rect x="3" y="14" width="7" height="7" rx="1"></rect><rect x="14" y="14" width="7" height="7" rx="1"></rect>',
  projects: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>',
  jira: '<path d="m12 2 7 7-7 7-7-7 7-7z"></path><path d="m12 9 5 5-5 5-5-5"></path>',
  tools: '<path d="M14.7 6.3a4 4 0 0 0-5 5L3 18v3h3l6.7-6.7a4 4 0 0 0 5-5l-2.4 2.4-3-3z"></path>',
  wifi: '<ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M3 5v6c0 1.7 4 3 9 3s9-1.3 9-3V5"></path><path d="M3 11v6c0 1.7 4 3 9 3s9-1.3 9-3v-6"></path>',
  settings: '<circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33A1.65 1.65 0 0 0 14 20.91V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15 1.65 1.65 0 0 0 3.17 14H3a2 2 0 1 1 0-4h.17A1.65 1.65 0 0 0 4.68 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68h.1A1.65 1.65 0 0 0 10 3.17V3a2 2 0 1 1 4 0v.17a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06-.06A1.65 1.65 0 0 0 19.32 9v.1A1.65 1.65 0 0 0 20.83 10H21a2 2 0 1 1 0 4h-.17A1.65 1.65 0 0 0 19.4 15z"></path>',
}

export const navigation = [
  { pageKey: 'dashboard', title: 'Dashboard', url: '/', icon: icons.dashboard },
  { pageKey: 'projects', title: 'Projects', url: '/projects.html', icon: icons.projects },
  { pageKey: 'jira', title: 'Jira', url: '/jira.html', icon: icons.jira },
  { pageKey: 'tools', title: 'Tools', url: '/tools.html', icon: icons.tools },
  { pageKey: 'wifi', title: 'Wi-Fi Data', url: '/wifi-database/peak-throughput', icon: icons.wifi },
  { pageKey: 'settings', title: 'Settings', url: '/settings.html', icon: icons.settings },
]

const pageOwners = { dashboard: 'dashboard', projects: 'projects', jira: 'jira', tools: 'tools', settings: 'settings', wifi: 'wifi', 'audit-email': 'tools', inbox: null, analytics: null }
const ownerKey = pageKey => pageOwners[pageKey]
const icon = value => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">${value}</svg>`
const themeToggle = () => '<div class="theme-toggle"><button class="theme-btn theme-btn-light active" data-theme="light" title="Light theme"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72 1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"></path></svg></button><button class="theme-btn theme-btn-dark" data-theme="dark" title="Dark theme"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg></button></div>'

function links(active, mobile = false) {
  return navigation.map(item => `<${mobile ? '' : 'div class="nav-item"><'}a href="${item.url}" data-page-key="${item.pageKey}" class="${mobile ? '' : 'nav-link '}${item.pageKey === active ? 'active' : ''}">${icon(item.icon)}<span>${item.title}</span></a>${mobile ? '' : '</div>'}`).join('')
}

export function createAppShell({ pageKey, root = document.querySelector('[data-app-shell]') }) {
  if (!root) throw new Error('app_shell_host_missing')
  if (!(pageKey in pageOwners)) throw new Error(`app_shell_page_unknown:${pageKey}`)
  const active = ownerKey(pageKey)
  const wifi = active === 'wifi'
  root.innerHTML = `<div class="mobile-menu-overlay"></div><div class="mobile-menu"><div class="mobile-menu-header"><a href="/" class="logo"><span class="logo-label">${WEB_BRAND_NAME}</span></a><button class="mobile-menu-close" type="button" onclick="closeMobileMenu()">×</button></div><nav class="mobile-menu-nav">${links(active, true)}</nav><div class="mobile-menu-footer"><div data-user-mobile></div>${themeToggle()}</div></div><div class="app-container"><nav class="top-nav"><div class="nav-container"><div class="nav-left"><a href="/" class="logo"><span class="logo-label">${WEB_BRAND_NAME}</span></a><div class="nav-menu">${links(active)}</div></div><div class="nav-right">${themeToggle()}<div class="user-entry"></div><button class="mobile-menu-btn" type="button" onclick="toggleMobileMenu()">☰</button></div></div></nav><nav class="database-nav" aria-label="Wi-Fi Data" ${wifi ? '' : 'hidden'}><a href="/wifi-database/peak-throughput">Peak Throughput</a><a href="/wifi-database/rvr">RVR</a><a href="/wifi-database/rvo">RVO</a></nav><main class="main-content"></main><footer class="footer"><p>© 2026 ${WEB_BRAND_NAME}</p></footer></div>`
  if (wifi) {
    for (const link of root.querySelectorAll('.database-nav a')) link.classList.toggle('active', link.pathname === window.location.pathname)
  }
  return {
    contentRoot: root.querySelector('main.main-content'),
    desktopHost: root.querySelector('.user-entry'),
    mobileHost: root.querySelector('[data-user-mobile]'),
  }
}
