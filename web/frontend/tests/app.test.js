// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createApp } from '../src/app.js'

describe('SmartTest Web shell', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="app"></div>'
    window.history.replaceState({}, '', '/')
  })

  it('uses an empty Home as the default and exposes only the three approved Database views', async () => {
    await createApp({ root: document.querySelector('#app'), api: {} }).start()

    expect(document.querySelector('main').textContent.trim()).toBe('')
    expect([...document.querySelectorAll('nav a')].map(link => link.textContent.trim())).toEqual([
      'Peak Throughput', 'RVR', 'RVO'
    ])
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
    document.querySelector('select[name="reportNames"] option').selected = true
    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(charts.render).toHaveBeenCalled())

    expect(charts.render.mock.calls[0][1]).toEqual([row])
    expect(charts.render.mock.calls[0][2]).toBe('PEAK_THROUGHPUT')
    expect(document.querySelector('[data-reports]').textContent).toBe('peak.csv')
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
      getFilters: vi.fn().mockResolvedValue({}),
      getPerformance: vi.fn().mockResolvedValue({ data: [{ reportName: 'rvr.csv' }] })
    }
    const charts = { clear: vi.fn(), render: vi.fn() }
    await createApp({ root: document.querySelector('#app'), api, capabilities: { charts, exportExcel, exportPdf } }).start()
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
