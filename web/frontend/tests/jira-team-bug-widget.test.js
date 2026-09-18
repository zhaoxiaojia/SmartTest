// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createJiraTeamBugWidget } from '../src/widgets/jira-team-bugs.js'

const productLines = [
  { id: 'China Operator Business', label: 'China Operator Business', people: [
    { identity: 'a', displayName: 'Alice', bugCount: 2, resolvedCount: 1, p0Count: 0, invalidCount: 1 },
    { identity: 'b', displayName: 'Bob', bugCount: 3, resolvedCount: 0, p0Count: 2, invalidCount: 0 },
  ] },
  { id: 'Smart Device Business', label: 'Smart Device Business', people: [] },
  { id: 'TV Business', label: 'TV Business', people: [] },
  { id: 'Global Operator & STB Business', label: 'Global Operator & STB Business', people: [] },
  { id: 'Wireless Connection', label: 'Wireless Connection', people: [
    { identity: 'w', displayName: 'WiFi Owner', bugCount: 4, resolvedCount: 2, p0Count: 1, invalidCount: 0 },
  ] },
]

function chartMock(_canvas, config) {
  return {
    get data() { return config.data }, set data(value) { config.data = value },
    get options() { return config.options }, set options(value) { config.options = value },
    update: vi.fn(), reset: vi.fn(), stop: vi.fn(), destroy: vi.fn(),
  }
}

function mount(api, chartFactory = vi.fn(chartMock), account = 'coco') {
  document.body.innerHTML = '<div id="root"></div>'
  const widget = createJiraTeamBugWidget({ pollDelay: 0, chartFactory })
  widget.mount(document.querySelector('#root'), { api, account })
  return { widget, chartFactory }
}

