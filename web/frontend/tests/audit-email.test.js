// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import { createAuditEmailPage } from '../src/audit-email.js'

it('triggers only explicitly and displays both frozen reports', async () => {
  document.body.innerHTML = '<div id="page"></div>'
  let count = 0
  const detail = { id: 'run-1', state: 'historical_preview', evidence: 'email=not_sent', reports: {
    jira: { html: '<p>118</p>' }, confluence: { html: '<p>12 / 168</p>' }
  } }
  const api = {
    listEvents: async () => ({ events: [] }),
    list: async () => ({ runs: count ? [{ id: 'run-1', label: '2026-09-07T03:00:00Z', state: 'historical_preview', source: 'manual' }] : [], total: count }),
    get: async () => detail,
    trigger: async () => { count++; return detail }
  }
  const page = createAuditEmailPage({ root: document.querySelector('#page'), api })
  await page.start()
  expect(count).toBe(0)
  document.querySelector('[data-trigger]').click()
  await vi.waitFor(() => expect(document.querySelector('[data-evidence]').value).toBe('email=not_sent'))
  expect(count).toBe(1)
  expect(document.querySelector('[title="Jira 报告预览"]').srcdoc).toBe('<p>118</p>')
  expect(document.querySelector('[title="Confluence 报告预览"]').srcdoc).toBe('<p>12 / 168</p>')
  document.querySelector('[data-view]').click()
  await vi.waitFor(() => expect(document.querySelector('[data-status]').textContent).toContain('run-1'))
  expect(count).toBe(1)
  page.destroy()
  expect(document.querySelector('iframe')).toBeNull()
})

it('polls real execution until complete and exposes the saved attachment', async () => {
  document.body.innerHTML = '<div id="page"></div>'
  const complete = { id: 'new', state: 'completed', evidence: 'finished', reports: {
    jira: { html: '<p>actual</p>', attachments: ['jira.xlsx'] }, confluence: { html: '' }
  } }
  const api = { listEvents: async () => ({ events: [] }), list: async () => ({ runs: [], total: 0 }),
    trigger: async () => ({ ...complete, state: 'running', evidence: 'auditing' }),
    get: async () => complete, attachmentUrl: () => '/api/attachment.xlsx' }
  const page = createAuditEmailPage({ root: document.querySelector('#page'), api, pollDelay: async () => {} })
  await page.start()
  document.querySelector('[data-trigger]').click()
  await vi.waitFor(() => expect(document.querySelector('[data-evidence]').value).toBe('finished'))
  expect(document.querySelector('a').getAttribute('href')).toBe('/api/attachment.xlsx')
  expect(document.querySelector('[data-trigger]').disabled).toBe(false)
  page.destroy()
})

it('exposes trigger errors and discards responses after account change', async () => {
  document.body.innerHTML = '<div id="page"></div>'
  let finish
  const api = { listEvents: async () => ({ events: [] }), list: async () => ({ runs: [], total: 0 }), trigger: async () => { throw Error('Service unavailable') } }
  const page = createAuditEmailPage({ root: document.querySelector('#page'), api })
  await page.start()
  document.querySelector('[data-trigger]').click()
  await vi.waitFor(() => expect(document.querySelector('[data-status]').textContent).toBe('Service unavailable'))
  api.trigger = () => new Promise(resolve => { finish = resolve })
  document.querySelector('[data-trigger]').click()
  page.destroy()
  finish({ id: 'old-account' })
  await Promise.resolve()
  expect(document.body.textContent).not.toContain('old-account')
})


it('creates a future Beijing event explicitly, polls delivery states and opens its run', async () => {
  document.body.innerHTML = '<div id="page"></div>'
  let event
  const api = {
    list: async () => ({ runs: [], total: 0 }),
    listEvents: async () => ({ events: event ? [event] : [] }),
    createEvent: vi.fn(async dueAt => {
      event = { id: 'event-1', dueAt, state: 'completed', runId: 'run-event', deliveries: { jira: { state: 'accepted' }, confluence: { state: 'failed', error: 'OutlookSendError' } } }
      return event
    }),
    get: vi.fn(async () => ({ id: 'run-event', state: 'partial', reports: {}, evidence: 'smtp_failed' }))
  }
  const page = createAuditEmailPage({ root: document.querySelector('#page'), api })
  await page.start()
  expect(api.createEvent).not.toHaveBeenCalled()
  const date = document.querySelector('[data-event-time]')
  date.value = '2099-09-07T15:30'
  document.querySelector('[data-event-form]').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
  await vi.waitFor(() => expect(api.createEvent).toHaveBeenCalledWith('2099-09-07T15:30:00+08:00'))
  await vi.waitFor(() => expect(document.querySelector('[data-events]').textContent).toContain('SMTP 已接受'))
  expect(document.querySelector('[data-events]').textContent).toContain('OutlookSendError')
  document.querySelector('[data-event-view]').click()
  await vi.waitFor(() => expect(api.get).toHaveBeenCalledWith('run-event'))
  page.destroy()
})


it('refreshes pending events and displays creation errors without fake success', async () => {
  document.body.innerHTML = '<div id="page"></div>'
  const api = { list: async () => ({ runs: [], total: 0 }),
    listEvents: vi.fn().mockResolvedValueOnce({ events: [{ id: 'pending', dueAt: '2099-09-07T15:30+08:00', state: 'pending', deliveries: {} }] })
      .mockResolvedValue({ events: [{ id: 'pending', dueAt: '2099-09-07T15:30+08:00', state: 'failed', error: 'interrupted', deliveries: {} }] }),
    createEvent: vi.fn().mockRejectedValue(Error('Service unavailable')) }
  vi.useFakeTimers()
  const page = createAuditEmailPage({ root: document.querySelector('#page'), api })
  try {
    await page.start()
    expect(document.querySelector('[data-events]').textContent).toContain('等待到期')
    await vi.advanceTimersByTimeAsync(1000)
    expect(document.querySelector('[data-events]').textContent).toContain('interrupted')
    document.querySelector('[data-event-time]').value = '2000-01-01T10:00'
    document.querySelector('[data-event-form]').dispatchEvent(new Event('submit', { cancelable: true }))
    expect(api.createEvent).not.toHaveBeenCalled()
    document.querySelector('[data-event-time]').value = '2099-09-07T15:30'
    document.querySelector('[data-event-form]').dispatchEvent(new Event('submit', { cancelable: true }))
    await vi.advanceTimersByTimeAsync(0)
    expect(document.querySelector('[data-event-status]').textContent).toBe('Service unavailable')
    expect(document.querySelector('[data-event-create]').disabled).toBe(false)
    page.destroy()
    expect(vi.getTimerCount()).toBe(0)
  } finally { page.destroy(); vi.useRealTimers() }
})

it('posts only the selected due time through the authenticated event API', async () => {
  const { createAuditEmailApi } = await import('../src/api.js')
  const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'event' }) })
  const api = createAuditEmailApi({ fetchImpl })
  await api.createEvent('2099-09-07T15:30:00+08:00')
  expect(fetchImpl).toHaveBeenCalledWith('/api/audit-email/events', {
    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dueAt: '2099-09-07T15:30:00+08:00' })
  })
  await api.listEvents()
  expect(fetchImpl).toHaveBeenLastCalledWith('/api/audit-email/events', { method: 'GET', credentials: 'same-origin' })
})
