import { createAsyncFeedback } from './async-feedback.js'
import { createDownloadButton } from './download-button.js'

function updateProgress(feedback, task, message = '') {
  const running = ['queued', 'running'].includes(task?.status)
  const state = running ? 'running' : ({
    completed: 'success', failed: 'failed', cancelled: 'cancelled'
  }[task?.status] ?? 'idle')
  feedback.update({
    state,
    stage: task?.stage,
    processed: task?.progress?.processed,
    total: task?.progress?.total,
    message,
  })
}

export function createJiraManualAudit({ root, api, pollDelay = () => new Promise(resolve => setTimeout(resolve, 500)), downloadNavigate }) {
  root.innerHTML = `<section class="report-workspace" data-jira-review>
    <header class="report-page-head"><div>
      <div class="eyebrow">Jira · Weekly Review</div>
      <h1>Jira Review</h1>
      <p>Review Jira issues against the current deterministic quality rules.</p>
    </div></header>
    <section class="card report-filter-card" data-audit-input-card>
      <h2>Review source</h2>
      <form class="jira-audit-form" data-audit-form><label class="jira-audit-query jira-audit-full-width">JQL, Issue URL, or Filter URL
        <textarea class="form-control" name="auditInput" rows="5" required></textarea></label>
        <div class="filter-actions jira-audit-controls" data-audit-controls>
          <button type="submit" class="button button-primary" data-start-audit>Start Review</button>
          <button type="button" class="button button-secondary" data-cancel-audit disabled>Cancel</button>
          <button type="button" class="button button-primary" data-audit-download disabled>Download</button>
        </div>
      </form>
      <div class="async-feedback" data-audit-progress></div>
    </section>
  </section>`
  const form = root.querySelector('[data-audit-form]')
  const start = root.querySelector('[data-start-audit]')
  const cancel = root.querySelector('[data-cancel-audit]')
  const feedback = createAsyncFeedback({ root: root.querySelector('[data-audit-progress]') })
  let auditId = ''
  let disposed = false

  const download = createDownloadButton({
    element: root.querySelector('[data-audit-download]'),
    prepare: async () => (await api.exportJiraAudit(auditId)).download,
    navigate: downloadNavigate,
    artifactUrl: api.downloadUrl,
  })
  download.element.disabled = true

  async function poll(task) {
    updateProgress(feedback, task)
    while (['queued', 'running'].includes(task.status)) {
      await pollDelay()
      if (disposed) return
      task = await api.getJiraAudit(auditId)
      if (disposed) return
      updateProgress(feedback, task)
    }
    cancel.disabled = true
    start.disabled = false
    download.element.disabled = task.status !== 'completed'
  }

  form.addEventListener('submit', async event => {
    event.preventDefault()
    start.disabled = true
    cancel.disabled = false
    download.element.disabled = true
    feedback.update({ state: 'running' })
    try {
      const task = await api.createJiraAudit({ input: form.elements.auditInput.value })
      if (disposed) return
      auditId = task.auditId
      await poll(task)
    } catch (error) {
      if (disposed) return
      updateProgress(feedback, { status: 'failed' }, error?.status === 422 ? 'invalid input' : 'audit unavailable')
      start.disabled = false
      cancel.disabled = true
    }
  })
  cancel.addEventListener('click', async () => {
    await api.cancelJiraAudit(auditId)
    cancel.disabled = true
  })
  return { root, destroy() { disposed = true; download.destroy() } }
}
