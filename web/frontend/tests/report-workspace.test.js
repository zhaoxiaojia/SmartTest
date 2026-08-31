// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createReportWorkspace } from '../src/report-workspace.js'

describe('Jira report workspace', () => {
  beforeEach(() => { document.body.innerHTML = '<div id="app"></div>'; localStorage.clear() })

  it('renders the Jira master-detail workspace with download', async () => {
    const source = 'jira'
    const report = { id: 'r1', title: `${source} report`, generatedAt: '2026-08-26T14:30:00', status: 'attention', sourceUrl: 'https://example.test/report' }
    const api = {
      listReports: vi.fn().mockResolvedValue({ state: 'ready', reports: [report], facets: { productLines: ['DOPL'], years: [2026], reportTypes: ['Audit'] } }),
      getReport: vi.fn().mockResolvedValue({ ...report, summary: { total: 3, passed: 2, attention: 1, failed: 0 }, sections: [{ title: 'Findings', headers: ['Issue', 'Status'], rows: [['ST-1', 'Open']] }] }),
      downloadUrl: vi.fn(() => '/download/r1')
    }

    await createReportWorkspace({ root: document.querySelector('#app'), source, api }).start()

    expect(document.querySelector('.report-workspace')).toBeTruthy()
    expect(document.querySelector('.report-directory-item.active').textContent).toContain(`${source} report`)
    expect(document.querySelector('.report-status-tag').textContent).toBe('Attention')
    expect(document.querySelector('.report-preview-table').textContent).toContain('ST-1')
    expect(document.querySelector('[data-download]').getAttribute('href')).toBe('/download/r1')
    expect(document.querySelector('[data-source-link]').href).toBe('https://example.test/report')
  })

  it.each([
    ['loading', 'Loading reports'], ['empty', 'No reports available'],
    ['unauthorized', 'You do not have permission'], ['config_missing', 'Report source is not configured'],
    ['external_failure', 'Report source is unavailable'], ['partial_success', 'Some reports could not be loaded']
  ])('renders the explicit %s state', async (state, message) => {
    let resolve
    const pending = new Promise(value => { resolve = value })
    const api = { listReports: vi.fn(() => pending) }
    const started = createReportWorkspace({ root: document.querySelector('#app'), source: 'jira', api }).start()
    expect(document.querySelector('[role="status"]').textContent).toContain('Loading reports')
    resolve({ state, reports: [], facets: {} })
    await started
    expect(document.querySelector('[role="status"]').textContent).toContain(message)
  })

  it('clears the selected report preview while the report directory reloads', async () => {
    let resolveRefresh
    const report = { id: 'r1', title: 'Old report', generatedAt: '2026-08-26', status: 'completed' }
    const api = {
      listReports: vi.fn()
        .mockResolvedValueOnce({ state: 'ready', reports: [report], facets: {} })
        .mockImplementationOnce(() => new Promise(resolve => { resolveRefresh = resolve })),
      getReport: vi.fn().mockResolvedValue({ ...report, summary: {}, sections: [] }), downloadUrl: vi.fn(() => '/download')
    }
    await createReportWorkspace({ root: document.querySelector('#app'), source: 'jira', api }).start()
    document.querySelector('[data-refresh]').click()
    expect(document.querySelector('[data-preview-title]').textContent).toBe('Loading reports…')
    expect(document.querySelector('[data-preview-meta]').textContent).toBe('')
    expect(document.querySelector('.report-preview-body').textContent).not.toContain('Old report')
    resolveRefresh({ state: 'empty', reports: [], facets: {} })
  })

  it.each([[403, 'You do not have permission'], [502, 'Report source is unavailable']])('maps detail HTTP %s to the correct state', async (httpStatus, message) => {
    const report = { id: 'r1', title: 'Report', status: 'completed' }
    const api = {
      listReports: vi.fn().mockResolvedValue({ state: 'ready', reports: [report], facets: {} }),
      getReport: vi.fn().mockRejectedValue({ status: httpStatus }), downloadUrl: vi.fn(() => '/download')
    }
    await createReportWorkspace({ root: document.querySelector('#app'), source: 'jira', api }).start()
    expect(document.querySelector('[role="status"]').textContent).toContain(message)
  })

  it('uses the Client JQL-driven contract for Jira generated reports', async () => {
    const api = { listReports: vi.fn().mockResolvedValue({ state: 'empty', reports: [], facets: {} }) }
    await createReportWorkspace({ root: document.querySelector('#app'), source: 'jira', api }).start()
    const form = document.querySelector('form')
    expect(form.elements.jql.tagName).toBe('TEXTAREA')
    expect(form.elements.productLine).toBeUndefined()
    expect(form.elements.year).toBeUndefined()
    expect(form.elements.reportType).toBeUndefined()
    expect(form.querySelector('[type="submit"]').textContent).toContain('Find Generated Reports')

    form.elements.jql.value = 'project = TV AND issuetype = Bug'
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(api.listReports).toHaveBeenCalledTimes(2))
    expect(api.listReports.mock.calls[1]).toEqual(['jira', { jql: 'project = TV AND issuetype = Bug' }])
  })
})
