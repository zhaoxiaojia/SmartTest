// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createApp } from '../src/app.js'
import { createAuthShell } from '../src/auth-shell.js'

describe('SmartTest Web shell', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="app"></div>'
    window.history.replaceState({}, '', '/')
    sessionStorage.clear()
    localStorage.clear()
    document.documentElement.classList.remove('dark-theme')
  })

  it('renders the complete SmartTest primary navigation', async () => {
    const authApi = { session: vi.fn().mockResolvedValue({ authenticated: false }) }
    await createApp({ root: document.querySelector('#app'), api: {}, capabilities: { authApi } }).start()

    expect(document.querySelector('.logo-label').textContent).toBe('SmartTest')
    expect([...document.querySelectorAll('.nav-menu a')].map(link => [link.textContent.trim(), link.pathname])).toEqual([
      ['Dashboard', '/'],
      ['Projects', '/projects.html'],
      ['Inbox', '/inbox.html'],
      ['Analytics', '/analytics.html'],
      ['Settings', '/settings.html'],
      ['Jira', '/jira.html'],
      ['Confluence', '/confluence.html'],
      ['Wi-Fi Data', '/wifi-database/peak-throughput']
    ])
    expect(document.querySelector('.nav-menu a.active').textContent.trim()).toBe('Dashboard')
    expect(document.querySelector('[data-login]')).not.toBeNull()
  })

  it('uses the login page and renders an existing avatar identity with logout menu', async () => {
    const authApi = {
      session: vi.fn().mockResolvedValue({ authenticated: true, username: 'coco', displayName: 'Coco Chen', avatarUrl: '' }),
      logout: vi.fn().mockResolvedValue({ authenticated: false })
    }
    await createApp({ root: document.querySelector('#app'), api: {}, capabilities: { authApi } }).start()
    expect(document.querySelector('[data-user-name]').textContent).toBe('Coco Chen')
    expect(document.querySelector('[data-user-avatar]').textContent).toBe('C')
    document.querySelector('[data-user-trigger]').click()
    document.querySelector('[data-logout]').click()
    await vi.waitFor(() => expect(document.querySelector('[data-login]')).not.toBeNull())
    expect(document.querySelector('[data-login]').getAttribute('href')).toBe('/login.html?next=%2F')
    expect(authApi.logout).toHaveBeenCalledTimes(1)
  })

  it('renders LDAP identity and avatar values as inert DOM data', async () => {
    const authApi = {
      session: vi.fn().mockResolvedValue({
        authenticated: true,
        username: 'coco',
        displayName: '<img src=x onerror="globalThis.injected=true">',
        avatarUrl: 'x" onerror="globalThis.avatarInjected=true'
      })
    }
    await createApp({ root: document.querySelector('#app'), api: {}, capabilities: { authApi } }).start()
    const entry = document.querySelector('[data-user-entry]')
    expect(entry.querySelectorAll('img')).toHaveLength(1)
    expect(entry.querySelector('[data-user-name]').textContent).toBe('<img src=x onerror="globalThis.injected=true">')
    expect(entry.querySelector('[data-user-avatar] img').getAttribute('src')).toBe('x" onerror="globalThis.avatarInjected=true')
    expect(entry.querySelector('[onerror]')).toBeNull()
  })

  it('adds the authenticated account name to the existing time-based greeting', async () => {
    document.body.innerHTML = '<h1 id="greeting">Good evening</h1><div id="desktop"></div><div id="mobile"></div>'
    const api = {
      session: vi.fn().mockResolvedValue({ authenticated: true, username: 'chao.li', displayName: 'Chao Li' }),
      logout: vi.fn().mockResolvedValue({ authenticated: false })
    }
    await createAuthShell({
      root: document,
      desktopHost: document.querySelector('#desktop'),
      mobileHost: document.querySelector('#mobile'),
      api
    }).start()
    expect(document.querySelector('#greeting').textContent).toBe('Good evening, chao.li')
    document.querySelector('[data-user-trigger]').click()
    document.querySelector('[data-logout]').click()
    await vi.waitFor(() => expect(document.querySelector('#greeting').textContent).toBe('Good evening'))
  })

  it.each([['/jira.html', 'Jira', 'jira'], ['/confluence.html', 'Confluence', 'confluence']])('activates the report workspace route %s', async (path, label, source) => {
    window.history.replaceState({}, '', path)
    const section = document.createElement('section')
    const start = vi.fn().mockResolvedValue()
    const reportWorkspace = vi.fn().mockReturnValue({ section, start })
    await createApp({ root: document.querySelector('#app'), api: {}, capabilities: { reportWorkspace } }).start()
    expect(document.querySelector('.nav-menu a.active').textContent.trim()).toBe(label)
    expect(reportWorkspace).toHaveBeenCalledWith(source)
    expect(document.querySelector('main').contains(section)).toBe(true)
    expect(start).toHaveBeenCalled()
  })

  it('uses the Wi-Fi Data navigation with the existing three database routes', async () => {
    window.history.replaceState({}, '', '/wifi-database/rvr')
    const api = { getFilters: vi.fn().mockResolvedValue({}), getPerformance: vi.fn() }

    await createApp({ root: document.querySelector('#app'), api }).start()

    expect(document.querySelector('.nav-menu a.active').textContent.trim()).toBe('Wi-Fi Data')
    expect([...document.querySelectorAll('.database-nav a')].map(link => [link.textContent.trim(), link.pathname])).toEqual([
      ['Peak Throughput', '/wifi-database/peak-throughput'],
      ['RVR', '/wifi-database/rvr'],
      ['RVO', '/wifi-database/rvo']
    ])
    expect(document.querySelector('.database-nav a.active').textContent.trim()).toBe('RVR')
  })

  it('leaves report links to a full page load when the Wi-Fi bundle cannot render them', async () => {
    window.history.replaceState({}, '', '/wifi-database/rvr')
    const api = { getFilters: vi.fn().mockResolvedValue({}), getPerformance: vi.fn() }
    const pushState = vi.spyOn(window.history, 'pushState')
    await createApp({ root: document.querySelector('#app'), api }).start()

    const event = new MouseEvent('click', { bubbles: true, cancelable: true })
    window.addEventListener('click', click => click.preventDefault(), { once: true })
    document.querySelector('.nav-menu a[href="/confluence.html"]').dispatchEvent(event)

    expect(pushState).not.toHaveBeenCalled()
  })

  it('persists the selected display theme', async () => {
    const preferenceApi = { get: vi.fn().mockResolvedValue({ items: {} }), put: vi.fn().mockResolvedValue({}), reset: vi.fn() }
    const authApi = { session: vi.fn().mockResolvedValue({ authenticated: true, username: 'coco' }) }
    await createApp({ root: document.querySelector('#app'), api: {}, capabilities: { authApi, preferenceApi } }).start()

    document.querySelector('[data-theme="dark"]').click()
    expect(document.documentElement.classList).toContain('dark-theme')
    await vi.waitFor(() => expect(preferenceApi.put).toHaveBeenCalledWith('global', { theme: 'dark' }))

    document.querySelector('[data-theme="light"]').click()
    expect(document.documentElement.classList).not.toContain('dark-theme')
    await vi.waitFor(() => expect(preferenceApi.put).toHaveBeenLastCalledWith('global', { theme: 'light' }))
  })

  it('requires a report, supports select-all/clear, and cascades filter facets', async () => {
    window.history.replaceState({}, '', '/wifi-database/rvr')
    const api = {
      getFilters: vi.fn().mockResolvedValue({ productLines: ['Consumer'], projects: ['Apollo'], testReports: ['rvr.csv'], standards: ['BE'] }),
      getPerformance: vi.fn()
    }
    await createApp({ root: document.querySelector('#app'), api, capabilities: { charts: { clear: vi.fn(), render: vi.fn() } } }).start()
    const nativeSelect = document.querySelector('select[name="testReportCsvNames"]')
    expect(nativeSelect.classList).toContain('d-none')
    const multi = nativeSelect.nextElementSibling
    expect(multi.querySelector('.multi-select__dropdown').getAttribute('aria-hidden')).toBe('true')
    multi.querySelector('.multi-select__control').click()
    expect(multi.querySelector('.multi-select__dropdown').getAttribute('aria-hidden')).toBe('false')
    const search = multi.querySelector('input[type="search"]')
    search.value = 'missing'; search.dispatchEvent(new Event('input', { bubbles: true }))
    expect(multi.querySelector('.multi-select__empty').textContent).toBe('No matches found')
    search.value = ''; search.dispatchEvent(new Event('input', { bubbles: true }))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(multi.querySelector('.multi-select__dropdown').getAttribute('aria-hidden')).toBe('true')
    multi.querySelector('.multi-select__control').click()
    multi.querySelector('[data-select-all]').click()
    expect(multi.querySelector('.multi-select__tag').textContent).toBe('rvr.csv')
    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(api.getPerformance).toHaveBeenCalled())
    multi.querySelector('[data-clear]').click()
    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    expect(document.querySelector('[role="status"]').textContent).toContain('Select at least one Test Report')
    expect(api.getPerformance).toHaveBeenCalledTimes(1)
    document.querySelector('select[name="productLines"] option').selected = true
    document.querySelector('select[name="productLines"]').dispatchEvent(new Event('change', { bubbles: true }))
    await vi.waitFor(() => expect(api.getFilters.mock.calls.at(-1)[0].productLines).toEqual(['Consumer']))
  })

  it('keeps independent filter state for each datatype and reset clears current state', async () => {
    window.history.replaceState({}, '', '/wifi-database/rvr')
    const api = { getFilters: vi.fn().mockResolvedValue({ testReports: ['rvr.csv'] }), getPerformance: vi.fn() }
    const preferenceApi = { get: vi.fn().mockResolvedValue({ items: {} }), put: vi.fn().mockResolvedValue({}), reset: vi.fn().mockResolvedValue({}) }
    const authApi = { session: vi.fn().mockResolvedValue({ authenticated: true, username: 'coco' }) }
    const app = createApp({ root: document.querySelector('#app'), api, capabilities: { authApi, preferenceApi, charts: { clear: vi.fn(), render: vi.fn() } } })
    await app.start()
    document.querySelector('select[name="testReportCsvNames"] option').selected = true
    document.querySelector('select[name="testReportCsvNames"]').dispatchEvent(new Event('change', { bubbles: true }))
    await vi.waitFor(() => expect(preferenceApi.put).toHaveBeenCalledWith('wifi-database/rvr', { testReportCsvNames: ['rvr.csv'] }))
    document.querySelector('[data-reset]').click()
    expect(document.querySelector('select[name="testReportCsvNames"]').selectedOptions).toHaveLength(0)
    await vi.waitFor(() => expect(preferenceApi.reset).toHaveBeenCalledWith('wifi-database/rvr'))
  })

  it('shows an explicit unavailable state without crashing', async () => {
    window.history.replaceState({}, '', '/wifi-database/rvr')
    const api = {
      getFilters: vi.fn().mockRejectedValue(new Error('offline')),
      getPerformance: vi.fn()
    }

    await createApp({ root: document.querySelector('#app'), api }).start()

    expect(document.querySelector('[role="status"]').textContent).toContain('API unavailable')
    expect(document.querySelector('h1').textContent).toBe('RVR')
  })

  it('renders selected reports and delegates returned rows to the datatype chart renderer', async () => {
    window.history.replaceState({}, '', '/wifi-database/peak-throughput')
    const row = { reportName: 'peak.csv', pathLossDb: 10, throughputAvgMbps: 900 }
    const api = {
      getFilters: vi.fn().mockResolvedValue({ reportNames: ['peak.csv'] }),
      getPerformance: vi.fn().mockResolvedValue({ data: [row] })
    }
    const charts = { clear: vi.fn(), render: vi.fn() }
    await createApp({
      root: document.querySelector('#app'), api,
      capabilities: { charts, exportExcel: vi.fn(), exportPdf: vi.fn() }
    }).start()
    document.querySelector('select[name="testReportCsvNames"] option').selected = true
    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(charts.render).toHaveBeenCalled())

    expect(charts.render.mock.calls[0][1]).toEqual([row])
    expect(charts.render.mock.calls[0][2]).toBe('PEAK_THROUGHPUT')
    expect(document.querySelector('[data-reports]').textContent).toBe('peak.csv')
    expect(document.querySelector('[data-report-count]').textContent).toBe('1')
    expect(document.querySelector('[data-export-excel]').disabled).toBe(false)
  })

  it.each([
    ['excel', '[data-export-excel]', 'Excel'],
    ['pdf', '[data-export-pdf]', 'PDF']
  ])('shows in-page status and restores buttons when %s export rejects', async (kind, selector, label) => {
    window.history.replaceState({}, '', '/wifi-database/rvr')
    let rejectExport
    const pending = new Promise((resolve, reject) => { rejectExport = reject })
    const exportExcel = vi.fn(() => kind === 'excel' ? pending : Promise.resolve())
    const exportPdf = vi.fn(() => kind === 'pdf' ? pending : Promise.resolve())
    const api = {
      getFilters: vi.fn().mockResolvedValue({ testReports: ['rvr.csv'] }),
      getPerformance: vi.fn().mockResolvedValue({ data: [{ reportName: 'rvr.csv' }] })
    }
    const charts = { clear: vi.fn(), render: vi.fn() }
    await createApp({ root: document.querySelector('#app'), api, capabilities: { charts, exportExcel, exportPdf } }).start()
    document.querySelector('select[name="testReportCsvNames"] option').selected = true
    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(document.querySelector(selector).disabled).toBe(false))

    document.querySelector(selector).click()
    expect(document.querySelector('[data-export-excel]').disabled).toBe(true)
    expect(document.querySelector('[data-export-pdf]').disabled).toBe(true)
    expect(document.querySelector('[data-export-status]').textContent).toContain(`Exporting ${label}`)
    rejectExport(new Error('disk unavailable'))

    await vi.waitFor(() => expect(document.querySelector('[data-export-status]').textContent).toContain(`${label} export failed`))
    expect(document.querySelector('[data-export-status]').textContent).toContain('disk unavailable')
    expect(document.querySelector('[data-export-excel]').disabled).toBe(false)
    expect(document.querySelector('[data-export-pdf]').disabled).toBe(false)
  })
})
