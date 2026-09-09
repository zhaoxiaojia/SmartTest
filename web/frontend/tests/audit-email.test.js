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

it('keeps polling after a transient event fetch failure and refreshes terminal run state', async () => {
  document.body.innerHTML = '<div id="page"></div>'
  const pending = { id: 'event-1', dueAt: '2099-09-07T15:30+08:00', state: 'pending', deliveries: {} }
  const completed = { ...pending, state: 'completed', runId: 'run-1', deliveries: {
    jira: { state: 'accepted' }, confluence: { state: 'accepted' }
  } }
  const api = {
    list: vi.fn(async () => ({ runs: [{ id: 'run-1', label: '2099-09-07T15:30:00+08:00', state: 'completed', source: 'one_time' }], total: 1 })),
    listEvents: vi.fn().mockResolvedValueOnce({ events: [pending] })
      .mockRejectedValueOnce(Error('temporary network failure'))
      .mockResolvedValueOnce({ events: [completed] }),
    get: vi.fn(async () => ({ id: 'run-1', state: 'completed', reports: {}, evidence: 'finished' })),
  }
  vi.useFakeTimers()
  const page = createAuditEmailPage({ root: document.querySelector('#page'), api })
  try {
    await page.start()
    await vi.advanceTimersByTimeAsync(1000)
    await vi.advanceTimersByTimeAsync(1000)
    expect(api.listEvents).toHaveBeenCalledTimes(3)
    expect(api.list).toHaveBeenCalledTimes(2)
    expect(api.get).toHaveBeenCalledWith('run-1')
    expect(document.querySelector('[data-evidence]').value).toBe('finished')
    expect(document.querySelector('[data-events]').textContent).toContain('已完成')
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

it('creates updates disables and deletes the persisted weekly schedule', async () => {
  document.body.innerHTML = '<div id="page"></div>'
  let schedule = null
  const api = {
    list: async () => ({ runs: [], total: 0 }), listEvents: async () => ({ events: [] }),
    getSchedule: vi.fn(async () => ({ schedule })),
    saveSchedule: vi.fn(async payload => ({ schedule: schedule = {
      id: 'weekly-coco', timezone: 'Asia/Shanghai', nextRunAt: payload.enabled ? '2026-09-11T15:00:00+08:00' : null,
      lastRunId: null, lastState: null, ...payload
    } })),
    deleteSchedule: vi.fn(async () => { schedule = null; return { deleted: true } })
  }
  const page = createAuditEmailPage({ root: document.querySelector('#page'), api })
  await page.start()
  expect(document.querySelector('[data-schedule-status]').textContent).toContain('尚未配置')
  expect(document.querySelector('[data-schedule-weekday]').value).toBe('4')
  expect(document.querySelector('[data-schedule-time]').value).toBe('15:00')

  document.querySelector('[data-schedule-form]').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
  await vi.waitFor(() => expect(api.saveSchedule).toHaveBeenCalledWith({ weekday: 4, time: '15:00', enabled: true }))
  expect(document.querySelector('[data-schedule-status]').textContent).toContain('2026')
  document.querySelector('[data-schedule-enabled]').checked = false
  document.querySelector('[data-schedule-form]').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
  await vi.waitFor(() => expect(api.saveSchedule).toHaveBeenLastCalledWith({ weekday: 4, time: '15:00', enabled: false }))
  document.querySelector('[data-schedule-delete]').click()
  await vi.waitFor(() => expect(api.deleteSchedule).toHaveBeenCalledTimes(1))
  expect(document.querySelector('[data-schedule-status]').textContent).toContain('尚未配置')
  page.destroy()
})

it('opens the latest scheduled result from the schedule card', async () => {
  document.body.innerHTML = '<div id="page"></div>'
  const api = {
    list: async () => ({ runs: [], total: 0 }), listEvents: async () => ({ events: [] }),
    getSchedule: async () => ({ schedule: { id: 'weekly-coco', weekday: 4, time: '15:00', enabled: true,
      timezone: 'Asia/Shanghai', nextRunAt: '2026-09-18T15:00:00+08:00', lastRunId: 'run-weekly', lastState: 'completed' } }),
    get: vi.fn(async () => ({ id: 'run-weekly', state: 'completed', reports: {}, evidence: 'scheduled' }))
  }
  const page = createAuditEmailPage({ root: document.querySelector('#page'), api })
  await page.start()
  document.querySelector('[data-schedule-view]').click()
  await vi.waitFor(() => expect(api.get).toHaveBeenCalledWith('run-weekly'))
  expect(document.querySelector('[data-evidence]').value).toBe('scheduled')
  page.destroy()
})

it('uses the weekly schedule CRUD API contract', async () => {
  const { createAuditEmailApi } = await import('../src/api.js')
  const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ schedule: null }) })
  const api = createAuditEmailApi({ fetchImpl })
  await api.getSchedule()
  await api.saveSchedule({ weekday: 4, time: '15:00', enabled: true })
  await api.deleteSchedule()
  expect(fetchImpl.mock.calls.map(call => [call[0], call[1].method])).toEqual([
    ['/api/audit-email/schedule', 'GET'], ['/api/audit-email/schedule', 'PUT'], ['/api/audit-email/schedule', 'DELETE']
  ])
})
