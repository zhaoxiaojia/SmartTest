// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createProjects } from '../src/projects.js'

const productSpaces = [
  { value: 'DOPL', label: 'China Operator Business' },
  { value: 'SDPL', label: 'Smart Device Business' },
  { value: 'TV', label: 'TV Business' },
  { value: 'OOPL', label: 'Global Operator & STB Business' },
]

const payload = {
  state: 'partial_success',
  productSpaces,
  counts: { stale: 1, failed: 0, inactive: 2 }, discrepancies: ['Unexpected Owner'],
  facets: [
    { key: '__product_space__', label: 'Product Space', labels: ['Product Space'], options: [{ value: 'DOPL', label: 'China Operator Business' }, { value: 'TV', label: 'TV Business' }] },
    { key: 'support mode', label: 'Support Mode', labels: ['Support Mode'], options: ['A', 'B'] },
    { key: 'unexpected owner', label: 'Unexpected Owner', labels: ['Unexpected Owner'], options: ['Alice'] }
  ],
  projects: [{ project_id: 'A-1', name: 'Apollo', space_key: 'DOPL', status: 'stale', fields: { 'support mode': 'B' },
    roles: { 'Major FAE QA': [{ name: 'Coco', identity: 'u-1' }] } }],
  ownerHierarchy: [{ role: 'Major FAE QA', people: [{ name: 'Coco', identity: 'u-1', projects: [
    { project_id: 'A-1', name: 'Apollo', space_key: 'DOPL', status: 'stale', fields: { 'support mode': 'B' } }
  ] }] }, { role: 'FAE QA', people: [] }, { role: 'QA Reviewer', people: [] }]
}
const fixedFacets = [
  ['__product_space__', 'Product Space'], ['page', 'Page'], ['date of commercial approval', 'Date of Commercial approval'],
  ['project id', 'Project ID'], ['odm', 'ODM'], ['oem/operator', 'OEM/Operator'], ['key part number', 'Key Part Number'],
  ['project status', 'Project Status'], ['current stage', 'Current Stage'], ['major pm', 'Major PM'], ['project owner', 'Project Owner'],
  ['support mode', 'Support Mode'], ['launch os', 'Launch OS'], ['date of kick off', 'Date of Kick Off'],
  ['planned closure', 'planned closure'], ['actual closure', 'actual closure'], ['mp time', 'MP Time'], ['launch time', 'Launch Time'],
  ['next target', 'Next Target'], ['next target date', 'Next Target Date'], ['sum', 'Sum']
].map(([key, label]) => ({ key, label, labels: [label], options: [] }))

