// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createTools } from '../src/tools.js'

describe('Tools page', () => {
  beforeEach(() => { document.body.innerHTML = '<main></main>' })

  it('owns both singleton filters, both reviews, and the audit email entry', async () => {
    const api = {
      getProjectFacts: vi.fn().mockResolvedValue({ state: 'ready', facets: [
        { key: 'project id', label: 'Project ID', options: ['P100'] },
        { key: 'support mode', label: 'Support Mode', options: ['A', 'B'] },
      ], projects: [], ownerHierarchy: [], querySnapshot: {
        filters: { 'project id': ['P100'], 'support mode': ['B'] }, search: 'weekly', revision: 2,
      } }),
      getProjectFactsStatus: vi.fn(), cancelProjectSync: vi.fn(),
      getJiraFilterSnapshot: vi.fn().mockResolvedValue({ facets: [
        { key: 'project', label: 'Project', options: ['SH'] },
        { key: 'type', label: 'Type', options: ['Bug'] },
        { key: 'status', label: 'Status', options: ['Open'] },
        { key: 'currentUser', label: 'Current User', options: ['Current User'] },
        { key: 'resolution', label: 'Resolution', options: ['Unresolved'] },
      ], snapshot: null }),
      applyJiraFilterSnapshot: vi.fn(), resetJiraFilterSnapshot: vi.fn(),
    }
    const page = createTools({ root: document.querySelector('main'), api })
    await page.start()

    expect([...document.querySelectorAll('[data-jira-filter] select')].map(item => item.name))
      .toEqual(['project', 'type', 'status', 'currentUser', 'resolution'])
    expect(document.querySelector('[data-jira-filter] textarea[name="jql"]')).not.toBeNull()
    expect(document.querySelector('[data-jira-review]')).not.toBeNull()
    expect(document.querySelector('[data-confluence-review]')).not.toBeNull()
    expect(document.querySelector('[name="search"]').value).toBe('weekly')
    expect(document.querySelector('[name="field.project id"] option[value="P100"]').selected).toBe(true)
    expect(document.querySelector('[name="field.support mode"]')).toBeNull()
    expect(document.querySelector('a[href="/audit-email.html"]')).not.toBeNull()
  })
})
