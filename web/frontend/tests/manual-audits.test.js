// @vitest-environment jsdom
import { beforeEach, expect, it, vi } from 'vitest'

import { createJiraManualAudit } from '../src/manual-audits.js'
import { createPreferenceStore } from '../src/preference-store.js'

beforeEach(() => { document.body.innerHTML = '<div id="app"></div>' })

it('saves and restores the Jira query without starting a review', async () => {
  const saved = {}
  const preferencesApi = {
    get: async scope => ({ items: saved[scope] || {} }),
    put: async (scope, items) => { saved[scope] = { ...saved[scope], ...items } },
  }
  const api = { createJiraAudit: vi.fn() }
  const root = document.querySelector('#app')
  let page = createJiraManualAudit({ root, api })
  let store = createPreferenceStore({ root, api: preferencesApi, route: () => '/jira.html' })
  try {
    await store.start()
    const input = root.querySelector('[name="auditInput"]')
    input.value = 'project = SH ORDER BY updated DESC'
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await vi.waitFor(() => expect(saved['jira.html']?.auditInput).toBe(input.value))
    store.destroy()
    page.destroy()
    page = createJiraManualAudit({ root, api })
    store = createPreferenceStore({ root, api: preferencesApi, route: () => '/jira.html' })
    await store.start()
    expect(root.querySelector('[name="auditInput"]').value).toBe('project = SH ORDER BY updated DESC')
    expect(api.createJiraAudit).not.toHaveBeenCalled()
    expect(root.querySelector('[data-audit-download]').disabled).toBe(true)
  } finally {
    store.destroy()
    page.destroy()
  }
})

it('discards old-session Jira creation before polling or enabling download', async () => {
  let release
  const api = { createJiraAudit: () => new Promise(resolve => { release = resolve }), getJiraAudit: vi.fn() }
  const page = createJiraManualAudit({ root: document.querySelector('#app'), api })
  document.querySelector('[name="auditInput"]').value = 'project=SH'
  document.querySelector('[data-start-audit]').click()
  page.destroy()
  release({ auditId: 'old', status: 'queued' })
  await Promise.resolve()
  expect(api.getJiraAudit).not.toHaveBeenCalled()
  expect(document.querySelector('[data-audit-download]').disabled).toBe(true)
})

it('runs one Jira review, shows shared progress, and enables its generated download', async () => {
  const api = {
    createJiraAudit: vi.fn().mockResolvedValue({ auditId: 'a1', status: 'queued' }),
    getJiraAudit: vi.fn()
      .mockResolvedValueOnce({ auditId: 'a1', status: 'running', stage: 'fetching_issues', progress: { processed: 0, total: 0 } })
      .mockResolvedValueOnce({ auditId: 'a1', status: 'running', stage: 'rule_auditing', progress: { processed: 1, total: 2 } })
      .mockResolvedValueOnce({ auditId: 'a1', status: 'completed', stage: 'exporting', progress: { processed: 2, total: 2 } }),
    exportJiraAudit: vi.fn().mockResolvedValue({ download: { id: 'd1', fileName: 'jira.xlsx' } }),
    cancelJiraAudit: vi.fn(),
    downloadUrl: id => '/api/downloads/' + id,
  }
  const navigate = vi.fn()
  createJiraManualAudit({
    root: document.querySelector('#app'), api, pollDelay: () => Promise.resolve(),
    downloadNavigate: navigate,
  })
  const workspace = document.querySelector('[data-jira-review]')
  const inputCard = document.querySelector('[data-audit-input-card]')
  const controls = document.querySelector('[data-audit-controls]')
  expect(workspace.querySelector('h1').textContent).toBe('Jira Review')
  expect(workspace.textContent).not.toContain('Results')
  const form = inputCard.querySelector('[data-audit-form]')
  const queryRow = form.querySelector(':scope > .jira-audit-query.jira-audit-full-width')
  expect(queryRow).not.toBeNull()
  expect(queryRow.querySelector('textarea[name="auditInput"]')).not.toBeNull()
  expect(controls.parentElement).toBe(form)
  expect([...controls.children]).toEqual(expect.arrayContaining([
    document.querySelector('[data-start-audit]'),
    document.querySelector('[data-cancel-audit]'),
    document.querySelector('[data-audit-download]'),
  ]))
  expect(document.querySelector('[data-confirm-audit]')).toBeNull()
  expect(document.querySelector('[name="resultFilter"]')).toBeNull()
  expect(document.querySelector('[data-audit-download]').textContent).toBe('Download')
  expect(document.querySelector('[data-audit-download]').disabled).toBe(true)

  document.querySelector('[name="auditInput"]').value = 'project=SH'
  document.querySelector('[data-start-audit]').click()
  await vi.waitFor(() => expect(document.querySelector('[data-audit-progress]').dataset.state).toBe('success'))
  expect(api.createJiraAudit).toHaveBeenCalledOnce()
  expect(api.getJiraAudit).toHaveBeenCalledTimes(3)
  expect(document.querySelector('[data-audit-download]').disabled).toBe(false)
  document.querySelector('[data-audit-download]').click()
  await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith('/api/downloads/d1'))
  expect(api.exportJiraAudit).toHaveBeenCalledOnce()
})

it('shows task creation failure and restores Jira controls', async () => {
  const api = {
    createJiraAudit: vi.fn().mockRejectedValue({ status: 422 }),
    downloadUrl: id => '/api/downloads/' + id,
  }
  createJiraManualAudit({ root: document.querySelector('#app'), api })
  document.querySelector('[name="auditInput"]').value = 'bad input'
  document.querySelector('[data-start-audit]').click()

  await vi.waitFor(() => expect(document.querySelector('[data-audit-progress]').textContent).toContain('invalid'))
  expect(document.querySelector('[data-start-audit]').disabled).toBe(false)
  expect(document.querySelector('[data-cancel-audit]').disabled).toBe(true)
  expect(document.querySelector('[data-audit-download]').disabled).toBe(true)
})

it.each(['failed', 'cancelled'])('keeps Download disabled when the Jira task is %s', async status => {
  const api = {
    createJiraAudit: vi.fn().mockResolvedValue({ auditId: 'a1', status: 'queued' }),
    getJiraAudit: vi.fn().mockResolvedValue({
      auditId: 'a1', status, stage: 'rule_auditing',
      progress: { processed: 1, total: 2 }, errorCode: status === 'failed' ? 'audit_failed' : 'cancelled',
    }),
    exportJiraAudit: vi.fn(),
    cancelJiraAudit: vi.fn(),
    downloadUrl: id => '/api/downloads/' + id,
  }
  createJiraManualAudit({ root: document.querySelector('#app'), api, pollDelay: () => Promise.resolve() })
  document.querySelector('[name="auditInput"]').value = 'project=SH'
  document.querySelector('[data-start-audit]').click()

  await vi.waitFor(() => expect(document.querySelector('[data-audit-progress]').dataset.state).toBe(status))
  expect(document.querySelector('[data-audit-download]').disabled).toBe(true)
  expect(api.exportJiraAudit).not.toHaveBeenCalled()
})
