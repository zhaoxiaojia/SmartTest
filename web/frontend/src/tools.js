import { createJiraManualAudit } from './manual-audits.js'
import { createProjects } from './projects.js'

export function createTools({ root, api, account, waitForPreferences, pollDelay, downloadNavigate }) {
  root.innerHTML = `<section class="report-workspace tools-workspace">
    <header class="report-page-head"><div><div class="eyebrow">Tools · Reviews</div><h1>Tools</h1><p>Manage shared review scopes and weekly review tools.</p></div></header>
    <section class="card report-filter-card"><h2>Jira Filter</h2><form data-jira-filter>
      <div class="report-filter-grid" data-jira-facets></div>
      <label>JQL<textarea class="form-control" name="jql" rows="3"></textarea></label>
      <div class="filter-actions"><button class="button button-primary" type="submit">Apply</button><button class="button button-secondary" type="button" data-jira-reset>Reset</button></div>
      <div class="inline-status" data-jira-filter-status></div></form></section>
    <div data-jira-review-host></div>
    <div data-confluence-filter-host></div>
    <section class="card settings-section"><h2>定期审查邮件</h2><p>手动触发每周审查，查看 Jira、Confluence 报告及逐次历史。</p><a class="button button-primary" href="/audit-email.html">管理审查报告</a></section>
  </section>`
  const form = root.querySelector('[data-jira-filter]')
  const status = root.querySelector('[data-jira-filter-status]')
  let disposed = false

  function renderJira(payload) {
    const applied = payload.snapshot?.filters ?? {}
    root.querySelector('[data-jira-facets]').innerHTML = (payload.facets ?? []).map(facet => `<label>${facet.label}<select class="form-control" name="${facet.key}" multiple>${(facet.options ?? []).map(value => `<option value="${escapeHtml(value)}"${applied[facet.key]?.includes(value) ? ' selected' : ''}>${escapeHtml(value)}</option>`).join('')}</select></label>`).join('')
    form.elements.jql.value = payload.snapshot?.jql ?? ''
  }
  function selection() {
    return { filters: Object.fromEntries(['project', 'type', 'status', 'currentUser', 'resolution']
      .map(key => [key, [...(form.elements[key]?.selectedOptions ?? [])].map(option => option.value)]).filter(([, values]) => values.length)),
    jql: form.elements.jql.value }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault(); status.textContent = 'Applying…'
    try { renderJira(await api.applyJiraFilterSnapshot(selection())); status.textContent = '' }
    catch { status.textContent = 'Jira filter unavailable.' }
  })
  root.querySelector('[data-jira-reset]').addEventListener('click', async () => {
    try { renderJira(await api.resetJiraFilterSnapshot()); status.textContent = '' }
    catch { status.textContent = 'Jira filter unavailable.' }
  })
  const jiraReview = createJiraManualAudit({ root: root.querySelector('[data-jira-review-host]'), api, pollDelay, downloadNavigate, standaloneInput: false })
  const confluence = createProjects({ root: root.querySelector('[data-confluence-filter-host]'), api, account,
    waitForPreferences, pollDelay, downloadNavigate, enableReview: true, filterOnly: true })
  return {
    async start() {
      const jira = api.getJiraFilterSnapshot().then(payload => { if (!disposed) renderJira(payload) })
        .catch(() => { if (!disposed) status.textContent = 'Jira filter unavailable.' })
      await Promise.allSettled([jira, confluence.start()])
    },
    destroy() { disposed = true; jiraReview.destroy(); confluence.destroy() },
  }
}

function escapeHtml(value) {
  const element = document.createElement('span'); element.textContent = String(value ?? ''); return element.innerHTML
}
