// @vitest-environment jsdom
import { beforeEach, expect, it, vi } from 'vitest'

import { createJiraWorkbench } from '../src/jira-workbench.js'


beforeEach(() => { document.body.innerHTML = '<main></main>' })

it('renders three columns, reuses dashboard scope, and keeps review in advanced area', async () => {
  const api = {
    getJiraReleaseIssues: vi.fn().mockResolvedValue({
      state: 'ready', selectedRelease: { projectId: 'P100', projectName: 'Orion', releaseName: 'Android 16' },
      facets: [], counts: { exact: 1, versionPending: 1 },
      issues: [{ key: 'SH-1', summary: 'Blocker', priority: 'P0', severity: 'Critical', status: 'Open',
        assignee: 'Alice', components: 'Video', softwareRelease: 'Android 16', fixVersions: '', updatedAt: '2026-09-04',
        releaseAssociation: 'exact' }],
      pagination: { page: 0, pageSize: 50, total: 1 }, sourceFreshness: {}, syncState: 'idle',
    }),
    getJiraReleaseIssue: vi.fn().mockResolvedValue({ key: 'SH-1', summary: 'Blocker', status: 'Open', priority: 'P0',
      projectId: 'P100', softwareRelease: 'Android 16', releaseAssociation: 'exact', associationReason: '版本字段一致', details: {} }),
    syncJiraReleaseIssues: vi.fn(), createJiraAudit: vi.fn(),
  }
  const page = createJiraWorkbench({
    root: document.querySelector('main'), api, snapshot: 'dashboard', projectId: 'P100',
  })

  await page.start()

  expect(api.getJiraReleaseIssues).toHaveBeenCalledWith(
    {}, { snapshot: 'dashboard', projectId: 'P100', page: 0, pageSize: 50 },
  )
  expect(document.querySelectorAll('.jira-workbench > *')).toHaveLength(3)
  expect(document.querySelector('[data-advanced-review] [data-start-audit]')).not.toBeNull()
  document.querySelector('[data-issue-row]').click()
  await vi.waitFor(() => expect(document.querySelector('[data-issue-detail]').textContent).toContain('版本字段一致'))
})

it('keeps cached issues visible and reports an invalid-credentials sync result', async () => {
  const cached = {
    state: 'ready', selectedRelease: null, facets: [], counts: { exact: 0, versionPending: 1 },
    issues: [{ key: 'SH-1', summary: 'Cached issue', priority: 'P1', severity: 'Major', status: 'Open',
      releaseAssociation: 'version_pending' }],
    pagination: { page: 0, pageSize: 50, total: 1 }, sourceFreshness: {}, syncState: 'idle',
  }
  const api = {
    getJiraReleaseIssues: vi.fn().mockResolvedValue(cached),
    syncJiraReleaseIssues: vi.fn().mockResolvedValue({ ...cached, syncState: 'invalid_credentials' }),
    createJiraAudit: vi.fn(),
  }
  const page = createJiraWorkbench({ root: document.querySelector('main'), api })
  await page.start()

  document.querySelector('[data-sync]').click()

  await vi.waitFor(() => expect(document.querySelector('[data-jira-feedback]').textContent)
    .toContain('credentials'))
  expect(document.querySelector('[data-issue-row]').textContent).toContain('Cached issue')
})
