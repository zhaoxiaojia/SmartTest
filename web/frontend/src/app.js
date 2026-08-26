import { createAuthShell } from './auth-shell.js'

const DATABASE_ROUTES = [
  { path: '/wifi-database/peak-throughput', dataType: 'PEAK_THROUGHPUT', label: 'Peak Throughput' },
  { path: '/wifi-database/rvr', dataType: 'RVR', label: 'RVR' },
  { path: '/wifi-database/rvo', dataType: 'RVO', label: 'RVO' }
]
const REPORT_ROUTES = [
  { path: '/jira.html', source: 'jira', label: 'Jira' },
  { path: '/confluence.html', source: 'confluence', label: 'Confluence' }
]

const dashboardIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>`
const projectsIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`
const inboxIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><path d="m22 6-10 7L2 6"/></svg>`
const analyticsIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>`
const settingsIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1h.1a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.4 1z"/></svg>`
const databaseIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v6c0 1.7 4 3 9 3s9-1.3 9-3V5"/><path d="M3 11v6c0 1.7 4 3 9 3s9-1.3 9-3v-6"/></svg>`
const jiraIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m12 2 7 7-7 7-7-7 7-7z"/><path d="m12 9 5 5-5 5-5-5"/></svg>`
const confluenceIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 7c3-3 5-3 8-1l6 4-3 4-6-4c-1-.7-2-.5-3 .7L5 13"/><path d="M19 17c-3 3-5 3-8 1l-6-4 3-4 6 4c1 .7 2 .5 3-.7L19 11"/></svg>`
const lightIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`
const darkIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`

function optionValues(payload, ...keys) {
  for (const key of keys) {
    if (Array.isArray(payload?.[key])) return payload[key]
  }
  return []
}

export function fillSelect(select, values) {
  select.replaceChildren()
  for (const raw of values) {
    const value = raw && typeof raw === 'object' ? raw.value : raw
    const label = raw && typeof raw === 'object' ? (raw.label ?? value) : value
    const option = document.createElement('option')
    option.value = `${value ?? ''}`
    option.textContent = `${label ?? ''}`
    select.append(option)
  }
  select._multiSelect?.syncFromSelect()
}

