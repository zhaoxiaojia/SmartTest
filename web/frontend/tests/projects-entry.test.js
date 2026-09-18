// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'

const charts = vi.hoisted(() => [])
vi.mock('chart.js', () => {
  const Chart = vi.fn(function (_canvas, config) {
    this.data = config.data; this.options = config.options
    this.destroy = vi.fn(); this.stop = vi.fn(); this.reset = vi.fn(); this.update = vi.fn()
    charts.push(this)
  })
  Chart.register = vi.fn()
  return { Chart, registerables: [] }
})

it('mounts the persisted Projects snapshot, preserves filters, and has no migrated review controls', async () => {
  window.history.replaceState({}, '', '/projects.html')
  document.body.innerHTML = '<div data-app-shell data-page-key="projects"></div>'
  const ready = { state: 'ready', accessibleProjectCount: 1,
    productSpaces: [
      { value: 'DOPL', label: 'China Operator Business' },
      { value: 'SDPL', label: 'Smart Device Business' },
      { value: 'TV', label: 'TV Business' },
      { value: 'OOPL', label: 'Global Operator & STB Business' },
    ],
    facets: [{ key: '__product_space__', label: 'Product Space', options: ['TV'] }],
    projects: [{ project_id: 'P1', name: 'Project One', space_key: 'TV' }],
    ownerHierarchy: [{ role: 'FAE QA', people: [{ identity: 'alice', name: 'Alice',
      projects: [{ project_id: 'P1', space_key: 'DOPL' }] }] }], sync: { state: 'idle' } }
  const respond = data => ({ ok: true, json: async () => data })
  let finishApply
  const fetchImpl = vi.fn(async (url, options = {}) => {
    const path = new URL(url, window.location.origin)
    if (path.pathname === '/api/auth/session') return respond({ authenticated: true, username: 'alice' })
    if (path.pathname.startsWith('/api/preferences/')) return respond({ items: {} })
    if (path.pathname === '/api/confluence/project-facts') {
      return respond(ready)
    }
    if (path.pathname === '/api/confluence/filter-snapshot' && options.method === 'PUT') {
      return new Promise(resolve => { finishApply = data => resolve(respond(data)) })
    }
    if (path.pathname === '/api/confluence/filter-snapshot' && options.method === 'DELETE') return respond(ready)
    throw new Error(`Unexpected request: ${path.pathname}`)
  })
  vi.stubGlobal('fetch', fetchImpl)
  await import('../src/projects-main.js')
  try {
    await vi.waitFor(() => expect(document.querySelector('main form')?.elements['field.__product_space__']).toBeDefined())
    expect(document.querySelector('main form').querySelector('[type="submit"]').disabled).toBe(false)
    const form = document.querySelector('main form')
    const workload = document.querySelector('[data-page-widget="role-workload"]')
    expect(workload).not.toBeNull()
    expect(workload.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy()
    expect(charts.at(-1).data.datasets[0].data).toEqual([1])
    const select = form.elements['field.__product_space__']
    select.value = 'TV'
    form.elements.search.value = 'Project One'
    expect(charts.at(-1).data.datasets[0].data).toEqual([1])
    expect(form.querySelector('[data-audit]')).toBeNull()
    const entryRequests = fetchImpl.mock.calls.map(([url]) => new URL(url, window.location.origin))
      .filter(url => url.pathname === '/api/confluence/project-facts')
    expect(entryRequests).toHaveLength(1)
    const projectsRequest = entryRequests.find(url => url.searchParams.get('snapshot') === '1')
    expect(projectsRequest.searchParams.has('catalog')).toBe(false)
    expect(form.elements['field.__product_space__']).toBe(select)
    expect(select.value).toBe('TV')

    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(finishApply).toBeTypeOf('function'))
    expect(document.querySelector('main form')).toBe(form)
    finishApply({ ...ready, ownerHierarchy: [{ role: 'FAE QA', people: [{ identity: 'alice', name: 'Alice',
      projects: [{ space_key: 'DOPL' }, { space_key: 'DOPL' }] }] }] })
    await vi.waitFor(() => expect(charts.at(-1).data.datasets[0].data).toEqual([2]))
    window.dispatchEvent(new CustomEvent('session:ready', { detail: { authenticated: true, username: 'alice' } }))
    expect(document.querySelector('main form')).toBe(form)
    expect(form.elements['field.__product_space__']).toBe(select)
    expect(form.elements.search.value).toBe('Project One')
    form.querySelector('[data-reset]').click()
    await vi.waitFor(() => expect(charts.at(-1).data.datasets[0].data).toEqual([1]))

    window.dispatchEvent(new Event('session:changing'))
    expect(document.querySelector('main form')).toBeNull()
    window.dispatchEvent(new CustomEvent('session:ready', { detail: { authenticated: true, username: 'alice' } }))
    await vi.waitFor(() => expect(document.querySelector('main form')).not.toBeNull())
    expect(document.querySelector('main form')).not.toBe(form)
    expect(document.querySelector('[data-audit-download]')).toBeNull()
    const nextForm = document.querySelector('main form')
    window.dispatchEvent(new CustomEvent('session:ready', { detail: { authenticated: true, username: 'bob' } }))
    expect(document.querySelector('main form')).not.toBe(nextForm)
    expect(document.querySelector('[name="search"]').value).toBe('')
    expect(document.querySelector('[data-audit-download]')).toBeNull()
  } finally {
    window.dispatchEvent(new Event('session:changing'))
    vi.unstubAllGlobals()
  }
})