describe('Projects', () => {
  beforeEach(() => { document.body.innerHTML = '<div id="app"></div>'; localStorage.clear(); sessionStorage.clear() })

  it('renders the previous account display before snapshot calibration completes', async () => {
    const first = createProjects({ root: document.querySelector('#app'), account: 'alice',
      api: { getProjectFacts: vi.fn().mockResolvedValue(payload) } })
    await first.start(); first.destroy()
    document.body.innerHTML = '<div id="app"></div>'
    let finishSnapshot
    const calibrated = { ...payload, projects: [], ownerHierarchy: [] }
    const second = createProjects({ root: document.querySelector('#app'), account: 'alice',
      api: { getProjectFacts: vi.fn(() => new Promise(resolve => { finishSnapshot = resolve })) } })

    const starting = second.start()
    expect(document.querySelector('[data-projects]').textContent).toContain('Apollo')
    finishSnapshot(calibrated)
    await starting
    expect(document.querySelectorAll('.project-card')).toHaveLength(0)
  })

  it('isolates disposable display state by account and clears it on identity change', async () => {
    const alice = createProjects({ root: document.querySelector('#app'), account: 'alice',
      api: { getProjectFacts: vi.fn().mockResolvedValue(payload) } })
    await alice.start()
    alice.destroy()
    document.body.innerHTML = '<div id="app"></div>'
    const bob = createProjects({ root: document.querySelector('#app'), account: 'bob',
      api: { getProjectFacts: vi.fn(() => new Promise(() => {})) } })

    void bob.start()
    expect(document.querySelector('[data-projects]').textContent).not.toContain('Apollo')
    expect(document.querySelector('[role="status"]').textContent).toContain('Loading')
  })

  it('keeps the previous display when snapshot calibration fails', async () => {
    const first = createProjects({ root: document.querySelector('#app'), account: 'alice',
      api: { getProjectFacts: vi.fn().mockResolvedValue(payload) } })
    await first.start(); first.destroy()
    document.body.innerHTML = '<div id="app"></div>'
    const second = createProjects({ root: document.querySelector('#app'), account: 'alice',
      api: { getProjectFacts: vi.fn().mockRejectedValue(new Error('offline')) } })

    await second.start()
    expect(document.querySelector('[data-projects]').textContent).toContain('Apollo')
    expect(document.querySelector('[role="status"]').textContent).toContain('unavailable')
  })

  it('keeps the page and review dates when Reset cannot restore the catalog scope', async () => {
    let failReset
    const api = { getProjectFacts: vi.fn().mockResolvedValueOnce({ ...payload, state: 'ready' })
      .mockImplementationOnce(() => new Promise((_resolve, reject) => { failReset = reject })) }
    const page = createProjects({ root: document.querySelector('#app'), api })
    await page.start()
    const form = document.querySelector('form'), select = form.elements['field.__product_space__']
    select.value = 'TV'
    form.elements.search.value = 'local edit'
    form.elements.reviewStartDate.value = '2026-08-17'
    form.elements.reviewEndDate.value = '2026-08-24'
    const review = form.querySelector('[data-audit]')
    form.querySelector('[data-reset]').click()
    await vi.waitFor(() => expect(failReset).toBeTypeOf('function'))
    failReset(new Error('offline'))
    await vi.waitFor(() => expect(document.querySelector('[role="status"]').textContent).toContain('unavailable'))
    expect(document.querySelector('form')).toBe(form)
    expect(form.elements['field.__product_space__'].value).toBe('')
    expect(form.elements.search.value).toBe('')
    expect(form.elements.reviewStartDate.value).toBe('2026-08-17')
    expect(form.elements.reviewEndDate.value).toBe('2026-08-24')
    expect(form.querySelector('[data-audit]')).toBe(review)
    expect(document.querySelector('[role="status"]').textContent).toContain('unavailable')
    page.destroy()
  })

  it('renders the persisted session snapshot on entry without starting remote work', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue({ ...payload, state: 'ready' }) }
    const page = createProjects({ root: document.querySelector('#app'), api, pollDelay: () => new Promise(() => {}) })
    await page.start()
    expect(api.getProjectFacts).toHaveBeenCalledOnce()
    expect(api.getProjectFacts.mock.calls[0]).toEqual([{ fields: {}, search: '' }, { details: false, snapshot: true }])
    expect(document.querySelector('[data-projects]').textContent).toContain('Apollo')
    expect(document.querySelector('[name="field.__product_space__"]').disabled).toBe(false)
    page.destroy()
  })

  it('renders dynamic facets and project results without report or download UI', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.body.textContent).toContain('Unexpected Owner')
    expect(document.body.textContent).toContain('Product Space')
    expect(document.body.textContent).toContain('Apollo')
    expect(document.body.textContent).toContain('Major FAE QA')
    expect(document.body.textContent).toContain('Coco')
    expect(document.body.textContent).toContain('Some project facts are stale or failed')
    expect(document.querySelector('[name="reportType"]')).toBeNull()
    expect(document.querySelector('.report-directory')).toBeNull()
    expect(document.querySelector('[data-download]')).toBeNull()
  })

  it('keeps four full-name product-space groups and preserves unique project order within each waterfall', async () => {
    const grouped = {
      ...payload,
      state: 'ready',
      facets: [
        { key: '__product_space__', label: 'Product Space', options: productSpaces },
      ],
      projects: [
        { identity: 'p-first', project_id: 'P-1', name: 'First China Project', space_key: 'DOPL', status: 'ACTIVE', stage: 'Validation', roles: { 'Major FAE QA': [{ name: 'Coco' }, { name: 'Bob' }] }, fields: { tags: ['one', 'two'] } },
        { identity: 'p-tv', project_id: 'P-2', name: 'TV Project', space_key: 'TV', status: 'ACTIVE', stage: 'Development', support_mode: 'A', customer_summary: 'Customer B', roles: { 'FAE QA': [{ name: 'Alice' }] }, fields: { odm: 'ODM B' } },
        { identity: 'p-second', project_id: 'P-3', name: 'Second China Project', space_key: 'DOPL', stage: 'Pilot', roles: {} },
        { identity: 'p-none', project_id: 'P-4', name: 'No Owner Project', space_key: 'SDPL', stage: '', roles: {} },
        { identity: 'p-first', project_id: 'P-1', name: 'Duplicate First Project', space_key: 'DOPL', stage: 'Development', roles: {} },
      ],
      ownerHierarchy: [],
    }
    const api = { getProjectFacts: vi.fn().mockResolvedValue(grouped) }
    await createProjects({ root: document.querySelector('#app'), api }).start()

    const groups = [...document.querySelectorAll('[data-product-space-group]')]
    expect(groups.map(group => group.querySelector('summary strong').textContent)).toEqual([
      'China Operator Business', 'Smart Device Business', 'TV Business', 'Global Operator & STB Business',
    ])
    expect(groups.every(group => group.open)).toBe(true)
    expect(groups.map(group => group.querySelector('[data-product-count]').textContent)).toEqual(['2', '1', '1', '0'])
    expect([...groups[0].querySelectorAll('.project-card')].map(card => card.dataset.projectId)).toEqual(['p-first', 'p-second'])
    expect(document.querySelectorAll('[data-project-id="p-first"]')).toHaveLength(1)
    expect(document.querySelector('[data-project-id="p-none"]').textContent).toContain('No Owner Project')
    expect(document.querySelector('[data-project-id="p-first"]').textContent).toContain('Coco, Bob')
    expect(document.querySelector('[data-project-id="p-first"]').textContent).toContain('one, two')
    expect(document.querySelector('[data-project-id="p-first"]').textContent).toContain('Validation')
    expect(groups.every(group => group.querySelector('[data-product-grid]'))).toBe(true)
    expect([...document.querySelectorAll('.project-card-badges .badge')].map(item => item.textContent))
      .not.toEqual(expect.arrayContaining(['DOPL', 'SDPL', 'TV', 'OOPL']))
  })

  it('renders the persisted snapshot while preferences restore unapplied controls', async () => {
    let releasePreferences
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    const waitForPreferences = vi.fn(() => new Promise(resolve => {
      releasePreferences = () => {
        document.querySelector('[name="field.__product_space__"] option').selected = true
        resolve()
      }
    }))
    const started = createProjects({
      root: document.querySelector('#app'), api, waitForPreferences
    }).start()

    await vi.waitFor(() => expect(releasePreferences).toBeTypeOf('function'))
    expect(document.querySelector('[data-projects]').textContent).toContain('Apollo')
    releasePreferences()
    await started

    expect(api.getProjectFacts).toHaveBeenCalledOnce()
    expect([...document.querySelector('[name="field.__product_space__"]').selectedOptions].map(option => option.value)).toEqual(['DOPL'])
    expect(document.querySelectorAll('.project-card')).toHaveLength(1)
  })

  it('keeps project controls separate from the Weekly Review controls', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    expect([...document.querySelector('.filter-actions').querySelectorAll('button')].map(button => button.textContent)).toEqual([
      'Apply Filters', 'Cancel Sync', 'Reset'
    ])
    expect(document.querySelector('.weekly-review [data-audit]').textContent).toBe('Review Filters')
  })

  it('keeps matched projects visible when responsibility data is unavailable', async () => {
    const ownerless = { ...payload, projects: [{
      identity: 'DOPL:A-1', project_id: 'A-1', name: 'Apollo', space_key: 'DOPL',
      fields: { 'current stage': '2 IN DEVELOPMENT' }, roles: {}, responsibility_unavailable: true
    }], ownerHierarchy: [{ role: 'Major FAE QA', people: [] }, { role: 'FAE QA', people: [] }, { role: 'QA Reviewer', people: [] }] }
    const api = { getProjectFacts: vi.fn().mockResolvedValue(ownerless) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.querySelector('[data-count]').textContent).toBe('1 projects')
    expect(document.querySelector('[data-projects]').textContent).toContain('Apollo')
    expect(document.body.textContent).toContain('Project / Person / Field Search')
  })

  it('renders identity-free metrics and project cards without the old owner accordion', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    expect([...document.querySelectorAll('[data-metric] strong')].map(item => item.textContent)).toEqual(['1', '1', '1', '1', '1.0'])
    expect(document.querySelectorAll('details.owner-role, details.owner-person').length).toBe(0)
    expect(document.body.textContent).not.toContain('u-1')
    expect(document.querySelector('.project-card').textContent).toContain('Apollo')
  })

  it('shows canonical accessible projects separately from filtered matched projects', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue({ ...payload, accessibleProjectCount: 651 }) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    const metrics = Object.fromEntries([...document.querySelectorAll('[data-metric]')].map(card => [
      card.querySelector('span').textContent, card.querySelector('strong').textContent
    ]))
    expect(metrics['Accessible projects']).toBe('651')
    expect(metrics['Matched projects']).toBe('1')
    expect(document.querySelector('.summary-definition')).toBeNull()
    expect(document.body.textContent).not.toContain('Metric definition')
  })

  it('builds a sorted horizontal workload chart and hides identity-only names', async () => {
    const chartFactory = vi.fn(() => ({ destroy: vi.fn() }))
    const identityOnly = { ...payload, ownerHierarchy: [{ role: 'FAE QA', people: [
      { name: '2c93-user-key', identity: '2c93-user-key', projects: [{ name: 'Beta', space_key: 'TV' }] },
      { name: 'Alice', identity: 'alice-key', projects: [{ name: 'One', space_key: 'DOPL' }, { name: 'Two', space_key: 'TV' }] }
    ] }] }
    const api = { getProjectFacts: vi.fn().mockResolvedValue(identityOnly) }
    await createProjects({ root: document.querySelector('#app'), api, chartFactory }).start()
    const config = chartFactory.mock.calls[0][1]
    expect(config.options.indexAxis).toBe('y')
    expect(config.data.labels).toEqual(['Alice', 'Unknown member'])
    expect(config.data.datasets[0].data).toEqual([2, 1])
    expect(document.body.textContent).not.toContain('2c93-user-key')
  })

  it('grows the workload chart surface for a long people list inside its bounded viewport', async () => {
    const people = Array.from({ length: 20 }, (_, index) => ({
      name: `Member ${index + 1}`, identity: `member-${index + 1}`,
      projects: Array.from({ length: index % 3 + 1 }, (__, projectIndex) => ({ name: `Project ${index}-${projectIndex}`, space_key: 'TV' }))
    }))
    const api = { getProjectFacts: vi.fn().mockResolvedValue({ ...payload, ownerHierarchy: [{ role: 'FAE QA', people }] }) }
    const chartFactory = vi.fn(() => ({ destroy: vi.fn() }))
    await createProjects({ root: document.querySelector('#app'), api, chartFactory }).start()
    const viewport = document.querySelector('.workload-chart-scroll')
    const surface = viewport.querySelector('.workload-chart-surface')
    expect(Number.parseFloat(getComputedStyle(surface).height)).toBeGreaterThan(600)
    expect(surface.parentElement).toBe(viewport)
  })

  it('keeps seven common filters and exposes optional filters to the common preference region', async () => {
    const complete = { ...payload, facets: [
      { key: '__product_space__', label: 'Product Space', options: ['DOPL'] },
      { key: 'date of commercial approval', label: 'Date of Commercial approval', options: [2025, 2026] },
      { key: 'project id', label: 'Project ID', options: ['A-1'] },
      { key: 'project status', label: 'Project Status', options: ['NORMAL'] },
      { key: 'current stage', label: 'Current Stage', options: ['Stage 1'] },
      { key: 'project owner', label: 'Project Owner', options: ['Alice'] },
      { key: 'support mode', label: 'Support Mode', options: ['A'] },
      { key: 'odm', label: 'ODM', options: ['ODM-X'] }
    ] }
    const api = { getProjectFacts: vi.fn().mockResolvedValue(complete) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    expect([...document.querySelectorAll('[data-main-facets] > label')].map(row => row.firstChild.textContent)).toEqual([
      'Product Space', 'Date of Commercial approval', 'Project ID', 'Project Status', 'Current Stage', 'Project Owner', 'Support Mode'
    ])
    document.querySelector('[data-more-facets] input[value="odm"]').click()
    expect(document.querySelector('[name="field.odm"]')).toBeTruthy()
    expect(document.querySelector('[data-more-facets] input[value="odm"]').name).toBe('enabledMoreFilters')
    expect(document.querySelector('form').hasAttribute('data-preference-region')).toBe(true)
    document.querySelector('[data-more-facets] input[value="odm"]').click()
    expect(document.querySelector('[name="field.odm"]')).toBeNull()
  })

  it('disables Apply while the local snapshot is loading', async () => {
    let resolve
    const api = { getProjectFacts: vi.fn().mockImplementationOnce(() => new Promise(done => { resolve = done })).mockResolvedValue(payload) }
    const started = createProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.querySelector('[type="submit"]').disabled).toBe(true)
    resolve(payload); await started
    expect(document.querySelector('[type="submit"]').disabled).toBe(false)
  })

  it('keeps every business control disabled and shows loading options without a local cache', async () => {
    const empty = {
      ...payload,
      state: 'no_snapshot', projects: [], ownerHierarchy: [],
      facets: payload.facets.map(facet => ({ ...facet, options: [] }))
    }
    const api = { getProjectFacts: vi.fn().mockResolvedValue(empty) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.querySelector('[data-audit]').disabled).toBe(true)
    expect(document.querySelector('[type="submit"]').disabled).toBe(true)
    expect(document.querySelector('[data-reset]').disabled).toBe(true)
    expect(document.querySelector('[name="search"]').disabled).toBe(true)
    expect([...document.querySelectorAll('[data-main-facets] select')].every(item => item.disabled)).toBe(true)
    expect([...document.querySelectorAll('[data-main-facets] .multi-select__control')].every(item => item.disabled)).toBe(true)
    expect([...document.querySelectorAll('[data-main-facets] .multi-select__summary')].every(item => item.textContent === 'Loading…')).toBe(true)
    expect([...document.querySelectorAll('[data-more-facets] input')].every(item => item.disabled)).toBe(true)
  })

  it('renders all seven common filters from the immediate loading payload then polls to ready', async () => {
    const loading = { ...payload, state: 'loading', projects: [], ownerHierarchy: [], facets: fixedFacets }
    const api = {
      getProjectFacts: vi.fn().mockResolvedValueOnce(loading).mockResolvedValueOnce(payload),
      getProjectFactsStatus: vi.fn().mockResolvedValue({ state: 'ready', completed: 0, total: 0 }),
    }
    let releasePoll
    const pollDelay = vi.fn(() => new Promise(resolve => { releasePoll = resolve }))
    const component = createProjects({ root: document.querySelector('#app'), api, pollDelay })
    await component.start()
    expect([...document.querySelectorAll('[data-main-facets] > label')].map(row => row.firstChild.textContent)).toEqual([
      'Product Space', 'Date of Commercial approval', 'Project ID', 'Project Status', 'Current Stage', 'Project Owner', 'Support Mode'
    ])
    expect([...document.querySelectorAll('[data-main-facets] select')].every(item => item.disabled)).toBe(true)
    expect([...document.querySelectorAll('[data-main-facets] .multi-select__summary')].every(item => item.textContent === 'Loading…')).toBe(true)
    expect(document.querySelector('[role="status"]').textContent).toContain('Loading')
    releasePoll()
    await vi.waitFor(() => expect(api.getProjectFacts).toHaveBeenCalledTimes(2))
    await vi.waitFor(() => expect(document.querySelector('[type="submit"]').disabled).toBe(false))
    expect([...document.querySelectorAll('[data-main-facets] .multi-select__summary')]
      .every(item => !item.textContent.includes('Loading'))).toBe(true)
    expect(api.getProjectFacts.mock.calls[0][1]).toEqual({ details: false, snapshot: true })
    expect(api.getProjectFacts.mock.calls[1][1]).toEqual({ details: false })
  })

  it('treats an empty completed catalog as ready and does not poll again', async () => {
    const readyEmpty = {
      ...payload, state: 'ready', projects: [], ownerHierarchy: [],
      facets: fixedFacets.map(facet => ({ ...facet, options: [] })),
    }
    const api = { getProjectFacts: vi.fn().mockResolvedValue(readyEmpty) }
    const pollDelay = vi.fn(() => Promise.resolve())

    await createProjects({ root: document.querySelector('#app'), api, pollDelay }).start()

    expect(api.getProjectFacts).toHaveBeenCalledOnce()
    expect(api.getProjectFacts.mock.calls[0][1]).toEqual({ details: false, snapshot: true })
    expect(pollDelay).not.toHaveBeenCalled()
    expect(document.querySelector('[type="submit"]').disabled).toBe(false)
  })

  it('does not present catalog loading as a detail sync job', async () => {
    const loading = {
      ...payload, state: 'loading', projects: [], ownerHierarchy: [],
      facets: fixedFacets,
      sync: { state: 'loading', completed: 0, total: 0 },
    }
    const api = { getProjectFacts: vi.fn().mockResolvedValue(loading) }
    await createProjects({
      root: document.querySelector('#app'), api,
      pollDelay: () => new Promise(() => {}),
    }).start()

    expect(document.querySelector('[data-async-feedback]').hidden).toBe(true)
    expect(document.querySelector('[data-async-feedback]').dataset.state).toBe('idle')
    expect(document.querySelector('[data-cancel]').hidden).toBe(true)
    expect(document.querySelector('[role="status"]').textContent).toContain('Loading project catalog')
    expect(document.querySelector('[role="status"]').textContent).not.toContain('Syncing project details')
  })

  it('stops polling on failed state and when the component is destroyed', async () => {
    const loading = { ...payload, state: 'loading', projects: [], ownerHierarchy: [], facets: fixedFacets }
    const failed = { ...loading, state: 'failed' }
    const api = {
      getProjectFacts: vi.fn().mockResolvedValueOnce(loading).mockResolvedValueOnce(failed),
      getProjectFactsStatus: vi.fn().mockResolvedValue({ state: 'failed', completed: 0, total: 0 }),
    }
    const component = createProjects({ root: document.querySelector('#app'), api, pollDelay: () => Promise.resolve() })
    await component.start()
    await vi.waitFor(() => expect(document.querySelector('[role="status"]').textContent).toContain('failed'))
    expect(api.getProjectFacts).toHaveBeenCalledTimes(2)
    component.destroy()
    await Promise.resolve()
    expect(api.getProjectFacts).toHaveBeenCalledTimes(2)
  })

  it('polls catalog status without restarting catalog or requesting details', async () => {
    const partial = { ...payload, state: 'loading' }
    const api = {
      getProjectFacts: vi.fn().mockResolvedValueOnce(partial).mockResolvedValueOnce(payload),
      getProjectFactsStatus: vi.fn().mockResolvedValueOnce({ state: 'loading', completed: 0, total: 0 })
        .mockResolvedValueOnce({ state: 'ready', completed: 0, total: 0 }),
    }
    const component = createProjects({ root: document.querySelector('#app'), api, pollDelay: () => new Promise(resolve => setTimeout(resolve, 1)) })

    await component.start()
    expect(document.querySelector('[name="field.__product_space__"]').disabled).toBe(true)
    expect(document.querySelector('[type="submit"]').disabled).toBe(true)
    await vi.waitFor(() => expect(api.getProjectFactsStatus).toHaveBeenCalledTimes(2))
    await vi.waitFor(() => expect(api.getProjectFacts).toHaveBeenCalledTimes(2))
    await vi.waitFor(() => expect(document.querySelector('[type="submit"]').disabled).toBe(false))
    expect(api.getProjectFacts.mock.calls.map(call => call[1])).toEqual([
      { details: false, snapshot: true }, { details: false },
    ])
    component.destroy()
  })

  it('uses the shared styled checkbox class for optional filters', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.querySelector('[data-more-facets] input').classList).toContain('form-check-input')
    expect(document.querySelector('[data-more-facets]').classList).toContain('more-filter-options')
  })

  it('submits every selected field facet and project/person search', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    const form = document.querySelector('form')
    document.querySelector('[data-more-facets] input[value="unexpected owner"]').click()
    const productSpaceControl = form.elements['field.__product_space__']
    form.elements['field.unexpected owner'].value = 'Alice'
    form.elements['field.__product_space__'].value = 'DOPL'
    form.elements.search.value = 'Coco'
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(api.getProjectFacts).toHaveBeenCalledTimes(2))
    expect(form.elements['field.__product_space__']).toBe(productSpaceControl)
    expect(api.getProjectFacts.mock.calls[1][0]).toEqual({ fields: { '__product_space__': ['DOPL'], 'unexpected owner': ['Alice'] }, search: 'Coco' })
    expect(api.getProjectFacts.mock.calls[1][1]).toEqual({ details: true })
    expect(document.querySelector('[type="submit"]').disabled).toBe(false)
  })

  it('shows detail feedback only after Apply starts a real detail job', async () => {
    let resolveApply
    const api = { getProjectFacts: vi.fn().mockResolvedValueOnce(payload)
      .mockImplementationOnce(() => new Promise(resolve => { resolveApply = resolve })),
      cancelProjectSync: vi.fn() }
    await createProjects({
      root: document.querySelector('#app'), api,
      pollDelay: () => new Promise(() => {}),
    }).start()

    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))

    expect(document.querySelector('[data-async-feedback]').hidden).toBe(true)
    expect(document.querySelector('[type="submit"]').disabled).toBe(true)
    resolveApply({ ...payload, sync: { state: 'loading', completed: 0, total: 1 } })
    await vi.waitFor(() => expect(document.querySelector('[data-async-feedback]').dataset.state).toBe('running'))
    expect(document.querySelector('[data-async-feedback] [role="progressbar"]').dataset.indeterminate).toBe('false')
    expect(document.querySelector('[data-cancel]').hidden).toBe(false)
  })

  it('shows Product Space labels while submitting keys and supports select all and clear', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    const select = document.querySelector('[name="field.__product_space__"]')
    const multi = select.nextElementSibling
    expect([...select.options].map(option => option.textContent)).toEqual(['China Operator Business', 'TV Business'])
    multi.querySelector('.multi-select__control').click()
    multi.querySelector('[data-select-all]').click()
    expect(api.getProjectFacts).toHaveBeenCalledOnce()
    expect(multi.querySelector('.multi-select__tags').textContent).toContain('China Operator Business+1')
    multi.querySelector('.multi-select__control').click()
    multi.querySelector('[data-clear]').click()
    expect(api.getProjectFacts).toHaveBeenCalledOnce()
    expect(multi.querySelector('.multi-select__summary').textContent).toBe('All Product Space')
  })

  it('keeps catalog facets fixed while Apply updates only downstream results', async () => {
    const filtered = { ...payload, facets: [{ key: '__product_space__', label: 'Product Space', options: [] }],
      projects: [], ownerHierarchy: [] }
    const api = { getProjectFacts: vi.fn().mockResolvedValueOnce(payload).mockResolvedValueOnce(filtered) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    const select = document.querySelector('[name="field.__product_space__"]')
    select.options[0].selected = true
    select.dispatchEvent(new Event('change', { bubbles: true }))
    expect(api.getProjectFacts).toHaveBeenCalledOnce()
    expect([...select.options].map(option => option.value)).toEqual(['DOPL', 'TV'])
    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(api.getProjectFacts).toHaveBeenCalledTimes(2))
    expect([...select.options].map(option => option.value)).toEqual(['DOPL', 'TV'])
    expect(document.querySelectorAll('.project-card')).toHaveLength(0)
  })

  it('Reset clears local values and restores the authorized catalog scope without details', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    const select = document.querySelector('[name="field.__product_space__"]')
    select.options[0].selected = true
    document.querySelector('[name="search"]').value = 'Coco'
    document.querySelector('[name="reviewStartDate"]').value = '2026-08-01'
    document.querySelector('[name="reviewEndDate"]').value = '2026-08-08'
    document.querySelector('[data-reset]').click()
    await vi.waitFor(() => expect(api.getProjectFacts).toHaveBeenCalledTimes(2))
    expect(api.getProjectFacts.mock.calls[1]).toEqual([{ fields: {}, search: '' }, { details: false, reset: true }])
    expect([...select.selectedOptions]).toEqual([])
    expect(document.querySelector('[name="search"]').value).toBe('')
    expect(document.querySelector('[name="reviewStartDate"]').value).toBe('2026-08-01')
    expect(document.querySelector('[name="reviewEndDate"]').value).toBe('2026-08-08')
    expect([...select.options].map(option => option.value)).toEqual(['DOPL', 'TV'])
  })

  it('Reset restores authorized Product Space candidates after a narrowed catalog response', async () => {
    const narrowed = { ...payload, facets: payload.facets.map(facet => facet.key === '__product_space__'
      ? { ...facet, options: [{ value: 'DOPL', label: 'China Operator Business' }] }
      : facet) }
    const api = { getProjectFacts: vi.fn()
      .mockResolvedValueOnce(narrowed).mockResolvedValueOnce(payload) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    expect([...document.querySelector('[name="field.__product_space__"]').options].map(option => option.value)).toEqual(['DOPL'])
    expect([...document.querySelectorAll('[data-product-space-group] summary strong')].map(item => item.textContent)).toEqual(
      productSpaces.map(item => item.label))

    document.querySelector('[name="field.__product_space__"] option').selected = true
    document.querySelector('[name="search"]').value = 'filtered'
    document.querySelector('[data-reset]').click()
    await vi.waitFor(() => expect(api.getProjectFacts).toHaveBeenCalledTimes(2))

    const restored = document.querySelector('[name="field.__product_space__"]')
    expect([...restored.options].map(option => option.value)).toEqual(['DOPL', 'TV'])
    expect([...restored.selectedOptions]).toEqual([])
    expect(document.querySelector('[name="search"]').value).toBe('')
  })

  it('refreshes results when the applied detail sync completes', async () => {
    const syncing = { ...payload, sync: { state: 'loading', completed: 0, total: 1 } }
    const updated = { ...payload, sync: { state: 'ready', completed: 1, total: 1 },
      projects: [], ownerHierarchy: [] }
    const api = { getProjectFacts: vi.fn().mockResolvedValueOnce(payload)
      .mockResolvedValueOnce(syncing).mockResolvedValueOnce(updated),
      getProjectFactsStatus: vi.fn().mockResolvedValue({ state: 'ready', completed: 1, total: 1 }),
      cancelProjectSync: vi.fn() }
    await createProjects({ root: document.querySelector('#app'), api, pollDelay: () => Promise.resolve() }).start()
    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(document.querySelectorAll('.project-card')).toHaveLength(0))
    expect(document.querySelector('[type="submit"]').disabled).toBe(false)
  })

  it('does not apply a completed job after controls change and cancel keeps local results', async () => {
    let finishPoll
    const syncing = { ...payload, sync: { state: 'loading', completed: 0, total: 1 } }
    const api = { getProjectFacts: vi.fn().mockResolvedValueOnce(payload).mockResolvedValueOnce(syncing),
      getProjectFactsStatus: vi.fn().mockImplementationOnce(() => new Promise(resolve => { finishPoll = () => resolve({ state: 'ready', completed: 1, total: 1 }) })),
      cancelProjectSync: vi.fn().mockResolvedValue({ cancelled: true }) }
    await createProjects({ root: document.querySelector('#app'), api, pollDelay: () => Promise.resolve() }).start()
    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(finishPoll).toBeTypeOf('function'))
    document.querySelector('[name="search"]').value = 'changed'
    document.querySelector('[data-cancel]').click()
    await vi.waitFor(() => expect(api.cancelProjectSync).toHaveBeenCalledOnce())
    finishPoll()
    await Promise.resolve()
    expect(document.querySelector('[data-projects]').textContent).not.toContain('Old job result')
    expect(document.querySelector('[data-projects]').textContent).toContain('Apollo')
    expect(document.querySelector('[type="submit"]').disabled).toBe(false)
  })

  it('shows the complete Core Product Space names without a search control', async () => {
    const facets = payload.facets.map(facet => facet.key === '__product_space__'
      ? { ...facet, options: productSpaces }
      : facet)
    const api = { getProjectFacts: vi.fn().mockResolvedValue({ ...payload, facets }) }

    await createProjects({ root: document.querySelector('#app'), api }).start()

    const multi = document.querySelector('[name="field.__product_space__"]').nextElementSibling
    expect(multi.querySelector('input[type="search"]')).toBeNull()
    expect([...multi.querySelectorAll('.multi-select__option span')].map(node => node.textContent)).toEqual(productSpaces.map(item => item.label))
  })

  it('reviews the current controls without requiring Apply and keeps an independent date window', async () => {
    const api = {
      getProjectFacts: vi.fn().mockResolvedValue(payload),
      createConfluenceAudit: vi.fn().mockResolvedValue({ auditId: 'a1', status: 'queued', stage: '', progress: { processed: 0, total: 0 } }),
      getConfluenceAudit: vi.fn()
        .mockResolvedValueOnce({ auditId: 'a1', status: 'running', stage: 'loading_versions', progress: { processed: 1, total: 8 } })
        .mockResolvedValueOnce({ auditId: 'a1', status: 'completed', stage: 'finalizing', progress: { processed: 1, total: 1 } }),
      exportConfluenceAudit: vi.fn().mockResolvedValue({ download: { id: 'd1', fileName: 'review.zip' } }),
      downloadUrl: id => '/api/downloads/' + id,
    }
    await createProjects({
      root: document.querySelector('#app'), api, pollDelay: () => Promise.resolve()
    }).start()
    document.querySelector('[name="reviewStartDate"]').value = '2026-08-17'
    document.querySelector('[name="reviewEndDate"]').value = '2026-08-24'
    const supportMode = document.querySelector('[name="field.support mode"]')
    for (const option of supportMode.options) option.selected = ['A', 'B'].includes(option.value)
    supportMode._multiSelect?.syncFromSelect()
    document.querySelector('[name="search"]').value = 'changed before review'
    const projectFactCalls = api.getProjectFacts.mock.calls.length
    document.querySelector('[data-audit]').click()
    await vi.waitFor(() => expect(api.createConfluenceAudit).toHaveBeenCalledOnce())
    expect(api.getProjectFacts).toHaveBeenCalledTimes(projectFactCalls)
    expect(api.getProjectFacts.mock.calls.at(-1)).toEqual([
      { fields: {}, search: '' }, { details: false, snapshot: true }
    ])
    expect(api.createConfluenceAudit).toHaveBeenCalledWith({
      filters: { fields: { 'support mode': ['A', 'B'] }, search: 'changed before review' },
      startDate: '2026-08-17', endDate: '2026-08-24'
    })
    await vi.waitFor(() => expect(document.querySelector('[data-audit-download]').disabled).toBe(false))
    expect(document.querySelector('[data-async-feedback]').dataset.state).toBe('success')
    expect(document.querySelector('[data-audit-download]').textContent).toBe('Download')
    expect(document.querySelector('[data-audit-findings]')).toBeNull()
  })

  it('uses one root feedback component and renders a delayed child as text without changing its progress scale', async () => {
    const api = {
      getProjectFacts: vi.fn().mockResolvedValueOnce(payload)
        .mockResolvedValueOnce({ ...payload, sync: {
          state: 'loading', completed: 9, total: 10,
          task: { state: 'running', progress: { processed: 2, total: 10 }, visibleChild: { label: 'Loading project A', state: 'running' } },
        } }),
      cancelProjectSync: vi.fn(),
    }
    await createProjects({ root: document.querySelector('#app'), api, pollDelay: () => new Promise(() => {}) }).start()
    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(document.querySelector('[data-async-feedback]').dataset.state).toBe('running'))
    expect(document.querySelectorAll('.async-feedback')).toHaveLength(1)
    expect(document.querySelector('[data-async-feedback] [role="progressbar"]').getAttribute('aria-valuenow')).toBe('2')
    expect(document.querySelector('[data-async-feedback]').textContent).toContain('Loading project A')
  })

  it.each([
    ['no_snapshot', 'No local project snapshot'],
    ['schema_error', 'Local project snapshot is unreadable'],
    ['partial_success', 'Some project facts are stale or failed']
  ])('renders %s state', async (state, message) => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue({ ...payload, state, projects: [] }) }
    await createProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.querySelector('[role="status"]').textContent).toContain(message)
  })
})
