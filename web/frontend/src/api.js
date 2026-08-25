export class ApiUnavailableError extends Error {
  constructor(message, { status, cause } = {}) {
    super(message, { cause })
    this.name = 'ApiUnavailableError'
    this.status = status
  }
}

const TYPE_MAP = {
  PEAK_THROUGHPUT: 'performance',
  RVR: 'RVR',
  RVO: 'RVO'
}

function appendValues(params, key, values) {
  for (const value of values ?? []) {
    if (`${value}`.trim()) params.append(key, value)
  }
}

function buildQuery(filters = {}) {
  const params = new URLSearchParams()
  appendValues(params, 'product_line', filters.productLines)
  appendValues(params, 'project', filters.projects)
  appendValues(params, 'report_name', filters.reportNames)
  appendValues(params, 'test_report_csv_name', filters.testReportCsvNames)
  appendValues(params, 'standard', filters.standards)
  params.set('data_type', TYPE_MAP[filters.dataType] ?? filters.dataType ?? 'performance')
  if (filters.startDate) params.set('start_date', filters.startDate)
  if (filters.endDate) params.set('end_date', filters.endDate)
  if (filters.limit) params.set('limit', filters.limit)
  return params
}

export function createWifiDatabaseApi({ fetchImpl = globalThis.fetch, baseUrl = '/api' } = {}) {
  async function getJson(path, filters) {
    const query = buildQuery(filters)
    const url = `${baseUrl}${path}?${query}`
    let response
    try {
      response = await fetchImpl(url)
    } catch (cause) {
      throw new ApiUnavailableError('Wi-Fi Database API unavailable.', { cause })
    }
    if (!response.ok) {
      const detail = (await response.text()).trim()
      throw new ApiUnavailableError(detail || `Wi-Fi Database API unavailable (${response.status}).`, {
        status: response.status
      })
    }
    return response.json()
  }

  return {
    getFilters: filters => getJson('/filters', filters),
    getPerformance: filters => getJson('/performance', filters)
  }
}
