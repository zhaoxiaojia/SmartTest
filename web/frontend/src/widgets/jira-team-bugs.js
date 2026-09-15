import { createSegmentedRanking, DASHBOARD_PRODUCT_LINES } from './segmented-ranking.js'

export const JIRA_TEAM_BUG_LAYOUT = Object.freeze({ defaultW: 24, defaultH: 16 })

const METRICS = Object.freeze([
  Object.freeze({ value: 'bugCount', label: 'Bugs' }),
  Object.freeze({ value: 'resolvedCount', label: 'Resolved' }),
  Object.freeze({ value: 'p0Count', label: 'P0' }),
  Object.freeze({ value: 'invalidCount', label: 'Invalid' }),
])

export function createJiraTeamBugWidget({ pollDelay = 800, chartFactory } = {}) {
  let root = null
  let stopped = false
  let timer = null
  const ranking = createSegmentedRanking({ chartFactory })

  function message(text, kind = '') {
    ranking.destroy()
    root.innerHTML = `<div class="team-bug-state${kind ? ` ${kind}` : ''}" data-team-bug-state></div>`
    root.firstElementChild.textContent = text
  }

  function render(payload) {
    if (payload.state === 'failed') { message(payload.error || 'Jira team bug overview could not be loaded.', 'inline-status-error'); return false }
    if (payload.state !== 'ready') {
      const progress = payload.task?.progress
      message(progress?.total ? `Loading Jira bugs… ${progress.processed}/${progress.total}` : 'Loading Jira bugs…')
      return true
    }
    const byLine = new Map((payload.productLines ?? []).map(line => [line.id, line]))
    ranking.mount(root, {
      productLines: DASHBOARD_PRODUCT_LINES,
      modes: METRICS,
      emptyText: 'No bugs in this product line.',
      rowsFor: (productLine, metric) => (byLine.get(productLine)?.people ?? []).map(person => ({
        name: person.displayName, count: Number(person[metric] || 0),
      })),
      datasetLabel: 'Issues',
    })
    return false
  }

  async function load(api) {
    try {
      const again = render(await api.getTeamBugOverview())
      if (again && !stopped) timer = setTimeout(() => { void load(api) }, pollDelay)
    } catch (error) {
      if (!stopped) message(error.message || 'Jira team bug overview could not be loaded.', 'inline-status-error')
    }
  }

  return {
    mount(target, config = {}) {
      root = target; stopped = false
      if (!config.api) { message('Jira team bug API is unavailable.', 'inline-status-error'); return }
      void load(config.api)
    },
    update() {},
    destroy() { stopped = true; clearTimeout(timer); ranking.destroy(); root = null },
  }
}
