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
  for (const raw of values) {
    const value = raw && typeof raw === 'object' ? raw.value : raw
    const label = raw && typeof raw === 'object' ? (raw.label ?? value) : value
    const option = document.createElement('option')
    option.value = `${value ?? ''}`
    option.textContent = `${label ?? ''}`
    select.append(option)
  }
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
}

function databaseView(route, api, capabilities) {
  const section = document.createElement('section')
  section.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-4">
      <div><div class="text-body-secondary">Wi-Fi Database</div><h1 class="h2 mb-0"></h1></div>
      <span class="badge text-bg-secondary" role="status">Connecting to API…</span>
    </div>
    <form class="card card-body mb-4">
      <div class="row g-3">
        <label class="col-md-3">Product Line<select name="productLines" class="form-select" multiple></select></label>
        <label class="col-md-3">Project<select name="projects" class="form-select" multiple></select></label>
        <label class="col-md-3">Test Report<select name="reportNames" class="form-select" multiple></select></label>
        <label class="col-md-3">Standard<select name="standards" class="form-select" multiple></select></label>
        <label class="col-md-3">Start Date<input name="startDate" class="form-control" type="date"></label>
        <label class="col-md-3">End Date<input name="endDate" class="form-control" type="date"></label>
        <div class="col-md-3 d-flex align-items-end gap-2"><button class="btn btn-primary" type="submit">Apply Filters</button></div>
      </div>
    </form>
    <div class="card card-body mb-3"><strong>Selected reports</strong><span data-reports>Select test reports and apply the filters.</span></div>
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
  const filters = () => ({
    dataType: route.dataType,
    productLines: selected(form.elements.productLines),
    projects: selected(form.elements.projects),
    reportNames: selected(form.elements.reportNames),
    standards: selected(form.elements.standards),
    startDate: form.elements.startDate.value,
    endDate: form.elements.endDate.value,
    limit: 1000
  })

  const ready = api.getFilters(filters()).then(payload => {
    fillSelect(form.elements.productLines, optionValues(payload, 'productLines'))
    fillSelect(form.elements.projects, optionValues(payload, 'projects'))
    fillSelect(form.elements.reportNames, optionValues(payload, 'reportNames', 'testReports'))
    fillSelect(form.elements.standards, optionValues(payload, 'standards'))
    status.className = 'badge text-bg-success'
    status.textContent = 'API connected'
  }).catch(() => {
    status.className = 'badge text-bg-danger'
    status.textContent = 'API unavailable — filters and results cannot be loaded.'
  })

  form.addEventListener('submit', async event => {
    event.preventDefault()
    status.className = 'badge text-bg-secondary'
    status.textContent = 'Loading…'
    try {
      const payload = await api.getPerformance(filters())
      latestRows = Array.isArray(payload) ? payload : (payload?.data ?? [])
      capabilities.charts.render(results, latestRows, route.dataType)
      renderReports(reports, latestRows, selected(form.elements.reportNames))
      excelButton.disabled = latestRows.length === 0
      pdfButton.disabled = latestRows.length === 0
      status.className = 'badge text-bg-success'
      status.textContent = 'API connected'
    } catch {
      status.className = 'badge text-bg-danger'
      status.textContent = 'API unavailable — performance data could not be loaded.'
    }
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
  pdfButton.addEventListener('click', () => runExport('PDF', () => capabilities.exportPdf(results)))
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
  for (const route of DATABASE_ROUTES) {
    const link = document.createElement('a')
    link.className = 'nav-link'
    link.href = route.path
    link.textContent = route.label
    nav.append(link)
  }

  async function render() {
    const route = DATABASE_ROUTES.find(candidate => candidate.path === window.location.pathname)
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
