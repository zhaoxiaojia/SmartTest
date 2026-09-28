// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createJiraStatisticsCard, JIRA_STATISTICS_CARDS } from '../src/widgets/jira-statistics-card.js'

const productLines = [
  { id: 'China Operator', label: 'China Operator', people: [
    { identity: 'a', displayName: 'Alice', bugCount: 2, resolvedCount: 1, p0Count: 0, invalidCount: 1 },
    { identity: 'b', displayName: 'Bob', bugCount: 3, resolvedCount: 0, p0Count: 2, invalidCount: 0 },
  ] },
  { id: 'Smart Device', label: 'Smart Device', people: [] },
  { id: 'TV', label: 'TV', people: [] },
  { id: 'Global Operator & STB', label: 'Global Operator & STB', people: [] },
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

function mount(api, chartFactory = vi.fn(chartMock), account = 'coco', cardKey = 'self-test') {
  document.body.innerHTML = '<div id="root"></div>'
  const widget = createJiraStatisticsCard({ pollDelay: 0, chartFactory })
  widget.mount(document.querySelector('#root'), { api, account, cardKey })
  return { widget, chartFactory }
}

describe('Jira statistics card', () => {
  it('declares three cards with shared component metadata', () => {
    expect(Object.keys(JIRA_STATISTICS_CARDS)).toEqual(['self-test', 'task', 'customer-feedback'])
    expect(Object.values(JIRA_STATISTICS_CARDS).map(card => card.title)).toEqual([
      'Self-Test Jira Statistics by Product Line',
      'Task Jira Statistics by Product Line',
      'Customer Feedback Jira Statistics by Product Line',
    ])
    expect(JIRA_STATISTICS_CARDS.task.firstMetricLabel).toBe('Tasks')
    expect(JIRA_STATISTICS_CARDS['customer-feedback'].title).toContain('Customer Feedback')
  })
  it('restores a card period and queries only when its own period is changed', async () => {
    const api = { getStatistics: vi.fn().mockResolvedValue({ state: 'ready', productLines, period: 'quarter' }),
      queryStatistics: vi.fn().mockResolvedValue({ state: 'ready', productLines, period: 'week' }) }
    const { widget } = mount(api)
    await vi.waitFor(() => expect(document.querySelector('[data-jira-period="quarter"]').checked).toBe(true))
    const periods = document.querySelector('[data-jira-periods]')
    expect(periods.previousElementSibling.matches('.report-preview-toolbar')).toBe(true)
    expect(periods.parentElement).not.toBe(document.querySelector('[data-product-line-segments]').parentElement)
    document.querySelector('[data-jira-period="week"]').click()
    await vi.waitFor(() => expect(api.queryStatistics).toHaveBeenCalledWith('week', 'reuse'))
    expect(document.querySelector('[data-jira-period="week"]').checked).toBe(true)
    widget.update({ query: true })
    await vi.waitFor(() => expect(api.queryStatistics).toHaveBeenCalledWith(undefined, 'refresh'))
    widget.destroy()
  })
  it('keeps radio identities independent across card instances and associates visible labels', () => {
    document.body.innerHTML = '<div id="first"></div><div id="second"></div>'
    const api = { getStatistics: () => new Promise(() => {}) }
    const first = createJiraStatisticsCard(), second = createJiraStatisticsCard()
    first.mount(document.querySelector('#first'), { api, account: 'coco', cardKey: 'self-test' })
    second.mount(document.querySelector('#second'), { api, account: 'coco', cardKey: 'task' })
    const firstInputs = [...document.querySelectorAll('#first input')]
    const secondInputs = [...document.querySelectorAll('#second input')]
    expect(firstInputs).toHaveLength(4)
    expect(new Set([...firstInputs, ...secondInputs].map(input => input.id)).size).toBe(8)
    expect(firstInputs[0].name).not.toBe(secondInputs[0].name)
    expect(firstInputs.map(input => input.labels[0].textContent)).toEqual(['Weekly', 'Monthly', 'Quarterly', 'Yearly'])
    firstInputs[0].labels[0].click()
    expect(firstInputs[0].checked).toBe(true)
    expect(secondInputs[1].checked).toBe(true)
    first.destroy(); second.destroy()
  })
  it('does not render aggregate summary cards while retaining aggregate values in its disposable display', async () => {
    const api = { getStatistics: vi.fn().mockResolvedValue({
      state: 'ready', productLines, teamTotal: 12, unmappedCount: 2, unassignedCount: 1,
    }) }
    const { widget } = mount(api)
    await vi.waitFor(() => expect(document.querySelector('[data-ranked-chart]')).not.toBeNull())
    expect(document.querySelector('[data-jira-statistics-summary]')).toBeNull()
    expect(document.body.textContent).not.toContain('Current total')
    expect(document.body.textContent).not.toContain('Previous total')
    expect(document.body.textContent).not.toContain('Unmapped projects')
    expect(document.body.textContent).not.toContain('Missing creators')
    const cached = JSON.parse(sessionStorage.getItem('smarttest:jira-statistics-display:coco:self-test'))
    expect(cached.unmappedCount).toBe(2)
    expect(cached.productLines).toHaveLength(5)
    widget.destroy()
  })
  it('never renders query JQL and keeps dimension clicks presentation-only', async () => {
    const api = { getStatistics: vi.fn().mockResolvedValue({ state: 'ready', productLines,
      query: { activeJql: 'aggregate query' } }) }
    const { widget } = mount(api, undefined, 'coco', 'task')
    await vi.waitFor(() => expect(document.querySelector('[data-ranked-chart]')).not.toBeNull())
    expect(document.body.textContent).not.toContain('aggregate query')
    document.querySelector('[data-product-line-segments] button[data-value="TV"]').click()
    document.querySelector('[data-mode-segments] button[data-value="p0Count"]').click()
    expect(api.getStatistics).toHaveBeenCalledTimes(1)
    widget.destroy()
  })
  beforeEach(() => { sessionStorage.clear() })

  it('stops polling after cancellation without removing its last display', async () => {
    sessionStorage.setItem('smarttest:jira-statistics-display:coco:self-test', JSON.stringify({ state: 'ready', productLines }))
    const api = { getStatistics: vi.fn().mockResolvedValue({ state: 'cancelled', error: 'Query cancelled.' }) }
    const { widget, chartFactory } = mount(api)
    await vi.waitFor(() => expect(document.body.textContent).toContain('Query cancelled.'))
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(api.getStatistics).toHaveBeenCalledTimes(1)
    expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([3, 2])
    widget.destroy()
  })

  it('reuses the same card display on any page and calibrates it from SQLite', async () => {
    sessionStorage.setItem('smarttest:jira-statistics-display:coco:self-test', JSON.stringify({ state: 'ready', productLines }))
    document.body.innerHTML = '<div id="root"></div>'
    const chartFactory = vi.fn(chartMock)
    const api = { getStatistics: vi.fn().mockResolvedValue({ state: 'no_snapshot' }) }
    const widget = createJiraStatisticsCard({ chartFactory })
    widget.mount(document.querySelector('#root'), { api, account: 'coco' })
    expect(chartFactory).toHaveBeenCalledOnce()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Apply a Jira query'))
    api.getStatistics.mockResolvedValue({ state: 'ready', productLines })
    widget.update()
    await vi.waitFor(() => expect(chartFactory).toHaveBeenCalledTimes(2))
    expect(sessionStorage.getItem('smarttest:jira-statistics-display:coco:self-test')).not.toBeNull()
    widget.destroy()
  })

  it('replays disposable display immediately and calibrates it from the SQLite response', async () => {
    sessionStorage.setItem('smarttest:jira-statistics-display:coco:self-test', JSON.stringify({ state: 'ready', productLines }))
    let resolve
    const api = { getStatistics: () => new Promise(done => { resolve = done }) }
    const { widget, chartFactory } = mount(api)
    expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([3, 2])
    resolve({ state: 'ready', productLines: [{ ...productLines[0], people: [{ ...productLines[0].people[0], bugCount: 8 }] }] })
    await vi.waitFor(() => expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([8]))
    const stored = JSON.parse(sessionStorage.getItem('smarttest:jira-statistics-display:coco:self-test'))
    expect(stored.productLines[0].people[0]).not.toHaveProperty('identity')
    expect(stored).not.toHaveProperty('task')
    widget.destroy()
  })

  it('retains a displayed graph during refresh, polls, and replaces it in place when fresh', async () => {
    sessionStorage.setItem('smarttest:jira-statistics-display:coco:self-test', JSON.stringify({ state: 'ready', productLines }))
    let resolveFresh
    const api = { getStatistics: vi.fn()
      .mockResolvedValueOnce({ state: 'loading', task: null, productLines })
      .mockImplementationOnce(() => new Promise(done => { resolveFresh = done })) }
    const { widget, chartFactory } = mount(api)
    await vi.waitFor(() => expect(resolveFresh).toBeTypeOf('function'))
    expect(document.querySelector('[data-ranked-chart]')).not.toBeNull()
    expect(document.body.textContent).toContain('Loading Jira')
    expect(chartFactory).toHaveBeenCalledOnce()
    resolveFresh({ state: 'ready', productLines: [{ ...productLines[0], people: [{ ...productLines[0].people[0], bugCount: 7 }] }] })
    await vi.waitFor(() => expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([7]))
    expect(document.querySelector('[data-jira-statistics-state]')).toBeNull()
    widget.destroy()
  })

  it('keeps the graph and reports a background failure instead of clearing it', async () => {
    sessionStorage.setItem('smarttest:jira-statistics-display:coco:self-test', JSON.stringify({ state: 'ready', productLines }))
    const { widget } = mount({ getStatistics: async () => ({ state: 'failed', error: 'jira_search_failed' }) })
    await vi.waitFor(() => expect(document.body.textContent).toContain('jira_search_failed'))
    expect(document.querySelector('[data-ranked-chart]')).not.toBeNull()
    widget.destroy()
  })

  it('does not reuse another account display and shows loading only on a first empty visit', () => {
    sessionStorage.setItem('smarttest:jira-statistics-display:alice:self-test', JSON.stringify({ state: 'ready', productLines }))
    const { widget, chartFactory } = mount({ getStatistics: () => new Promise(() => {}) }, undefined, 'bob')
    expect(chartFactory).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Loading Jira')
    widget.destroy()
  })
  it('switches four metrics and product lines with sorted horizontal ranking data', async () => {
    const api = { getStatistics: vi.fn().mockResolvedValue({ state: 'ready', teamTotal: 5, productLines }) }
    const { widget, chartFactory } = mount(api)
    await vi.waitFor(() => expect(chartFactory).toHaveBeenCalled())
    expect(document.querySelector('[data-product-line-segments] button').textContent).toBe('China Operator')
    const bugsChart = chartFactory.mock.calls.at(-1)[1]
    expect(bugsChart.data.labels).toEqual(['Bob', 'Alice'])
    expect(bugsChart.data.datasets[0].data).toEqual([3, 2])
    expect(bugsChart.options.plugins.datalabels.labels.percentage.formatter(3)).toBe('3 · 60%')
    expect(bugsChart.options.plugins.datalabels.labels.value.formatter(3)).toBeNull()
    expect(bugsChart.options.plugins.datalabels.labels.value.align).toBe('right')
    ;[...document.querySelectorAll('[data-mode-segments] button')].find(button => button.textContent === 'P0').click()
    expect(chartFactory.mock.results[0].value.destroy).not.toHaveBeenCalled()
    expect(chartFactory.mock.results[0].value.reset).toHaveBeenCalledOnce()
    expect(chartFactory.mock.calls.at(-1)[1].data.labels).toEqual(['Bob'])
    expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([2])
    ;[...document.querySelectorAll('[data-product-line-segments] button')].find(button => button.textContent === 'Smart Device').click()
    expect(document.querySelector('[data-ranked-empty]').hidden).toBe(false)
    expect(document.body.textContent).not.toContain('%')
    expect(document.querySelector('table')).toBeNull()
    ;[...document.querySelectorAll('[data-product-line-segments] button')].find(button => button.textContent === 'Wireless Connection').click()
    expect(chartFactory.mock.calls.at(-1)[1].data.labels).toEqual(['WiFi Owner'])
    widget.destroy()
    expect(chartFactory.mock.results[1].value.destroy).toHaveBeenCalledOnce()
  })

  it('groups current and previous values with readable comparison labels and ranges', async () => {
    const previousLines = productLines.map(line => ({ ...line, people: line.id === 'China Operator' ? [
      { identity: 'a', displayName: 'Alice', bugCount: 5, resolvedCount: 2, p0Count: 0, invalidCount: 0 },
      { identity: 'c', displayName: 'Carol', bugCount: 4, resolvedCount: 1, p0Count: 0, invalidCount: 0 },
    ] : [] }))
    const api = { getStatistics: vi.fn().mockResolvedValue({ state: 'ready', period: 'month',
      ranges: { current: { start: '2026-09-01', end: null }, previous: { start: '2026-08-01', end: '2026-09-01' } },
      current: { teamTotal: 5, productLines, unmappedCount: 0, unassignedCount: 0 },
      previous: { teamTotal: 9, productLines: previousLines, unmappedCount: 0, unassignedCount: 0 },
    }) }

    const { widget, chartFactory } = mount(api)
    await vi.waitFor(() => expect(chartFactory).toHaveBeenCalled())
    const chart = chartFactory.mock.calls.at(-1)[1]
    expect(chart.data.labels).toEqual(['Bob', 'Alice', 'Carol'])
    expect(chart.data.datasets.map(dataset => dataset.data)).toEqual([[3, 2, 0], [0, 5, 4]])
    expect(chart.data.datasets.map(dataset => dataset.barThickness)).toEqual([12, 12])
    expect(chart.data.datasets.every(dataset => dataset.grouped)).toBe(true)
    expect(chart.options.plugins.datalabels.labels.value.formatter(2, { dataIndex: 1, datasetIndex: 0 })).toBe('↓ 3')
    expect(chart.options.plugins.datalabels.labels.value.formatter(5, { dataIndex: 1, datasetIndex: 1 })).toBeNull()
    expect(chart.options.plugins.tooltip.callbacks.afterBody([{ dataIndex: 1 }])).toContain('Current: 2026-09-01 – now')
    expect(chart.options.plugins.tooltip.callbacks.afterBody([{ dataIndex: 1 }])).toContain('Previous: 2026-08-01 – 2026-09-01')
    widget.destroy()
  })

  it('polls loading state and renders explicit failure', async () => {
    const api = { getStatistics: vi.fn()
      .mockResolvedValueOnce({ state: 'loading', task: { progress: { processed: 2, total: 10 } } })
      .mockResolvedValueOnce({ state: 'failed', error: 'jira_search_failed' }) }
    mount(api)
    await vi.waitFor(() => expect(document.body.textContent).toContain('jira_search_failed'))
    expect(api.getStatistics).toHaveBeenCalledTimes(2)
  })
})