export function enhanceMultiSelect(select, { emptyLabel = 'Select options', compact = false, searchable = true } = {}) {
  select.classList.add('d-none')
  const container = document.createElement('div'); container.className = 'multi-select'
  container.innerHTML = `<button type="button" class="multi-select__control form-select" aria-haspopup="listbox" aria-expanded="false">
      <span class="multi-select__summary">Select options</span><span class="multi-select__tags" hidden></span></button>
    <div class="multi-select__dropdown card shadow-lg" role="listbox" aria-multiselectable="true" aria-hidden="true">
      ${searchable ? '<div class="multi-select__search"><input class="form-control" type="search" placeholder="Search options" aria-label="Search options"></div>' : ''}
      <div class="multi-select__options"></div><div class="multi-select__empty">No options available</div>
      <div class="multi-select__actions"><button type="button" class="button button-secondary" data-clear>Clear</button><button type="button" class="button button-primary" data-select-all>Select all</button></div>
    </div>`
  select.after(container)
  const control = container.querySelector('.multi-select__control')
  const dropdown = container.querySelector('.multi-select__dropdown')
  const options = container.querySelector('.multi-select__options')
  const empty = container.querySelector('.multi-select__empty')
  const search = container.querySelector('input[type="search"]')
  const outside = event => { if (!container.contains(event.target)) close() }
  const keyboard = event => { if (event.key === 'Escape') close() }
  const close = () => {
    container.classList.remove('is-open'); dropdown.setAttribute('aria-hidden', 'true'); control.setAttribute('aria-expanded', 'false')
    document.removeEventListener('mousedown', outside); document.removeEventListener('keydown', keyboard)
    if (search) search.value = ''
  }
  const updateSummary = () => {
    const values = selected(select); const tags = container.querySelector('.multi-select__tags'); const summary = container.querySelector('.multi-select__summary')
    tags.replaceChildren(); tags.hidden = values.length === 0; summary.hidden = values.length > 0
    summary.textContent = emptyLabel
    const shown = compact ? values.slice(0, 1) : values.slice(0, 2)
    shown.forEach(value => { const tag = document.createElement('span'); tag.className = 'multi-select__tag badge'; tag.textContent = [...select.options].find(option => option.value === value)?.textContent || value; tags.append(tag) })
    if (values.length > shown.length) { const more = document.createElement('span'); more.className = 'multi-select__tag badge'; more.textContent = `+${values.length - shown.length}`; tags.append(more) }
    container.querySelector('[data-clear]').disabled = values.length === 0
    container.querySelector('[data-select-all]').disabled = select.options.length === 0 || values.length === select.options.length
  }
  const syncFromSelect = () => {
    options.replaceChildren()
    for (const option of select.options) {
      const label = document.createElement('label'); label.className = 'multi-select__option'
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.className = 'form-check-input'; checkbox.value = option.value; checkbox.checked = option.selected
      const text = document.createElement('span'); text.textContent = option.textContent
      checkbox.addEventListener('change', () => { option.selected = checkbox.checked; updateSummary(); select.dispatchEvent(new Event('change', { bubbles: true })) })
      label.append(checkbox, text); options.append(label)
    }
    empty.hidden = select.options.length > 0; updateSummary()
  }
  select._multiSelect = { syncFromSelect, setDisabled(disabled) {
    control.disabled = disabled; if (search) search.disabled = disabled
    for (const input of options.querySelectorAll('input')) input.disabled = disabled
    if (disabled) for (const button of container.querySelectorAll('[data-clear], [data-select-all]')) button.disabled = true
    else updateSummary()
  } }
  control.addEventListener('click', () => { const open = !container.classList.contains('is-open'); if (open) { container.classList.add('is-open'); dropdown.setAttribute('aria-hidden', 'false'); control.setAttribute('aria-expanded', 'true'); document.addEventListener('mousedown', outside); document.addEventListener('keydown', keyboard); search?.focus() } else close() })
  search?.addEventListener('input', () => { let visible = 0; for (const item of options.children) { item.hidden = !item.textContent.toLowerCase().includes(search.value.trim().toLowerCase()); if (!item.hidden) visible += 1 } empty.hidden = visible > 0; empty.textContent = select.options.length ? 'No matches found' : 'No options available' })
  container.querySelector('[data-select-all]').addEventListener('click', event => { event.stopPropagation(); for (const option of select.options) option.selected = true; syncFromSelect(); select.dispatchEvent(new Event('change', { bubbles: true })); close() })
  container.querySelector('[data-clear]').addEventListener('click', event => { event.stopPropagation(); for (const option of select.options) option.selected = false; syncFromSelect(); select.dispatchEvent(new Event('change', { bubbles: true })) })
  select.addEventListener('change', updateSummary)
  syncFromSelect()
  return syncFromSelect
}

export function selected(select) {
  return [...select.selectedOptions].map(option => option.value)
}

function renderReports(container, rows, selectedReports) {
  const names = [...new Set([
    ...selectedReports,
    ...rows.map(row => row.reportName).filter(Boolean)
  ])].sort()
  container.replaceChildren()
  container.textContent = names.length ? names.join(', ') : 'No matching reports.'
  container.parentElement.querySelector('[data-report-count]').textContent = `${names.length}`
}

