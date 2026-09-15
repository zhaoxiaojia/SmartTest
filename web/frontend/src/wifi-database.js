import { enhanceMultiSelect, fillSelect, selected } from './multi-select.js'

export const DATABASE_ROUTES = [
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
    <form class="card filter-panel" data-preference-region>
      <div class="filter-grid">
        <label>Product Line<select name="productLines" class="form-select" multiple></select></label>
        <label>Project<select name="projects" class="form-select" multiple></select></label>
        <label>Test Report<select name="testReportCsvNames" class="form-select" multiple></select></label>
        <label>Standard<select name="standards" class="form-select" multiple></select></label>
        <label>Start Date<input name="startDate" class="form-control" type="date"></label>
        <label>End Date<input name="endDate" class="form-control" type="date"></label>
        <div class="filter-actions"><button class="button button-primary" type="submit">Apply Filters</button><button class="button button-secondary" type="button" data-refresh>Refresh</button><button class="button button-secondary" type="button" data-reset data-preference-reset>Reset</button></div>
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
  const loadFacets = () => api.getFilters(filters()).then(payload => {
    fillSelect(form.elements.productLines, optionValues(payload, 'productLines'))
    fillSelect(form.elements.projects, optionValues(payload, 'projects'))
    fillSelect(form.elements.testReportCsvNames, optionValues(payload, 'testReports', 'reportNames'))
    fillSelect(form.elements.standards, optionValues(payload, 'standards'))
    updateCounts.forEach(update => update())
    status.className = 'status-badge status-success'
    status.textContent = 'API connected'
  }).catch(() => {
    status.className = 'status-badge status-danger'
    status.textContent = 'API unavailable — filters and results cannot be loaded.'
  })
  const ready = loadFacets()

  for (const control of controls) control.addEventListener('change', () => {
    loadFacets()
  })

  form.addEventListener('submit', async event => {
    event.preventDefault()
    if (!selected(form.elements.testReportCsvNames).length) {
      status.className = 'status-badge status-warning'
      status.textContent = 'Select at least one Test Report.'
      return
    }
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
    updateCounts.forEach(update => update())
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

export async function mountWifiDatabase({ root, api, capabilities = {}, path = window.location.pathname }) {
  const route = DATABASE_ROUTES.find(candidate => candidate.path === path) ?? DATABASE_ROUTES[0]
  capabilities.charts?.clear?.()
  const { section, ready } = databaseView(route, api, capabilities)
  root.replaceChildren(section)
  await ready
}
