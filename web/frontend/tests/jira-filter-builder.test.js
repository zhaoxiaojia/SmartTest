// @vitest-environment jsdom
import { beforeEach, expect, it, vi } from 'vitest'
import { createJiraFilterBuilder } from '../src/jira-filter-builder.js'

beforeEach(() => { document.body.innerHTML = '<div id="root"></div>'; localStorage.clear() })

function api() {
  return {
    getJiraAnalyticsState: vi.fn().mockResolvedValue({ activeJql: 'status = "Open"', taskId: '' }),
    getJiraAnalyticsFields: vi.fn().mockResolvedValue({ fixed: [
      { id: 'project', name: 'Project', control: 'multi', queryable: true },
      { id: 'issuetype', name: 'Type', control: 'multi', queryable: true },
      { id: 'status', name: 'Status', control: 'multi', queryable: true },
      { id: 'assignee', name: 'Assignee', control: 'user', queryable: true },
      { id: 'resolution', name: 'Resolution', control: 'multi', queryable: true },
    ], more: [
      { id: 'resolution', name: 'Resolution', control: 'multi', queryable: true, options: ['Done'] },
      { id: 'cascade', name: 'Cascade', control: 'advanced', queryable: false, options: [] },
    ] }),
    getJiraAnalyticsSavedFilters: vi.fn().mockResolvedValue([{ id: '7', name: 'Mine' }]),
    getJiraAnalyticsSavedFilter: vi.fn().mockResolvedValue({ id: '7', name: 'Mine', jql: 'project = SH' }),
    getJiraAnalyticsSuggestions: vi.fn((field, query) => Promise.resolve([
      { value: `${field}:value`, displayName: query ? `${field}:${query}` : `${field}:display` },
    ])),
    validateJiraAnalytics: vi.fn().mockResolvedValue({ valid: true, errors: [], jql: 'project IN ("SH")' }),
    searchJiraAnalytics: vi.fn().mockResolvedValue({ validation: { valid: true, errors: [] }, taskId: 'task-1', state: {} }),
    getJiraAnalyticsTask: vi.fn().mockResolvedValue({ state: 'completed', progress: { processed: 1, total: 1 }, query: { activeJql: 'project IN ("SH")' } }),
    cancelJiraAnalyticsTask: vi.fn(),
  }
}

it('loads each fixed dropdown from Jira suggestions on open and renders response values verbatim', async () => {
  const client = api(); const component = createJiraFilterBuilder({ root: document.querySelector('#root'), api: client, account: 'alice' })
  await component.start()

  expect(document.querySelector('[name="project"]').classList.contains('d-none')).toBe(true)
  expect(document.querySelector('[data-jira-field="project"] .multi-select__summary').textContent).toBe('Project: All')
  expect(document.querySelector('[data-jira-field="issuetype"] .multi-select__summary').textContent).toBe('Type: All')
  expect(document.querySelector('[data-jira-field="status"] .multi-select__summary').textContent).toBe('Status: All')
  expect(document.querySelector('[data-jira-field="assignee"] .multi-select__summary').textContent).toBe('Assignee: All')
  expect(document.querySelector('[data-jira-field="resolution"] .multi-select__summary').textContent).toBe('Resolution: All')
  expect(document.querySelector('[data-jira-field="resolution"]').parentElement.matches('[data-conditions]')).toBe(true)
  expect(document.querySelector('[data-search]').closest('.jira-native-query-row')).not.toBeNull()
  expect(document.querySelector('[data-advanced]').closest('.jira-native-query-row')).not.toBeNull()

  const project = document.querySelector('[data-jira-field="project"]')
  project.querySelector('.multi-select__control').click()
  await vi.waitFor(() => expect(client.getJiraAnalyticsSuggestions).toHaveBeenCalledWith('project', ''))
  expect(project.querySelector('.multi-select__dropdown').getAttribute('aria-hidden')).toBe('false')
  const option = project.querySelector('.multi-select__option input')
  expect(option.value).toBe('project:value')
  expect(option.nextElementSibling.textContent).toBe('project:display')
  const search = project.querySelector('input[type="search"]'); search.value = 'tv'; search.dispatchEvent(new Event('input'))
  await vi.waitFor(() => expect(client.getJiraAnalyticsSuggestions).toHaveBeenCalledWith('project', 'tv'))
  expect(project.querySelector('.multi-select__option span').textContent).toBe('project:tv')
  const searchedOption = project.querySelector('.multi-select__option input')
  searchedOption.checked = true; searchedOption.dispatchEvent(new Event('change', { bubbles: true }))
  document.querySelector('[data-search]').click()
  await vi.waitFor(() => expect(client.searchJiraAnalytics).toHaveBeenCalledWith(expect.objectContaining({
    mode: 'basic', basic: expect.objectContaining({ project: ['project:value'] }),
  })))
})

it('uses the Jira compact text layout and reveals Advanced before JQL generation finishes', async () => {
  let finishValidation
  const client = api()
  client.validateJiraAnalytics.mockReturnValueOnce(new Promise(resolve => { finishValidation = resolve }))
  const component = createJiraFilterBuilder({ root: document.querySelector('#root'), api: client, account: 'alice' })
  await component.start()

  const contains = document.querySelector('[name="containsText"]')
  expect(contains.placeholder).toBe('Contains text')
  expect(contains.closest('label')).toBeNull()
  expect(document.querySelector('input[name="jql"]')).not.toBeNull()
  expect(document.querySelector('textarea[name="jql"]')).toBeNull()

  document.querySelector('[data-advanced]').click()
  expect(document.querySelector('[data-advanced-panel]').hidden).toBe(false)
  expect(document.querySelector('[data-basic-panel]').hidden).toBe(true)
  finishValidation({ valid: true, errors: [], jql: 'project IN ("SH")' })
  await vi.waitFor(() => expect(document.querySelector('[name="jql"]').value).toBe('project IN ("SH")'))
})