function databaseView(route, api, capabilities) {
  const section = document.createElement('section')
  section.innerHTML = `
    <div class="database-header">
      <div><div class="eyebrow">Wi-Fi Data</div><h1></h1></div>
      <span class="status-badge status-neutral" role="status">Connecting to API…</span>
    </div>
    <form class="card filter-panel">
      <div class="filter-grid">
        <label>Product Line<select name="productLines" class="form-select" multiple></select></label>
        <label>Project<select name="projects" class="form-select" multiple></select></label>
        <label>Test Report<select name="testReportCsvNames" class="form-select" multiple></select></label>
        <label>Standard<select name="standards" class="form-select" multiple></select></label>
        <label>Start Date<input name="startDate" class="form-control" type="date"></label>
        <label>End Date<input name="endDate" class="form-control" type="date"></label>
        <div class="filter-actions"><button class="button button-primary" type="submit">Apply Filters</button><button class="button button-secondary" type="button" data-refresh>Refresh</button><button class="button button-secondary" type="button" data-reset>Reset</button></div>
      </div>
    </form>
    <div class="card selected-reports"><strong>Selected reports <span class="count-badge" data-report-count>0</span></strong><span data-reports>Select test reports and apply the filters.</span></div>
    <div class="export-actions">
      <button class="button button-secondary" type="button" data-export-excel disabled>Export Excel</button>
      <button class="button button-secondary" type="button" data-export-pdf disabled>Export PDF</button>
    </div>
    <div class="inline-status" data-export-status aria-live="polite"></div>
    <div data-results>Choose filters and click “Apply Filters” to run the query.</div>`
  section.querySelector('h1').textContent = route.label
  const form = section.querySelector('form')
  const status = section.querySelector('[role="status"]')
  const results = section.querySelector('[data-results]')
  const reports = section.querySelector('[data-reports]')
  const excelButton = section.querySelector('[data-export-excel]')
  const pdfButton = section.querySelector('[data-export-pdf]')
  const exportStatus = section.querySelector('[data-export-status]')
  let latestRows = []
  const stateKey = `wifi-database:${route.dataType}`
  const filters = () => ({
    dataType: route.dataType,
    productLines: selected(form.elements.productLines),
    projects: selected(form.elements.projects),
    testReportCsvNames: selected(form.elements.testReportCsvNames),
    standards: selected(form.elements.standards),
    startDate: form.elements.startDate.value,
    endDate: form.elements.endDate.value,
    limit: 1000
  })

  const controls = [...form.querySelectorAll('select[multiple]')]
  const updateCounts = controls.map(enhanceMultiSelect)
  const saveState = () => sessionStorage.setItem(stateKey, JSON.stringify(filters()))
  const restoreState = () => {
    let state = {}; try { state = JSON.parse(sessionStorage.getItem(stateKey) || '{}') } catch { state = {} }
    for (const select of controls) {
      const wanted = new Set(state[select.name] || [])
      for (const option of select.options) option.selected = wanted.has(option.value)
    }
    form.elements.startDate.value = state.startDate || ''
    form.elements.endDate.value = state.endDate || ''
    updateCounts.forEach(update => update())
  }
  const loadFacets = () => api.getFilters(filters()).then(payload => {
    fillSelect(form.elements.productLines, optionValues(payload, 'productLines'))
    fillSelect(form.elements.projects, optionValues(payload, 'projects'))
    fillSelect(form.elements.testReportCsvNames, optionValues(payload, 'testReports', 'reportNames'))
    fillSelect(form.elements.standards, optionValues(payload, 'standards'))
    restoreState()
    status.className = 'status-badge status-success'
    status.textContent = 'API connected'
  }).catch(() => {
    status.className = 'status-badge status-danger'
    status.textContent = 'API unavailable — filters and results cannot be loaded.'
  })
  const ready = loadFacets()

  for (const control of controls) control.addEventListener('change', () => {
    saveState()
    loadFacets()
  })

  form.addEventListener('submit', async event => {
    event.preventDefault()
    if (!selected(form.elements.testReportCsvNames).length) {
      status.className = 'status-badge status-warning'
      status.textContent = 'Select at least one Test Report.'
      return
    }
    saveState()
    status.className = 'status-badge status-neutral'
    status.textContent = 'Loading…'
    try {
      const payload = await api.getPerformance(filters())
      latestRows = Array.isArray(payload) ? payload : (payload?.data ?? [])
      capabilities.charts.render(results, latestRows, route.dataType)
      renderReports(reports, latestRows, selected(form.elements.testReportCsvNames))
      excelButton.disabled = latestRows.length === 0
      pdfButton.disabled = latestRows.length === 0
      status.className = 'status-badge status-success'
      const truncated = !Array.isArray(payload) && payload?.metadata?.truncated
      status.textContent = truncated ? 'Success — result limit reached; refine filters.' : 'Success'
    } catch {
      status.className = 'status-badge status-danger'
      status.textContent = 'API unavailable — performance data could not be loaded.'
    }
  })
  section.querySelector('[data-refresh]').addEventListener('click', () => loadFacets())
  section.querySelector('[data-reset]').addEventListener('click', () => {
    form.reset()
    for (const select of controls) for (const option of select.options) option.selected = false
    saveState(); updateCounts.forEach(update => update())
    reports.textContent = 'Select test reports and apply the filters.'
    section.querySelector('[data-report-count]').textContent = '0'
    results.textContent = 'Choose filters and click “Apply Filters” to run the query.'
    capabilities.charts?.clear?.()
  })
  const runExport = async (label, operation) => {
    excelButton.disabled = true
    pdfButton.disabled = true
    exportStatus.className = 'inline-status'
    exportStatus.textContent = `Exporting ${label}…`
    try {
      await operation()
      exportStatus.textContent = `${label} export ready.`
    } catch (error) {
      exportStatus.className = 'inline-status inline-status-error'
      exportStatus.textContent = `${label} export failed: ${error?.message || 'Unknown error'}`
    } finally {
      const enabled = latestRows.length > 0
      excelButton.disabled = !enabled
      pdfButton.disabled = !enabled
    }
  }
  excelButton.addEventListener('click', () => runExport('Excel', () => capabilities.exportExcel(latestRows)))
  pdfButton.addEventListener('click', () => runExport('PDF', () => capabilities.exportPdf(results, route.dataType)))
  return { section, ready }
}

