// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest'
import { createJiraTeamBugWidget } from '../src/widgets/jira-team-bugs.js'

const productLines = [
  { id: 'DOPL', projectKey: 'IPTV', people: [
    { identity: 'a', displayName: 'Alice', bugCount: 2, resolvedCount: 1, p0Count: 0, invalidCount: 1 },
    { identity: 'b', displayName: 'Bob', bugCount: 3, resolvedCount: 0, p0Count: 2, invalidCount: 0 },
  ] },
  { id: 'SDPL', projectKey: 'SH', people: [] },
  { id: 'TV', projectKey: 'TV', people: [] },
  { id: 'OOPL', projectKey: 'OTT', people: [] },
]

function mount(api, chartFactory = vi.fn(() => ({ destroy: vi.fn() }))) {
  document.body.innerHTML = '<div id="root"></div>'
  const widget = createJiraTeamBugWidget({ pollDelay: 0, chartFactory })
  widget.mount(document.querySelector('#root'), { api })
  return { widget, chartFactory }
}

describe('Jira team bug widget', () => {
  it('switches four metrics and product lines with sorted horizontal ranking data', async () => {
    const api = { getTeamBugOverview: vi.fn().mockResolvedValue({ state: 'ready', teamTotal: 5, productLines }) }
    const { widget, chartFactory } = mount(api)
    await vi.waitFor(() => expect(chartFactory).toHaveBeenCalled())
    expect(chartFactory.mock.calls.at(-1)[1].data.labels).toEqual(['Bob', 'Alice'])
    expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([3, 2])
    ;[...document.querySelectorAll('[data-mode-segments] button')].find(button => button.textContent === 'P0').click()
    expect(chartFactory.mock.results[0].value.destroy).toHaveBeenCalledOnce()
    expect(chartFactory.mock.calls.at(-1)[1].data.labels).toEqual(['Bob'])
    expect(chartFactory.mock.calls.at(-1)[1].data.datasets[0].data).toEqual([2])
    ;[...document.querySelectorAll('[data-product-line-segments] button')].find(button => button.textContent === 'Smart Device Business').click()
    expect(document.querySelector('[data-ranked-empty]').hidden).toBe(false)
    expect(document.body.textContent).not.toContain('%')
    expect(document.querySelector('table')).toBeNull()
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
