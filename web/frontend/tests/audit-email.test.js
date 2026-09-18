// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import { createAuditEmailPage } from '../src/audit-email.js'

it('offers only immediate weekly review and displays both completed reports', async () => {
  document.body.innerHTML = '<div id="page"></div>'
  const detail = { id: 'run-1', state: 'completed', evidence: 'email=recorded', reports: {
    jira: { html: '<p>jira</p>', attachments: [] }, confluence: { html: '<p>confluence</p>', attachments: [] }
  } }
  const api = { list: vi.fn(async () => ({ runs: [], total: 0 })), trigger: vi.fn(async () => detail), get: vi.fn() }
  const page = createAuditEmailPage({ root: document.querySelector('#page'), api })
  await page.start()
  expect(document.body.textContent).toContain('每周五北京时间 18:00')
  expect(document.body.textContent).toContain('fae.qa@amlogic.com')
  expect(document.body.textContent).not.toContain('ping.xiong@amlogic.com')
  expect(document.querySelector('[data-event-form]')).toBeNull()
  expect(document.querySelector('[data-schedule-form]')).toBeNull()
  document.querySelector('[data-trigger]').click()
  await vi.waitFor(() => expect(api.trigger).toHaveBeenCalledTimes(1))
  await vi.waitFor(() => expect(document.querySelector('[data-evidence]').value).toBe('email=recorded'))
  expect(document.querySelector('[title="Jira 报告预览"]').srcdoc).toBe('<p>jira</p>')
  page.destroy()
})

it('polls immediate execution to its saved terminal result', async () => {
  document.body.innerHTML = '<div id="page"></div>'
  const complete = { id: 'run-2', state: 'completed', evidence: 'smtp_accepted', reports: { jira: {}, confluence: {} } }
  const api = { list: async () => ({ runs: [], total: 0 }), trigger: async () => ({ ...complete, state: 'running' }), get: vi.fn(async () => complete) }
  const page = createAuditEmailPage({ root: document.querySelector('#page'), api, pollDelay: async () => {} })
  await page.start(); document.querySelector('[data-trigger]').click()
  await vi.waitFor(() => expect(api.get).toHaveBeenCalledWith('run-2'))
  expect(document.querySelector('[data-evidence]').value).toBe('smtp_accepted')
  page.destroy()
})

it('audit email api exposes history and immediate trigger only', async () => {
  const { createAuditEmailApi } = await import('../src/api.js')
  const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
  const api = createAuditEmailApi({ fetchImpl })
  expect(api.listEvents).toBeUndefined(); expect(api.getSchedule).toBeUndefined()
  await api.trigger(); await api.list(4)
  expect(fetchImpl.mock.calls.map(call => [call[0], call[1].method])).toEqual([
    ['/api/audit-email/runs', 'POST'], ['/api/audit-email/runs?offset=4', 'GET']
  ])
})
