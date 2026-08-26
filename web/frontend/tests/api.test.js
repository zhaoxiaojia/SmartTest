import { describe, expect, it, vi } from 'vitest'

import { createAuthApi, createProjectFactsApi, createReportWorkspaceApi, createWifiDatabaseApi } from '../src/api.js'

describe('Web session API contract', () => {
  it('uses cookie-backed session endpoints without persisting credentials', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ authenticated: true }) })
    const api = createAuthApi({ fetchImpl })
    await api.login('coco', 'secret')
    await api.session()
    await api.logout()
    expect(fetchImpl.mock.calls.map(call => call[0])).toEqual(['/api/auth/login', '/api/auth/session', '/api/auth/logout'])
    expect(fetchImpl.mock.calls[0][1]).toMatchObject({ method: 'POST', credentials: 'same-origin' })
    expect(fetchImpl.mock.calls[1][1]).toMatchObject({ credentials: 'same-origin' })
    expect(fetchImpl.mock.calls[0][1].body).toBe(JSON.stringify({ username: 'coco', password: 'secret' }))
  })
})

describe('Wi-Fi Database API contract', () => {
  it('keeps the legacy repeated-query filter contract and Peak type mapping', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: [] }) })
    const api = createWifiDatabaseApi({ fetchImpl, baseUrl: '/api' })

    await api.getPerformance({
      dataType: 'PEAK_THROUGHPUT',
      productLines: ['Consumer', 'Enterprise'],
      projects: ['Apollo'],
      testReportCsvNames: ['report.csv'],
      standards: ['802.11be'],
      startDate: '2026-08-01',
      endDate: '2026-08-24',
      limit: 1000
    })

    const url = new URL(fetchImpl.mock.calls[0][0], 'https://smarttest.local')
    expect(url.pathname).toBe('/api/performance')
    expect(url.searchParams.getAll('product_line')).toEqual(['Consumer', 'Enterprise'])
    expect(url.searchParams.getAll('project')).toEqual(['Apollo'])
    expect(url.searchParams.getAll('test_report_csv_name')).toEqual(['report.csv'])
    expect(url.searchParams.getAll('standard')).toEqual(['802.11be'])
    expect(url.searchParams.get('data_type')).toBe('performance')
    expect(url.searchParams.get('start_date')).toBe('2026-08-01')
    expect(url.searchParams.get('end_date')).toBe('2026-08-24')
    expect(url.searchParams.get('limit')).toBe('1000')
  })

  it('reports HTTP and network failures as an unavailable API', async () => {
    const httpApi = createWifiDatabaseApi({
      fetchImpl: vi.fn().mockResolvedValue({ ok: false, status: 503, text: async () => '' })
    })
    await expect(httpApi.getFilters({ dataType: 'RVR' })).rejects.toMatchObject({
      name: 'ApiUnavailableError',
      status: 503
    })

    const networkApi = createWifiDatabaseApi({ fetchImpl: vi.fn().mockRejectedValue(new TypeError('offline')) })
    await expect(networkApi.getPerformance({ dataType: 'RVO' })).rejects.toMatchObject({
      name: 'ApiUnavailableError'
    })
  })
})

describe('report workspace API contract', () => {
  it('uses read-only list, detail and download endpoints', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ reports: [] }) })
    const api = createReportWorkspaceApi({ fetchImpl })

    await api.listReports('jira', { productLine: 'DOPL', year: 2026, search: 'audit' })
    await api.getReport('jira', 'report-1')

    const url = new URL(fetchImpl.mock.calls[0][0], 'https://smarttest.local')
    expect(url.pathname).toBe('/api/report-workspaces/jira')
    expect(url.searchParams.get('product_line')).toBe('DOPL')
    expect(url.searchParams.get('year')).toBe('2026')
    expect(fetchImpl.mock.calls[1][0]).toBe('/api/report-workspaces/jira/report-1')
    expect(api.downloadUrl('jira', 'report-1')).toBe('/api/report-workspaces/jira/report-1/download')
  })

  it('sends Jira JQL when locating Client-generated audit reports', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ reports: [] }) })
    const api = createReportWorkspaceApi({ fetchImpl })
    await api.listReports('jira', { jql: 'project = TV AND issuetype = Bug' })
    const url = new URL(fetchImpl.mock.calls[0][0], 'https://smarttest.local')
    expect(url.searchParams.get('jql')).toBe('project = TV AND issuetype = Bug')
  })
})

describe('Confluence project facts API contract', () => {
  it('sends dynamic field filters and project/person search to the read-only endpoint', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ projects: [] }) })
    await createProjectFactsApi({ fetchImpl }).getProjectFacts({
      fields: { 'unexpected owner': ['Alice', 'Bob'], 'support mode': ['B'] }, search: 'Coco'
    })
    const url = new URL(fetchImpl.mock.calls[0][0], 'https://smarttest.local')
    expect(url.pathname).toBe('/api/confluence/project-facts')
    expect(url.searchParams.getAll('field.unexpected owner')).toEqual(['Alice', 'Bob'])
    expect(url.searchParams.get('field.support mode')).toBe('B')
    expect(url.searchParams.get('search')).toBe('Coco')
  })
})