describe('Jira team bug widget', () => {
  it('shows unmapped project and missing reporter counts without inventing a product line', async () => {
    const api = { getTeamBugOverview: vi.fn().mockResolvedValue({
      state: 'ready', productLines, teamTotal: 12, unmappedCount: 2, unassignedCount: 1,
    }) }
    const { widget } = mount(api)
    await vi.waitFor(() => expect(document.body.textContent).toContain('Unmapped project: 2'))
    expect(document.body.textContent).toContain('Missing reporter: 1')
    expect(document.body.textContent).toContain('Total: 12')
    const cached = JSON.parse(sessionStorage.getItem('smarttest:jira-self-test-display:coco'))
    expect(cached.unmappedCount).toBe(2)
    expect(cached.productLines).toHaveLength(5)
    widget.destroy()
  })
  beforeEach(() => { sessionStorage.clear() })

  it('stops polling after cancellation without removing its last display', async () => {
    sessionStorage.setItem('smarttest:jira-self-test-display:coco', JSON.stringify({ state: 'ready', productLines }))
    const api = { getTeamBugOverview: vi.fn().mockResolvedValue({ state: 'cancelled', error: 'Query cancelled.' }) }
    const { widget, chartFactory } = mount(api)
    await vi.waitFor(() => expect(document.body.textContent).toContain('Query cancelled.'))
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(api.getTeamBugOverview).toHaveBeenCalledTimes(1)
    expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([3, 2])
    widget.destroy()
  })

  it('reuses the same card display on any page and calibrates it from SQLite', async () => {
    sessionStorage.setItem('smarttest:jira-self-test-display:coco', JSON.stringify({ state: 'ready', productLines }))
    document.body.innerHTML = '<div id="root"></div>'
    const chartFactory = vi.fn(chartMock)
    const api = { getTeamBugOverview: vi.fn().mockResolvedValue({ state: 'no_snapshot' }) }
    const widget = createJiraTeamBugWidget({ chartFactory })
    widget.mount(document.querySelector('#root'), { api, account: 'coco' })
    expect(chartFactory).toHaveBeenCalledOnce()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Apply a Jira query'))
    api.getTeamBugOverview.mockResolvedValue({ state: 'ready', productLines })
    widget.update()
    await vi.waitFor(() => expect(chartFactory).toHaveBeenCalledTimes(2))
    expect(sessionStorage.getItem('smarttest:jira-self-test-display:coco')).not.toBeNull()
    widget.destroy()
  })

  it('replays disposable display immediately and calibrates it from the SQLite response', async () => {
    sessionStorage.setItem('smarttest:jira-self-test-display:coco', JSON.stringify({ state: 'ready', productLines }))
    let resolve
    const api = { getTeamBugOverview: () => new Promise(done => { resolve = done }) }
    const { widget, chartFactory } = mount(api)
    expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([3, 2])
    resolve({ state: 'ready', productLines: [{ ...productLines[0], people: [{ ...productLines[0].people[0], bugCount: 8 }] }] })
    await vi.waitFor(() => expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([8]))
    const stored = JSON.parse(sessionStorage.getItem('smarttest:jira-self-test-display:coco'))
    expect(stored.productLines[0].people[0]).not.toHaveProperty('identity')
    expect(stored).not.toHaveProperty('task')
    widget.destroy()
  })

  it('retains a displayed graph during refresh, polls, and replaces it in place when fresh', async () => {
    sessionStorage.setItem('smarttest:jira-self-test-display:coco', JSON.stringify({ state: 'ready', productLines }))
    let resolveFresh
    const api = { getTeamBugOverview: vi.fn()
      .mockResolvedValueOnce({ state: 'loading', task: null, productLines })
      .mockImplementationOnce(() => new Promise(done => { resolveFresh = done })) }
    const { widget, chartFactory } = mount(api)
    await vi.waitFor(() => expect(resolveFresh).toBeTypeOf('function'))
    expect(document.querySelector('[data-ranked-chart]')).not.toBeNull()
    expect(document.body.textContent).toContain('Loading Jira')
    expect(chartFactory).toHaveBeenCalledOnce()
    resolveFresh({ state: 'ready', productLines: [{ ...productLines[0], people: [{ ...productLines[0].people[0], bugCount: 7 }] }] })
    await vi.waitFor(() => expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([7]))
    expect(document.querySelector('[data-team-bug-state]')).toBeNull()
    widget.destroy()
  })

  it('keeps the graph and reports a background failure instead of clearing it', async () => {
    sessionStorage.setItem('smarttest:jira-self-test-display:coco', JSON.stringify({ state: 'ready', productLines }))
    const { widget } = mount({ getTeamBugOverview: async () => ({ state: 'failed', error: 'jira_search_failed' }) })
    await vi.waitFor(() => expect(document.body.textContent).toContain('jira_search_failed'))
    expect(document.querySelector('[data-ranked-chart]')).not.toBeNull()
    widget.destroy()
  })

  it('does not reuse another account display and shows loading only on a first empty visit', () => {
    sessionStorage.setItem('smarttest:jira-self-test-display:alice', JSON.stringify({ state: 'ready', productLines }))
    const { widget, chartFactory } = mount({ getTeamBugOverview: () => new Promise(() => {}) }, undefined, 'bob')
    expect(chartFactory).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Loading Jira')
    widget.destroy()
  })
  it('switches four metrics and product lines with sorted horizontal ranking data', async () => {
    const api = { getTeamBugOverview: vi.fn().mockResolvedValue({ state: 'ready', teamTotal: 5, productLines }) }
    const { widget, chartFactory } = mount(api)
    await vi.waitFor(() => expect(chartFactory).toHaveBeenCalled())
    expect(document.querySelector('[data-product-line-segments] button').textContent).toBe('China Operator Business')
    const bugsChart = chartFactory.mock.calls.at(-1)[1]
    expect(bugsChart.data.labels).toEqual(['Bob', 'Alice'])
    expect(bugsChart.data.datasets[0].data).toEqual([3, 2])
    expect(bugsChart.options.plugins.datalabels.labels.percentage.formatter(3)).toBe('60%')
    expect(bugsChart.options.plugins.datalabels.labels.percentage.align).toBe('left')
    expect(bugsChart.options.plugins.datalabels.labels.value.formatter(3)).toBe(3)
    expect(bugsChart.options.plugins.datalabels.labels.value.align).toBe('right')
    ;[...document.querySelectorAll('[data-mode-segments] button')].find(button => button.textContent === 'P0').click()
    expect(chartFactory.mock.results[0].value.destroy).not.toHaveBeenCalled()
    expect(chartFactory.mock.results[0].value.reset).toHaveBeenCalledOnce()
    expect(chartFactory.mock.calls.at(-1)[1].data.labels).toEqual(['Bob'])
    expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([2])
    ;[...document.querySelectorAll('[data-product-line-segments] button')].find(button => button.textContent === 'Smart Device Business').click()
    expect(document.querySelector('[data-ranked-empty]').hidden).toBe(false)
    expect(document.body.textContent).not.toContain('%')
    expect(document.querySelector('table')).toBeNull()
    ;[...document.querySelectorAll('[data-product-line-segments] button')].find(button => button.textContent === 'Wireless Connection').click()
    expect(chartFactory.mock.calls.at(-1)[1].data.labels).toEqual(['WiFi Owner'])
    widget.destroy()
    expect(chartFactory.mock.results[1].value.destroy).toHaveBeenCalledOnce()
  })

  it('polls loading state and renders explicit failure', async () => {
    const api = { getTeamBugOverview: vi.fn()
      .mockResolvedValueOnce({ state: 'loading', task: { progress: { processed: 2, total: 10 } } })
      .mockResolvedValueOnce({ state: 'failed', error: 'jira_search_failed' }) }
    mount(api)
    await vi.waitFor(() => expect(document.body.textContent).toContain('jira_search_failed'))
    expect(api.getTeamBugOverview).toHaveBeenCalledTimes(2)
  })
})