it('switches builder jql back losslessly until advanced text is edited', async () => {
  const client = api(); const component = createJiraFilterBuilder({ root: document.querySelector('#root'), api: client, account: 'alice' })
  await component.start()
  document.querySelector('[name="project"]').value = 'SH'
  document.querySelector('[data-advanced]').click()
  await vi.waitFor(() => expect(document.querySelector('[name="jql"]').value).toBe('project IN ("SH")'))
  document.querySelector('[data-basic]').click()
  expect(document.querySelector('[data-mode]').textContent).toContain('Basic')
  document.querySelector('[data-advanced]').click(); await Promise.resolve()
  const jql = document.querySelector('[name="jql"]'); jql.value += ' OR status = Open'; jql.dispatchEvent(new Event('input'))
  document.querySelector('[data-basic]').click()
  expect(document.querySelector('[data-feedback]').textContent).toContain('cannot be converted')
  expect(jql.value).toContain(' OR status')
})

it('loads saved filter as advanced draft without searching and Search starts task', async () => {
  const client = api(); const component = createJiraFilterBuilder({ root: document.querySelector('#root'), api: client, account: 'alice' })
  await component.start()
  const saved = document.querySelector('[name="savedFilter"]'); saved.value = '7'; saved.dispatchEvent(new Event('change'))
  await vi.waitFor(() => expect(document.querySelector('[name="jql"]').value).toBe('project = SH'))
  expect(client.searchJiraAnalytics).not.toHaveBeenCalled()
  document.querySelector('[data-search]').click()
  await vi.waitFor(() => expect(client.searchJiraAnalytics).toHaveBeenCalledWith({ mode: 'advanced', jql: 'project = SH', sourceFilterId: '7' }))
  await vi.waitFor(() => expect(document.querySelector('[data-progress]').textContent).toContain('completed'))
})

it('More is searchable, anchored, and contains only fields returned by Jira', async () => {
  const client = api(); const component = createJiraFilterBuilder({ root: document.querySelector('#root'), api: client, account: 'alice' })
  await component.start()
  document.querySelector('[data-more]').click()
  const menu = document.querySelector('[data-more-menu]')
  expect(menu.parentElement.matches('.jira-more-anchor')).toBe(true)
  expect(menu.querySelector('[data-more-search]')).not.toBeNull()
  expect(document.querySelector('[data-add-field="resolution"]').getAttribute('aria-label')).toContain('Resolution')
  expect(document.querySelector('[data-add-field="cascade"]').disabled).toBe(true)
  expect(menu.textContent).not.toContain('Reporter')
})

it('loads More field values from Jira suggestions when its condition opens', async () => {
  const client = api(); const component = createJiraFilterBuilder({ root: document.querySelector('#root'), api: client, account: 'alice' })
  await component.start(); document.querySelector('[data-more]').click()
  document.querySelector('[data-add-field="resolution"]').click()
  const condition = document.querySelector('[data-condition="resolution"]')
  condition.querySelector('.multi-select__control').click()
  await vi.waitFor(() => expect(client.getJiraAnalyticsSuggestions).toHaveBeenCalledWith('resolution', ''))
  expect(condition.querySelector('.multi-select__option span').textContent).toBe('resolution:display')
})

it('destroy removes account draft so another account never flashes it', async () => {
  const root = document.querySelector('#root'); const first = createJiraFilterBuilder({ root, api: api(), account: 'alice' })
  await first.start(); document.querySelector('[name="containsText"]').value = 'secret'; first.destroy()
  root.replaceChildren()
  const second = createJiraFilterBuilder({ root, api: api(), account: 'bob' }); await second.start()
  expect(document.querySelector('[name="containsText"]').value).toBe('')
})

it('keeps the loaded draft visible when its Saved Filter source disappears', async () => {
  const client = api(); client.getJiraAnalyticsSavedFilter.mockResolvedValueOnce({ id: '7', jql: 'project = SH' }).mockRejectedValueOnce(new Error('gone'))
  const component = createJiraFilterBuilder({ root: document.querySelector('#root'), api: client, account: 'alice' }); await component.start()
  const saved = document.querySelector('[name="savedFilter"]'); saved.value = '7'; saved.dispatchEvent(new Event('change'))
  await vi.waitFor(() => expect(document.querySelector('[name="jql"]').value).toBe('project = SH'))
  saved.dispatchEvent(new Event('change'))
  await vi.waitFor(() => expect(document.querySelector('[data-feedback]').textContent).toContain('no longer available'))
  expect(document.querySelector('[name="jql"]').value).toBe('project = SH')
})

it('keeps advanced draft when Search transport fails', async () => {
  const client = api(); client.searchJiraAnalytics.mockRejectedValue(new Error('offline'))
  const component = createJiraFilterBuilder({ root: document.querySelector('#root'), api: client, account: 'alice' }); await component.start()
  document.querySelector('[data-advanced]').click(); await vi.waitFor(() => expect(document.querySelector('[name="jql"]').value).not.toBe(''))
  document.querySelector('[data-search]').click()
  await vi.waitFor(() => expect(document.querySelector('[data-feedback]').textContent).toContain('failed'))
  expect(document.querySelector('[name="jql"]').value).toBe('project IN ("SH")')
})
