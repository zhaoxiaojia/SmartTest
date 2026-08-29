const TERMINAL = new Set(['success', 'failed', 'cancelled'])

export function createAsyncFeedback({ root, cancelButton, onCancel } = {}) {
  root.innerHTML = `<div class="async-feedback__head"><strong data-async-message></strong><span data-async-count></span></div>
    <div class="async-feedback__track" role="progressbar" aria-label="Task progress"><div class="async-feedback__fill"></div></div>`
  const message = root.querySelector('[data-async-message]')
  const count = root.querySelector('[data-async-count]')
  const track = root.querySelector('[role="progressbar"]')
  const fill = root.querySelector('.async-feedback__fill')
  let state = 'idle'
  let cancelling = false

  async function cancel() {
    if (state !== 'running' || cancelling || !onCancel) return
    cancelling = true
    cancelButton.disabled = true
    try { await onCancel() } finally { cancelling = false }
  }
  cancelButton?.addEventListener('click', cancel)

  function update(next = {}) {
    state = next.state || 'idle'
    const completed = Math.max(0, Number(next.completed) || 0)
    const total = Math.max(0, Number(next.total) || 0)
    const running = state === 'running'
    const determinate = running && total > 0
    root.hidden = state === 'idle'
    root.dataset.state = state
    message.textContent = next.message || ({ running: 'Working…', success: 'Completed',
      failed: 'Task failed', cancelled: 'Cancelled' }[state] ?? '')
    count.textContent = determinate ? `${completed}/${total}` : ''
    track.hidden = !running
    track.dataset.indeterminate = String(running && !determinate)
    track.removeAttribute('aria-valuenow'); track.removeAttribute('aria-valuemax')
    if (determinate) {
      track.setAttribute('aria-valuemin', '0')
      track.setAttribute('aria-valuenow', String(Math.min(completed, total)))
      track.setAttribute('aria-valuemax', String(total))
      fill.style.width = `${Math.min(100, completed / total * 100)}%`
    } else {
      track.removeAttribute('aria-valuemin')
      fill.style.width = ''
    }
    if (cancelButton) {
      cancelButton.hidden = !running
      cancelButton.disabled = !running || cancelling
    }
    if (TERMINAL.has(state)) root.setAttribute('aria-live', state === 'failed' ? 'assertive' : 'polite')
    else root.setAttribute('aria-live', 'polite')
  }

  update()
  return { update, get state() { return state } }
}
