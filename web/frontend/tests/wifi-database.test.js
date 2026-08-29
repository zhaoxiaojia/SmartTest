// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mountWifiDatabase } from '../src/wifi-database.js'
import { createPreferenceStore } from '../src/preference-store.js'

const createWifiView = ({ root, api, capabilities = {} }) => ({ start: () => mountWifiDatabase({ root, api, capabilities }) })

describe('Wi-Fi Data view', () => {
  beforeEach(() => { document.body.innerHTML = '<div id="app"></div>'; window.history.replaceState({}, '', '/wifi-database/rvr'); localStorage.clear() })
  it('requires a report, supports select-all/clear, and cascades filter facets', async () => {
    window.history.replaceState({}, '', '/wifi-database/rvr')
    const api = {
      getFilters: vi.fn().mockResolvedValue({ productLines: ['Consumer'], projects: ['Apollo'], testReports: ['rvr.csv'], standards: ['BE'] }),
      getPerformance: vi.fn()
    }
    await createWifiView({ root: document.querySelector('#app'), api, capabilities: { charts: { clear: vi.fn(), render: vi.fn() } } }).start()
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
    const app = createWifiView({ root: document.querySelector('#app'), api, capabilities: { charts: { clear: vi.fn(), render: vi.fn() } } })
    await app.start()
    await createPreferenceStore({ root: document, api: preferenceApi }).start()
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

    await createWifiView({ root: document.querySelector('#app'), api }).start()

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
    await createWifiView({
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
    await createWifiView({ root: document.querySelector('#app'), api, capabilities: { charts, exportExcel, exportPdf } }).start()
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
