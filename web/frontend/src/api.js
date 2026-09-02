export class ApiUnavailableError extends Error {
  constructor(message, { status, cause } = {}) {
    super(message, { cause })
    this.name = 'ApiUnavailableError'
    this.status = status
  }
}

function identityChangeMarker() {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID()
  return `${Date.now()}-${Math.random()}`
}

export function createAuthApi({ fetchImpl = globalThis.fetch, baseUrl = '/api' } = {}) {
  async function change(path, options) {
    const result = await request(path, options)
    if (globalThis.window) {
      window.localStorage.setItem('smarttest:identity-change', identityChangeMarker())
      window.dispatchEvent(new Event('auth:changed'))
    }
    return result
  }
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
    login: (username, password) => change('/auth/login', {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ username, password })
    }),
    logout: () => change('/auth/logout', { method: 'POST' })
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

export function createManualAuditApi({ fetchImpl = globalThis.fetch, baseUrl = '/api' } = {}) {
  async function request(path, { method = 'GET', body } = {}) {
    const options = { method, credentials: 'same-origin' }
    if (body !== undefined) {
      options.headers = { 'content-type': 'application/json' }
      options.body = JSON.stringify(body)
    }
    let response
    try { response = await fetchImpl(`${baseUrl}${path}`, options) } catch (cause) {
      throw new ApiUnavailableError('Manual audit API unavailable.', { cause })
    }
    if (!response.ok) throw new ApiUnavailableError(`Manual audit API unavailable (${response.status}).`, { status: response.status })
    return response.json()
  }
  const encode = encodeURIComponent
  const post = (path, body) => request(path, { method: 'POST', body })
  return {
    createJiraAudit: body => post('/audits/jira', body),
    getJiraAudit: id => request(`/audits/jira/${encode(id)}`),
    cancelJiraAudit: id => post(`/audits/jira/${encode(id)}/cancel`),
    exportJiraAudit: id => post(`/audits/jira/${encode(id)}/export`),
    createConfluenceAudit: body => post('/audits/confluence', body),
    getConfluenceAudit: id => request(`/audits/confluence/${encode(id)}`),
    cancelConfluenceAudit: id => post(`/audits/confluence/${encode(id)}/cancel`),
    exportConfluenceAudit: id => post(`/audits/confluence/${encode(id)}/export`),
    downloadUrl: id => `${baseUrl}/downloads/${encode(id)}`,
  }
}

export function createProjectFactsApi({ fetchImpl = globalThis.fetch, baseUrl = '/api' } = {}) {
  return {
    async getProjectFacts(filters = {}, { details = false, catalog = false } = {}) {
      const query = new URLSearchParams()
      for (const [key, values] of Object.entries(filters.fields ?? {})) {
        for (const value of Array.isArray(values) ? values : [values]) if (`${value}`.trim()) query.append(`field.${key}`, value)
      }
      if (filters.search) query.set('search', filters.search)
      if (details) query.set('details', '1')
      if (catalog) query.set('catalog', '1')
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
