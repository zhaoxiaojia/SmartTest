const DATABASE_ROUTES = [
  { path: '/wifi-database/peak-throughput', dataType: 'PEAK_THROUGHPUT', label: 'Peak Throughput' },
  { path: '/wifi-database/rvr', dataType: 'RVR', label: 'RVR' },
  { path: '/wifi-database/rvo', dataType: 'RVO', label: 'RVO' }
]

function optionValues(payload, ...keys) {
  for (const key of keys) {
    if (Array.isArray(payload?.[key])) return payload[key]
  }
  return []
}

function fillSelect(select, values) {
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

function enhanceMultiSelect(select) {
  select.classList.add('d-none')
  const container = document.createElement('div'); container.className = 'multi-select'
  container.innerHTML = `<button type="button" class="multi-select__control form-select" aria-haspopup="listbox" aria-expanded="false">
      <span class="multi-select__summary">Select options</span><span class="multi-select__tags" hidden></span></button>
    <div class="multi-select__dropdown card shadow-lg" role="listbox" aria-multiselectable="true" aria-hidden="true">
      <div class="multi-select__search"><input class="form-control form-control-sm" type="search" placeholder="Search options" aria-label="Search options"></div>
      <div class="multi-select__options"></div><div class="multi-select__empty">No options available</div>
      <div class="multi-select__actions"><button type="button" class="btn btn-light btn-sm" data-clear>Clear</button><button type="button" class="btn btn-primary btn-sm" data-select-all>Select All</button></div>
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
    search.value = ''
  }
  const updateSummary = () => {
    const values = selected(select); const tags = container.querySelector('.multi-select__tags'); const summary = container.querySelector('.multi-select__summary')
    tags.replaceChildren(); tags.hidden = values.length === 0; summary.hidden = values.length > 0
    values.slice(0, 2).forEach(value => { const tag = document.createElement('span'); tag.className = 'multi-select__tag badge'; tag.textContent = [...select.options].find(option => option.value === value)?.textContent || value; tags.append(tag) })
    if (values.length > 2) { const more = document.createElement('span'); more.className = 'multi-select__tag badge'; more.textContent = `+${values.length - 2} more`; tags.append(more) }
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
  select._multiSelect = { syncFromSelect }
  control.addEventListener('click', () => { const open = !container.classList.contains('is-open'); if (open) { container.classList.add('is-open'); dropdown.setAttribute('aria-hidden', 'false'); control.setAttribute('aria-expanded', 'true'); document.addEventListener('mousedown', outside); document.addEventListener('keydown', keyboard); search.focus() } else close() })
  search.addEventListener('input', () => { let visible = 0; for (const item of options.children) { item.hidden = !item.textContent.toLowerCase().includes(search.value.trim().toLowerCase()); if (!item.hidden) visible += 1 } empty.hidden = visible > 0; empty.textContent = select.options.length ? 'No matches found' : 'No options available' })
  container.querySelector('[data-select-all]').addEventListener('click', event => { event.stopPropagation(); for (const option of select.options) option.selected = true; syncFromSelect(); select.dispatchEvent(new Event('change', { bubbles: true })); close() })
  container.querySelector('[data-clear]').addEventListener('click', event => { event.stopPropagation(); for (const option of select.options) option.selected = false; syncFromSelect(); select.dispatchEvent(new Event('change', { bubbles: true })) })
  select.addEventListener('change', updateSummary)
  syncFromSelect()
  return syncFromSelect
}

function selected(select) {
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
    <div class="database-header d-flex justify-content-between align-items-center mb-4">
      <div><div class="text-body-secondary">Wi-Fi Database</div><h1 class="h2 mb-0"></h1></div>
      <span class="badge text-bg-secondary" role="status">Connecting to API…</span>
    </div>
    <form class="card card-body mb-4">
      <div class="row g-3">
        <label class="col-md-3">Product Line<select name="productLines" class="form-select" multiple></select></label>
        <label class="col-md-3">Project<select name="projects" class="form-select" multiple></select></label>
        <label class="col-md-3">Test Report<select name="testReportCsvNames" class="form-select" multiple></select></label>
        <label class="col-md-3">Standard<select name="standards" class="form-select" multiple></select></label>
        <label class="col-md-3">Start Date<input name="startDate" class="form-control" type="date"></label>
        <label class="col-md-3">End Date<input name="endDate" class="form-control" type="date"></label>
        <div class="filter-actions col-md-6 d-flex align-items-end gap-2"><button class="btn btn-primary" type="submit">Apply Filters</button><button class="btn btn-outline-secondary" type="button" data-refresh>Refresh</button><button class="btn btn-outline-secondary" type="button" data-reset>Reset</button></div>
      </div>
    </form>
    <div class="card card-body mb-3"><strong>Selected reports <span class="badge text-bg-primary" data-report-count>0</span></strong><span data-reports>Select test reports and apply the filters.</span></div>
    <div class="d-flex gap-2 mb-3">
      <button class="btn btn-outline-success" type="button" data-export-excel disabled>Export Excel</button>
      <button class="btn btn-outline-danger" type="button" data-export-pdf disabled>Export PDF</button>
    </div>
    <div class="small text-body-secondary mb-3" data-export-status aria-live="polite"></div>
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
    status.className = 'badge text-bg-success'
    status.textContent = 'API connected'
  }).catch(() => {
    status.className = 'badge text-bg-danger'
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
      status.className = 'badge text-bg-warning'
      status.textContent = 'Select at least one Test Report.'
      return
    }
    saveState()
    status.className = 'badge text-bg-secondary'
    status.textContent = 'Loading…'
    try {
      const payload = await api.getPerformance(filters())
      latestRows = Array.isArray(payload) ? payload : (payload?.data ?? [])
      capabilities.charts.render(results, latestRows, route.dataType)
      renderReports(reports, latestRows, selected(form.elements.testReportCsvNames))
      excelButton.disabled = latestRows.length === 0
      pdfButton.disabled = latestRows.length === 0
      status.className = 'badge text-bg-success'
      const truncated = !Array.isArray(payload) && payload?.metadata?.truncated
      status.textContent = truncated ? 'Success — result limit reached; refine filters.' : 'Success'
    } catch {
      status.className = 'badge text-bg-danger'
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
    exportStatus.className = 'small text-body-secondary mb-3'
    exportStatus.textContent = `Exporting ${label}…`
    try {
      await operation()
      exportStatus.textContent = `${label} export ready.`
    } catch (error) {
      exportStatus.className = 'small text-danger mb-3'
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
    <div class="app-shell">
      <aside class="sidebar sidebar-dark border-end">
        <a class="brand" href="/">SmartTest</a>
        <div class="sidebar-label">Wi-Fi Database</div>
        <nav class="sidebar-nav"></nav>
      </aside>
      <main class="content"></main>
    </div>`
  const nav = root.querySelector('nav')
  const main = root.querySelector('main')

  function renderNavigation(route) {
    nav.replaceChildren()
    const routes = route ? DATABASE_ROUTES : [{ path: DATABASE_ROUTES[0].path, label: 'Wi-Fi Database' }]
    for (const item of routes) {
      const link = document.createElement('a')
      link.className = 'nav-link'
      link.href = item.path
      link.textContent = item.label
      nav.append(link)
    }
  }

  async function render() {
    const route = DATABASE_ROUTES.find(candidate => candidate.path === window.location.pathname)
    renderNavigation(route)
    main.replaceChildren()
    if (!route) return
    capabilities.charts?.clear?.()
    const { section, ready } = databaseView(route, api, capabilities)
    main.append(section)
    await ready
  }

  root.addEventListener('click', event => {
    const link = event.target.closest('a')
    if (!link || link.origin !== window.location.origin) return
    event.preventDefault()
    window.history.pushState({}, '', link.pathname)
    render()
  })
  window.addEventListener('popstate', render)
  return { start: render }
}
