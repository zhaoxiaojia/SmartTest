import { createRankingCard } from './ranking-card.js'
import { createDisposableDisplayCache } from '../disposable-display.js'

export const JIRA_TEAM_BUG_LAYOUT = Object.freeze({ defaultW: 24 })
export const JIRA_SELF_TEST_TITLE = 'Product Lines Self Test Jiras Statistics'
export const JIRA_CUSTOMER_TITLE = 'Product Lines Customer Jiras Statistics'

const PERIODS = [{ value: 'week', label: 'Weekly' }, { value: 'month', label: 'Monthly' },
  { value: 'quarter', label: 'Quarterly' }, { value: 'year', label: 'Yearly' }]
let periodInstance = 0
function periodMarkup(preferences = false) {
  const name = `jira-period-${++periodInstance}`
  return `<fieldset class="jira-period-fieldset" data-jira-periods aria-label="Statistics period" ${preferences ? 'data-preference-region data-preference-scope="jira/cards/customer"' : ''}>${PERIODS.map(item => `<div class="jira-period-button-group"><input type="radio" name="${name}" id="${name}-${item.value}" value="${item.value}" data-jira-period="${item.value}" ${item.value === 'month' ? 'checked' : ''} ${preferences ? 'data-preference-key="period"' : ''}><label for="${name}-${item.value}">${item.label}</label></div>`).join('')}</fieldset>`
}

export function createJiraCustomerPlaceholder() {
  let root
  return { mount(target) { root = target; root.innerHTML = periodMarkup(true) }, update() {}, destroy() { root?.replaceChildren() } }
}

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
  let displayed = false
  let displaySignature = ''
  let displayCache
  let api
  let generation = 0
  let rankingHost, periods
  let period = 'month'
  const ranking = createRankingCard({ chartFactory })

  function message(text, kind = '') {
    if (!displayed) rankingHost.replaceChildren()
    let status = root.querySelector('[data-team-bug-state]')
    if (!status) {
      status = document.createElement('div')
      status.dataset.teamBugState = ''
      root.append(status)
    }
    status.className = `team-bug-state${kind ? ` ${kind}` : ''}`
    status.textContent = text
  }

  function render(payload) {
    if (payload.period) period = payload.period
    selectPeriod()
    if (payload.state === 'no_snapshot') {
      root.prepend(periods)
      ranking.destroy(); displayed = false; displaySignature = ''
      displayCache.write(null)
      message('Apply a Jira query to display statistics.')
      return false
    }
    if (payload.productLines) draw(payload)
    if (['failed', 'cancelled'].includes(payload.state)) { message(payload.error || 'Jira query did not complete.', 'inline-status-error'); return false }
    if (payload.state !== 'ready') {
      const progress = payload.task?.progress
      message(progress?.total ? `Loading Jira bugs… ${progress.processed}/${progress.total}` : 'Loading Jira bugs…')
      return true
    }
    root.querySelector('[data-team-bug-state]')?.remove()
    return false
  }

  function draw(payload) {
    if (payload.period) period = payload.period
    const display = { state: 'ready', period, teamTotal: payload.teamTotal,
      unmappedCount: Number(payload.unmappedCount || 0), unassignedCount: Number(payload.unassignedCount || 0),
      productLines: payload.productLines.map(line => ({ id: line.id, label: line.label,
        people: (line.people ?? []).map(person => ({ displayName: person.displayName,
          ...Object.fromEntries(METRICS.map(metric => [metric.value, Number(person[metric.value] || 0)])),
        })),
      })),
    }
    const signature = JSON.stringify(display)
    if (displayed && signature === displaySignature) return
    const byLine = new Map((payload.productLines ?? []).map(line => [line.id, line]))
    const presentation = {
      productLines: (payload.productLines ?? []).map(line => ({ value: line.id, label: line.label })),
      modes: METRICS,
      emptyText: 'No bugs in this product line.',
      rowsFor: (productLine, metric) => (byLine.get(productLine)?.people ?? []).map(person => ({
        name: person.displayName, count: Number(person[metric] || 0),
      })),
      datasetLabel: 'Issues',
    }
    if (displayed) ranking.update(presentation)
    else ranking.mount(rankingHost, presentation)
    root.querySelector('.report-preview-toolbar').after(periods)
    selectPeriod()
    let summary = root.querySelector('[data-team-bug-summary]')
    if (!summary) {
      summary = document.createElement('p')
      summary.className = 'card-subtitle ranking-card-summary'
      summary.dataset.teamBugSummary = ''
      root.querySelector('.report-preview-toolbar').before(summary)
    }
    summary.textContent = `Total: ${Number(payload.teamTotal || 0)} · Unmapped project: ${display.unmappedCount} · Missing reporter: ${display.unassignedCount}`
    displayed = true
    displaySignature = signature
    displayCache.write(display)
  }

  function selectPeriod() {
    for (const input of periods.querySelectorAll('input')) input.checked = input.value === period
  }

  async function load(request = ++generation, query = false, selectedPeriod) {
    clearTimeout(timer)
    try {
      const payload = await (query ? api.queryTeamBugOverview(selectedPeriod, selectedPeriod ? 'reuse' : 'refresh') : api.getTeamBugOverview())
      if (stopped || request !== generation) return
      const again = render(payload)
      if (again && !stopped) timer = setTimeout(() => { void load() }, pollDelay)
    } catch (error) {
      if (!stopped && request === generation) message(error.message || 'Jira team bug overview could not be loaded.', 'inline-status-error')
    }
  }

  return {
    mount(target, config = {}) {
      root = target; stopped = false
      period = 'month'
      root.innerHTML = `${periodMarkup()}<div data-jira-ranking></div>`
      rankingHost = root.querySelector('[data-jira-ranking]')
      periods = root.querySelector('[data-jira-periods]')
      periods.addEventListener('change', event => {
        const selected = event.target.closest('[data-jira-period]')?.dataset.jiraPeriod
        if (selected && selected !== period && api) {
          period = selected; selectPeriod(); void load(++generation, true, period)
        }
      })
      displayed = false
      displayCache = createDisposableDisplayCache('jiraSelfTest', config.account)
      const cached = displayCache.read()
      if (cached?.productLines) draw(cached)
      else message('Loading Jira bugs…')
      if (!config.api) { message('Jira team bug API is unavailable.', 'inline-status-error'); return }
      api = config.api
      void load()
    },
    update({ query = false } = {}) { if (!stopped && api) void load(++generation, query) },
    destroy() { stopped = true; clearTimeout(timer); ranking.destroy(); root = null; displayed = false },
  }
}
