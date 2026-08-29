export class ApiUnavailableError extends Error {
  constructor(message, { status, cause } = {}) {
    super(message, { cause })
    this.name = 'ApiUnavailableError'
    this.status = status
  }
}

export function createAuthApi({ fetchImpl = globalThis.fetch, baseUrl = '/api' } = {}) {
  async function request(path, options = {}) {
    let response
    try { response = await fetchImpl(`${baseUrl}${path}`, { credentials: 'same-origin', ...options }) } catch (cause) {
      throw new ApiUnavailableError('Authentication service unavailable.', { cause })
    }
    if (!response.ok) throw new ApiUnavailableError(`Authentication failed (${response.status}).`, { status: response.status })
    return response.json()
  }
  return {
    session: () => request('/auth/session'),
    login: (username, password) => request('/auth/login', {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ username, password })
    }),
    logout: () => request('/auth/logout', { method: 'POST' })
  }
}

export function createPreferenceApi({ fetchImpl = globalThis.fetch, baseUrl = '/api' } = {}) {
  async function request(scope, method, body) {
    let response
    const path = `${baseUrl}/preferences/${encodeURIComponent(scope.replace(/^\/+/, ''))}`
    const options = { method, credentials: 'same-origin' }
    if (body) { options.headers = { 'content-type': 'application/json' }; options.body = JSON.stringify(body) }
    try { response = await fetchImpl(path, options) } catch (cause) {
      throw new ApiUnavailableError('Preference service unavailable.', { cause })
    }
    if (!response.ok) throw new ApiUnavailableError(`Preference service unavailable (${response.status}).`, { status: response.status })
    return response.json()
  }
  return {
    get: scope => request(scope, 'GET'),
    put: (scope, items) => request(scope, 'PUT', { items, schemaVersion: 1 }),
    reset: scope => request(scope, 'DELETE')
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

export function createReportWorkspaceApi({ fetchImpl = globalThis.fetch, baseUrl = '/api' } = {}) {
  async function getJson(path, params) {
    const query = new URLSearchParams()
    if (params?.productLine) query.set('product_line', params.productLine)
    if (params?.year) query.set('year', params.year)
    if (params?.reportType) query.set('report_type', params.reportType)
    if (params?.search) query.set('search', params.search)
    if (params?.jql) query.set('jql', params.jql)
    const suffix = query.size ? `?${query}` : ''
    let response
    try { response = await fetchImpl(`${baseUrl}${path}${suffix}`) } catch (cause) {
      throw new ApiUnavailableError('Report workspace API unavailable.', { cause })
    }
    if (!response.ok) {
      throw new ApiUnavailableError(`Report workspace API unavailable (${response.status}).`, { status: response.status })
    }
    return response.json()
  }
  const encode = value => encodeURIComponent(value)
  return {
    listReports: (source, filters) => getJson(`/report-workspaces/${encode(source)}`, filters),
    getReport: (source, id) => getJson(`/report-workspaces/${encode(source)}/${encode(id)}`),
    downloadUrl: (source, id) => `${baseUrl}/report-workspaces/${encode(source)}/${encode(id)}/download`
  }
}

export function createProjectFactsApi({ fetchImpl = globalThis.fetch, baseUrl = '/api' } = {}) {
  return {
    async getProjectFacts(filters = {}, { details = false } = {}) {
      const query = new URLSearchParams()
      for (const [key, values] of Object.entries(filters.fields ?? {})) {
        for (const value of Array.isArray(values) ? values : [values]) if (`${value}`.trim()) query.append(`field.${key}`, value)
      }
      if (filters.search) query.set('search', filters.search)
      if (details) query.set('details', '1')
      let response
      try { response = await fetchImpl(`${baseUrl}/confluence/project-facts${query.size ? `?${query}` : ''}`) } catch (cause) {
        throw new ApiUnavailableError('Project facts API unavailable.', { cause })
      }
      if (!response.ok) throw new ApiUnavailableError(`Project facts API unavailable (${response.status}).`, { status: response.status })
      return response.json()
    },
    async cancelProjectSync() {
      const response = await fetchImpl(`${baseUrl}/confluence/project-facts/cancel`, {
        method: 'POST', credentials: 'same-origin'
      })
      if (!response.ok) throw new ApiUnavailableError(`Project sync cancellation failed (${response.status}).`, { status: response.status })
      return response.json()
    },
  }
}
