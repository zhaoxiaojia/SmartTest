import { describe, expect, it, vi } from 'vitest'

import { createWifiDatabaseApi } from '../src/api.js'

describe('Wi-Fi Database API contract', () => {
  it('keeps the legacy repeated-query filter contract and Peak type mapping', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: [] }) })
    const api = createWifiDatabaseApi({ fetchImpl, baseUrl: '/api' })

    await api.getPerformance({
      dataType: 'PEAK_THROUGHPUT',
      productLines: ['Consumer', 'Enterprise'],
      projects: ['Apollo'],
      reportNames: ['report.csv'],
      standards: ['802.11be'],
      startDate: '2026-08-01',
      endDate: '2026-08-24',
      limit: 1000
    })

    const url = new URL(fetchImpl.mock.calls[0][0], 'https://smarttest.local')
    expect(url.pathname).toBe('/api/performance')
    expect(url.searchParams.getAll('product_line')).toEqual(['Consumer', 'Enterprise'])
    expect(url.searchParams.getAll('project')).toEqual(['Apollo'])
    expect(url.searchParams.getAll('report_name')).toEqual(['report.csv'])
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
