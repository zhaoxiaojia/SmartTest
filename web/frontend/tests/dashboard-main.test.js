// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ authenticated: null, dashboard: null }))

vi.mock('../src/authenticated-page.js', () => ({
  startAuthenticatedPage: vi.fn(options => { state.authenticated = options }),
}))
vi.mock('../src/dashboard/dashboard-grid.js', () => ({
  createDashboardGrid: vi.fn(options => { state.dashboard = options; return { start() {}, destroy() {} } }),
}))
vi.mock('gridstack', () => ({ GridStack: { init: vi.fn() } }))
vi.mock('chart.js', () => ({ Chart: Object.assign(vi.fn(), { register: vi.fn() }), registerables: [] }))
vi.mock('chartjs-plugin-datalabels', () => ({ default: {} }))

describe('Dashboard page', () => {
  beforeEach(() => {
    vi.resetModules()
    document.body.innerHTML = '<main></main>'
    state.authenticated = null
    state.dashboard = null
  })

  it('mounts the account dashboard with shared widget and existing APIs', async () => {
    await import('../src/dashboard-main.js')
    state.authenticated.mount(document.querySelector('main'), { username: 'coco' })
    expect(state.dashboard.registry.get('role-workload').title).toBe('Project Resource Statistics')
    expect(state.dashboard.registry.get('jira-team-bugs').title).toBe('Product Lines Self Test Jiras Statistics')
    const customer = state.dashboard.registry.get('jira-customer-statistics')
    expect(customer.title).toBe('Product Lines Customer Jiras Statistics')
    const target = document.createElement('div')
    customer.create().mount(target)
    expect(target.textContent).toBe('WeeklyMonthlyQuarterlyYearly')
    expect(await state.dashboard.widgetConfig('jira-customer-statistics')).toEqual({})
    expect(state.dashboard.preferenceApi).toMatchObject({ get: expect.any(Function), put: expect.any(Function), reset: expect.any(Function) })
    expect(state.dashboard.gridFactory).toBeTypeOf('function')
    expect(state.dashboard.widgetConfig).toBeTypeOf('function')
  })

  it('provides the account Jira overview API to its independent widget', async () => {
    await import('../src/dashboard-main.js')
    state.authenticated.mount(document.querySelector('main'), { username: 'coco' })
    expect((await state.dashboard.widgetConfig('jira-team-bugs')).api.getTeamBugOverview).toBeTypeOf('function')
  })

  it('loads Role workload from the complete account-visible catalog instead of the Projects filter snapshot', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ownerHierarchy: [], productSpaces: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)
    await import('../src/dashboard-main.js')
    state.authenticated.mount(document.querySelector('main'), { username: 'coco' })
    await state.dashboard.widgetConfig('role-workload')
    const url = new URL(fetchMock.mock.calls[0][0], 'http://localhost')
    expect(url.pathname).toBe('/api/confluence/project-facts')
    expect(url.search).toBe('')
    vi.unstubAllGlobals()
  })
})