export function createApp({ root, api, capabilities = {} }) {
  root.innerHTML = `
    <div class="mobile-menu-overlay"></div>
    <div class="mobile-menu" aria-hidden="true">
      <div class="mobile-menu-header"><a class="logo" href="/"><span class="logo-icon">✓</span><span class="logo-label">SmartTest</span></a><button class="mobile-menu-close" type="button" aria-label="Close navigation">×</button></div>
      <nav class="mobile-menu-nav"></nav>
      <div class="mobile-menu-footer"><div data-user-mobile></div><div class="theme-toggle"><button class="theme-btn" type="button" data-theme="light" title="Light theme">${lightIcon}</button><button class="theme-btn" type="button" data-theme="dark" title="Dark theme">${darkIcon}</button></div></div>
    </div>
    <div class="app-container">
      <nav class="top-nav">
        <div class="nav-container">
          <div class="nav-left"><a class="logo" href="/"><span class="logo-icon">✓</span><span class="logo-label">SmartTest</span></a><div class="nav-menu"></div></div>
          <div class="nav-right"><div class="theme-toggle"><button class="theme-btn" type="button" data-theme="light" title="Light theme">${lightIcon}</button><button class="theme-btn" type="button" data-theme="dark" title="Dark theme">${darkIcon}</button></div><div class="user-entry" data-user-entry></div><button class="mobile-menu-btn" type="button" aria-label="Open navigation"><span></span><span></span><span></span></button></div>
        </div>
      </nav>
      <nav class="database-nav" aria-label="Wi-Fi Data"></nav>
      <main class="main-content"></main>
    </div>
    `
  const nav = root.querySelector('.nav-menu')
  const mobileNav = root.querySelector('.mobile-menu-nav')
  const databaseNav = root.querySelector('.database-nav')
  const main = root.querySelector('main')
  const authShell = createAuthShell({ root, desktopHost: root.querySelector('[data-user-entry]'), mobileHost: root.querySelector('[data-user-mobile]'), api: capabilities.authApi })

  function renderNavigation(route) {
    nav.replaceChildren()
    mobileNav.replaceChildren()
    const routes = [
      { path: '/', label: 'Dashboard', icon: dashboardIcon, active: !route },
      { path: '/projects.html', label: 'Projects', icon: projectsIcon, active: false },
      { path: '/inbox.html', label: 'Inbox', icon: inboxIcon, active: false },
      { path: '/analytics.html', label: 'Analytics', icon: analyticsIcon, active: false },
      { path: '/settings.html', label: 'Settings', icon: settingsIcon, active: false },
      { path: '/jira.html', label: 'Jira', icon: jiraIcon, active: route?.source === 'jira' },
      { path: '/confluence.html', label: 'Confluence', icon: confluenceIcon, active: route?.source === 'confluence' },
      { path: DATABASE_ROUTES[0].path, label: 'Wi-Fi Data', icon: databaseIcon, active: Boolean(route?.dataType) }
    ]
    for (const item of routes) {
      const link = document.createElement('a')
      link.className = `nav-link${item.active ? ' active' : ''}`
      link.href = item.path
      link.innerHTML = `${item.icon}<span>${item.label}</span>`
      nav.append(link)
      mobileNav.append(link.cloneNode(true))
    }
    databaseNav.replaceChildren()
    databaseNav.hidden = !route?.dataType
    if (route?.dataType) {
      for (const item of DATABASE_ROUTES) {
        const link = document.createElement('a')
        link.className = item.path === route.path ? 'active' : ''
        link.href = item.path
        link.textContent = item.label
        databaseNav.append(link)
      }
    }
  }

  function setTheme(theme) {
    const dark = theme === 'dark'
    document.documentElement.classList.toggle('dark-theme', dark)
    localStorage.setItem('smarttest-web-theme', dark ? 'dark' : 'light')
    root.querySelectorAll('[data-theme]').forEach(button => button.classList.toggle('active', button.dataset.theme === theme))
  }

  setTheme(localStorage.getItem('smarttest-web-theme') === 'dark' ? 'dark' : 'light')
  root.querySelectorAll('[data-theme]').forEach(button => button.addEventListener('click', () => setTheme(button.dataset.theme)))
  const menu = root.querySelector('.mobile-menu')
  const overlay = root.querySelector('.mobile-menu-overlay')
  const closeMenu = () => { menu.classList.remove('active'); overlay.classList.remove('active'); menu.setAttribute('aria-hidden', 'true') }
  root.querySelector('.mobile-menu-btn').addEventListener('click', () => { menu.classList.add('active'); overlay.classList.add('active'); menu.setAttribute('aria-hidden', 'false') })
  root.querySelector('.mobile-menu-close').addEventListener('click', closeMenu)
  overlay.addEventListener('click', closeMenu)

  async function render() {
    const route = DATABASE_ROUTES.find(candidate => candidate.path === window.location.pathname) ?? REPORT_ROUTES.find(candidate => candidate.path === window.location.pathname)
    renderNavigation(route)
    main.replaceChildren()
    if (!route) return
    if (route.source) {
      const workspace = capabilities.reportWorkspace?.(route.source)
      if (workspace) { main.append(workspace.section); await workspace.start() }
      return
    }
    capabilities.charts?.clear?.()
    const { section, ready } = databaseView(route, api, capabilities)
    main.append(section)
    await ready
  }

  async function start() {
    await authShell.start()
    return render()
  }

  root.addEventListener('click', event => {
    const link = event.target.closest('a')
    if (!link || link.origin !== window.location.origin) return
    if (![...DATABASE_ROUTES, ...REPORT_ROUTES].some(route => route.path === link.pathname)) return
    event.preventDefault()
    window.history.pushState({}, '', link.pathname)
    closeMenu()
    render()
  })
  window.addEventListener('popstate', render)
  return { start }
}
